"""Import von Körperdaten aus hc_scale (Mi Scale / Waage) in die hc_med DB.

Liest die Waage-Datenbank und importiert:
- Gewicht (kg)
- BMI
- Fettanteil (%)
- Muskelmasse (%)
- Körperwasser (%)

Multi-User: Nutzt userlist.yaml für Pfade und Patientendaten.
Wird beim `make labor-reset` automatisch aufgerufen.
"""

import sqlite3
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

import yaml

# Pfade
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
USERLIST_PATH = DATA_DIR / "userlist.yaml"


def load_userlist() -> dict:
    """Lädt die Userliste."""
    if not USERLIST_PATH.exists():
        return {}
    data = yaml.safe_load(USERLIST_PATH.read_text(encoding="utf-8")) or {}
    return data.get("patient", {})


def calculate_age(measurement_date: str, geburtsdatum: date) -> int:
    """Berechnet das Alter zum Messzeitpunkt."""
    try:
        parts = measurement_date.split("-")
        d = date(int(parts[0]), int(parts[1]), int(parts[2]))
        age = d.year - geburtsdatum.year
        if (d.month, d.day) < (geburtsdatum.month, geburtsdatum.day):
            age -= 1
        return age
    except (ValueError, IndexError):
        return 0


def resolve_scale_db(scaledb_path: str) -> Path | None:
    """Löst den scaledb-Pfad relativ zum DATA_DIR auf."""
    if not scaledb_path:
        return None
    # Relativ zum data/ Verzeichnis auflösen
    resolved = (DATA_DIR / scaledb_path).resolve()
    if resolved.exists():
        return resolved
    # Absoluter Pfad als Fallback
    abs_path = Path(scaledb_path)
    if abs_path.exists():
        return abs_path
    return None


def import_scale_data(user_id: str | None = None):
    """Importiert Waage-Daten aus hc_scale in die hc_med DB.

    Args:
        user_id: Optionaler User-ID. Wenn None, werden alle User importiert.
    """
    users = load_userlist()
    if not users:
        print("  ⚠️  userlist.yaml nicht gefunden oder leer")
        return

    if user_id:
        if user_id not in users:
            print(f"  ⚠️  User '{user_id}' nicht in userlist.yaml")
            return
        users = {user_id: users[user_id]}

    total_imported = 0
    for uid, info in users.items():
        scaledb_str = info.get("scaledb", "")
        if not scaledb_str:
            continue

        med_db_path = DATA_DIR / "user" / uid / "labor.db"
        if not med_db_path.exists():
            print(f"  ⚠️  [{uid}] labor.db nicht vorhanden – übersprungen")
            continue

        scale_path = resolve_scale_db(scaledb_str)
        if not scale_path:
            print(f"  ⚠️  [{uid}] Scale-DB nicht gefunden: {scaledb_str}")
            continue

        count = _import_for_user(uid, info, scale_path, med_db_path)
        total_imported += count

    if total_imported:
        print(f"\n  ✓ Gesamt: {total_imported} Körperdaten importiert")


def _import_for_user(uid: str, info: dict, scale_path: Path, med_db_path: Path) -> int:
    """Importiert Scale-Daten für einen einzelnen User."""
    vorname = info.get("vorname", "")
    scale_name = info.get("scale_name", vorname)  # Fallback auf vorname
    geburtsdatum_str = info.get("geburtsdatum", "1960-01-01")
    geburtsdatum = date(*[int(x) for x in geburtsdatum_str.split("-")])

    # Scale-Daten lesen (Name = scale_name oder Vorname des Users)
    scale_conn = sqlite3.connect(str(scale_path))
    rows = scale_conn.execute("""
        SELECT date, weight, bmi, fat, muscle, water, visceral, lbm, protein, poi
        FROM daily_miscale
        WHERE name=? AND weight > 0
        ORDER BY date
    """, (scale_name,)).fetchall()
    scale_conn.close()

    if not rows:
        print(f"  ⚠️  [{uid}] Keine Daten für '{scale_name}' in hc_scale")
        return 0

    # In hc_med DB importieren
    med_conn = sqlite3.connect(str(med_db_path))
    med_conn.execute("PRAGMA journal_mode=WAL")

    # Patient-ID holen
    patient = med_conn.execute("SELECT id FROM patienten LIMIT 1").fetchone()
    if not patient:
        print(f"  ⚠️  [{uid}] Kein Patient in labor.db")
        med_conn.close()
        return 0
    patient_id = patient[0]

    # Befund für Scale-Daten anlegen
    med_conn.execute("""
        INSERT OR IGNORE INTO befunde (patient_id, datum, quelldatei, labor, format)
        VALUES (?, ?, 'hc_scale_import', 'Mi Scale Waage', 'scale')
    """, (patient_id, rows[-1][0]))
    med_conn.commit()
    befund_id = med_conn.execute(
        "SELECT id FROM befunde WHERE quelldatei='hc_scale_import'"
    ).fetchone()[0]

    # Alte Scale-Daten löschen
    med_conn.execute("DELETE FROM laborwerte WHERE befund_id=?", (befund_id,))

    # Mapping: (db_column, test_standard, einheit, normbereich)
    TESTS = [
        ("weight", "Gewicht", "kg", "60-80"),
        ("bmi", "BMI", "", "18.5-25.0"),
        ("fat", "Fettgehalt", "%", "10-20"),
        ("muscle", "Muskelmasse", "%", "40-55"),
        ("water", "Körperwasser", "%", "50-68"),
        ("visceral", "Viszeralfett", "Lvl", "1-12"),
        ("lbm", "Fettfreie Masse", "kg", "50-70"),
        ("protein", "Proteinanteil", "%", "16-22"),
        ("poi", "Knochenmasse", "kg", "10-15"),
    ]

    # Pro Monat: letzten Wert nehmen (kompakter)
    weekly = defaultdict(list)
    for row in rows:
        d = row[0]  # YYYY-MM-DD
        weekly[d[:7]].append(row)

    insert_rows = []
    for month, month_rows in sorted(weekly.items()):
        r = month_rows[-1]
        datum = r[0]
        alter = calculate_age(datum, geburtsdatum)

        for i, (col, test, einheit, norm) in enumerate(TESTS):
            val = r[i + 1]
            if val and val > 0:
                # Flag berechnen
                flag = ""
                try:
                    parts = norm.split("-")
                    if len(parts) == 2:
                        lo, hi = float(parts[0]), float(parts[1])
                        if val < lo:
                            flag = "L"
                        elif val > hi:
                            flag = "H"
                except ValueError:
                    pass

                insert_rows.append((
                    befund_id, patient_id, datum, alter,
                    "Körperdaten", test, test,
                    f"{val:.1f}", einheit, f"{val:.1f}", einheit,
                    norm, flag,
                ))

    med_conn.executemany("""
        INSERT INTO laborwerte
        (befund_id, patient_id, datum, alter_bei_messung, gruppe,
         test_standard, test_original, wert_norm, einheit_norm,
         wert_original, einheit_original, normbereich, flag)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, insert_rows)
    med_conn.commit()
    med_conn.close()

    print(f"  ✓ [{uid}] {len(insert_rows)} Körperdaten importiert ({len(weekly)} Monate)")
    return len(insert_rows)


if __name__ == "__main__":
    # Optional: User-ID als Argument
    user = sys.argv[1] if len(sys.argv) > 1 else None
    import_scale_data(user)
