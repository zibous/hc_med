import logging
import sqlite3
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

from config.app_config import config

log = logging.getLogger("labor_pipeline")

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
    # Das DATA_DIR liegt parallel zum Skriptordner
    data_dir = config.PROJECT_DIR / "data"
    resolved = (data_dir / scaledb_path).resolve()
    if resolved.exists():
        return resolved
    abs_path = Path(scaledb_path)
    if abs_path.exists():
        return abs_path
    return None

def import_scale_data(user_id: str):
    """Importiert Waage-Daten aus hc_scale in die aktive hc_med DB."""
    # Patientendaten und Scale-DB direkt aus der zentralen config ziehen
    patient_data = getattr(config, "_patient", {})
    scaledb_str = patient_data.get("scaledb", "")
    
    if not scaledb_str:
        log.info(f"  ℹ️  [{user_id}] Kein 'scaledb'-Eintrag hinterlegt – Übersprungen.")
        return

    med_db_path = config.DB_FILE
    scale_path = resolve_scale_db(scaledb_str)
    
    if not scale_path:
        log.warning(f"  ⚠️  [{user_id}] Scale-DB nicht gefunden unter: {scaledb_str}")
        return

    vorname = patient_data.get("vorname", "")
    scale_name = patient_data.get("scale_name", vorname)
    geburtsdatum_str = patient_data.get("geburtsdatum", "1960-01-01")
    geburtsdatum = date(*[int(x) for x in geburtsdatum_str.split("-")])

    # Scale-Daten einlesen
    scale_conn = sqlite3.connect(str(scale_path))
    rows = scale_conn.execute("""
        SELECT date, weight, bmi, fat, muscle, water, visceral, lbm, protein, poi
        FROM daily_miscale
        WHERE name=? AND weight > 0
        ORDER BY date
    """, (scale_name,)).fetchall()
    scale_conn.close()

    if not rows:
        log.warning(f"  ⚠️  [{user_id}] Keine Waage-Daten für Name '{scale_name}' in hc_scale gefunden.")
        return

    # In aktive hc_med DB einspeisen
    med_conn = sqlite3.connect(str(med_db_path))
    med_conn.execute("PRAGMA journal_mode=WAL")

    # Echte, interne Patienten-ID holen
    patient = med_conn.execute("SELECT id FROM patienten LIMIT 1").fetchone()
    if not patient:
        log.warning(f"  ⚠️  [{user_id}] SQLite-Fehler: Noch kein Patient in der Datenbank vorhanden.")
        med_conn.close()
        return
    patient_id = patient[0]

    # Befund-Kopf für den Waage-Import absichern
    med_conn.execute("""
        INSERT OR IGNORE INTO befunde (patient_id, datum, quelldatei, labor, format)
        VALUES (?, ?, 'hc_scale_import', 'Mi Scale Waage', 'scale')
    """, (patient_id, rows[-1][0]))
    med_conn.commit()
    
    befund_id = med_conn.execute(
        "SELECT id FROM befunde WHERE quelldatei='hc_scale_import'"
    ).fetchone()[0]

    # Vorhandene Altdaten dieses Imports gezielt überschreiben
    med_conn.execute("DELETE FROM laborwerte WHERE befund_id=?", (befund_id,))

    # Standard-Grenzwerte und Konfigurationen
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

    # Pro Monat den letzten verfügbaren Wert kompakt bündeln
    weekly = defaultdict(list)
    for row in rows:
        d = row[0]
        weekly[d[:7]].append(row)

    insert_rows = []
    for month, month_rows in sorted(weekly.items()):
        r = month_rows[-1]
        datum = r[0]
        alter = calculate_age(datum, geburtsdatum)

        for i, (col, test, einheit, norm) in enumerate(TESTS):
            val = r[i + 1]
            if val and val > 0:
                flag = ""
                try:
                    parts = norm.split("-")
                    if len(parts) == 2:
                        lo, hi = float(parts[0]), float(parts[1])
                        if val < lo: flag = "L"
                        elif val > hi: flag = "H"
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

    log.info(f"  ✓ [{user_id}] {len(insert_rows)} Körperdaten erfolgreich aus Scale-DB geladen ({len(weekly)} Monate).")
