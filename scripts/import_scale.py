"""Import von Körperdaten aus hc_scale (Mi Scale / Waage) in die hc_med DB.

Liest die Waage-Datenbank und importiert:
- Gewicht (kg)
- BMI
- Fettanteil (%)
- Muskelmasse (%)
- Körperwasser (%)

Wird beim `make labor-reset` automatisch aufgerufen.
"""

import sqlite3
from datetime import date
from pathlib import Path

import yaml

# Pfade
SCALE_DB = Path("/dockerapps/apps_v2/hc_scale/data/miscaledata.db")
SCALE_DB_ALT = Path(__file__).parent.parent.parent / "hc_scale" / "data" / "miscaledata.db"
MED_DB = Path(__file__).parent.parent / "data" / "labor.db"
CONFIG_PATH = Path(__file__).parent.parent / "data" / "labor_config.yaml"

# Config laden
_config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
_patient = _config.get("patient", {})

PATIENT_GEBURTSDATUM = date(*[int(x) for x in _patient.get("geburtsdatum", "1955-12-16").split("-")])
PATIENT_NAME = "Peter"  # Name in hc_scale DB


def get_scale_db() -> Path:
    """Findet die hc_scale Datenbank."""
    if SCALE_DB.exists():
        return SCALE_DB
    if SCALE_DB_ALT.exists():
        return SCALE_DB_ALT
    return None


def calculate_age(measurement_date: str) -> int:
    """Berechnet das Alter zum Messzeitpunkt."""
    try:
        parts = measurement_date.split("-")
        d = date(int(parts[0]), int(parts[1]), int(parts[2]))
        age = d.year - PATIENT_GEBURTSDATUM.year
        if (d.month, d.day) < (PATIENT_GEBURTSDATUM.month, PATIENT_GEBURTSDATUM.day):
            age -= 1
        return age
    except (ValueError, IndexError):
        return 0


def import_scale_data():
    """Importiert Waage-Daten aus hc_scale in die hc_med DB."""
    scale_path = get_scale_db()
    if not scale_path:
        print("  ⚠️  hc_scale DB nicht gefunden – Körperdaten-Import übersprungen")
        return 0

    if not MED_DB.exists():
        print("  ⚠️  hc_med DB nicht gefunden – erst make labor ausführen")
        return 0

    # Scale-Daten lesen (nur Peter, tägliche Werte)
    scale_conn = sqlite3.connect(str(scale_path))
    rows = scale_conn.execute("""
        SELECT date, weight, bmi, fat, muscle, water, visceral, lbm, protein, poi
        FROM daily_miscale
        WHERE name=? AND weight > 0
        ORDER BY date
    """, (PATIENT_NAME,)).fetchall()
    scale_conn.close()

    if not rows:
        print(f"  ⚠️  Keine Daten für '{PATIENT_NAME}' in hc_scale gefunden")
        return 0

    # In hc_med DB importieren
    med_conn = sqlite3.connect(str(MED_DB))
    med_conn.execute("PRAGMA journal_mode=WAL")

    # Patient-ID holen
    patient = med_conn.execute("SELECT id FROM patienten LIMIT 1").fetchone()
    if not patient:
        print("  ⚠️  Kein Patient in hc_med DB")
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

    # Nicht jeden Tag importieren – nur wöchentliche Durchschnitte für übersichtliche Charts
    from collections import defaultdict
    weekly = defaultdict(list)
    for row in rows:
        # Woche berechnen (ISO-Woche)
        d = row[0]  # YYYY-MM-DD
        weekly[d[:7]].append(row)  # Pro Monat gruppieren (kompakter)

    insert_rows = []
    for month, month_rows in sorted(weekly.items()):
        # Letzten Wert des Monats nehmen
        r = month_rows[-1]
        datum = r[0]
        alter = calculate_age(datum)

        for i, (col, test, einheit, norm) in enumerate(TESTS):
            val = r[i + 1]  # weight=1, bmi=2, fat=3, muscle=4, water=5
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

    print(f"  ✓ {len(insert_rows)} Körperdaten aus hc_scale importiert ({len(weekly)} Monate)")
    return len(insert_rows)


if __name__ == "__main__":
    import_scale_data()
