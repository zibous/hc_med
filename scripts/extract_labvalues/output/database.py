import sqlite3
from pathlib import Path
from datetime import datetime
import logging


def write_to_db(records: list[dict], db_path: Path):
    """
    Write normalized lab records into the existing DB schema.
    Expects tables: patienten, befunde, laborwerte (with patient_id, befund_id).
    """
    logger = logging.getLogger("database")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Ensure schema exists
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS patienten (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vorname TEXT NOT NULL,
            nachname TEXT NOT NULL,
            geburtsdatum TEXT NOT NULL,
            geschlecht TEXT NOT NULL CHECK(geschlecht IN ('m', 'w', 'd')),
            UNIQUE(vorname, nachname, geburtsdatum)
        );

        CREATE TABLE IF NOT EXISTS befunde (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL REFERENCES patienten(id),
            datum TEXT NOT NULL,
            quelldatei TEXT NOT NULL,
            labor TEXT,
            format TEXT,
            nuechtern INTEGER DEFAULT 1,
            importiert_am TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(patient_id, quelldatei)
        );

        CREATE TABLE IF NOT EXISTS laborwerte (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            befund_id INTEGER NOT NULL REFERENCES befunde(id),
            patient_id INTEGER NOT NULL REFERENCES patienten(id),
            datum TEXT NOT NULL,
            alter_bei_messung INTEGER,
            gruppe TEXT NOT NULL,
            test_standard TEXT NOT NULL,
            test_original TEXT NOT NULL,
            wert_norm TEXT NOT NULL,
            einheit_norm TEXT,
            wert_original TEXT NOT NULL,
            einheit_original TEXT,
            normbereich TEXT,
            flag TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_laborwerte_datum ON laborwerte(datum);
        CREATE INDEX IF NOT EXISTS idx_laborwerte_test ON laborwerte(test_standard);
        CREATE INDEX IF NOT EXISTS idx_laborwerte_gruppe ON laborwerte(gruppe);
        CREATE INDEX IF NOT EXISTS idx_laborwerte_patient_test ON laborwerte(patient_id, test_standard, datum);
        CREATE INDEX IF NOT EXISTS idx_befunde_patient ON befunde(patient_id);
    """)

    # Clear existing data (full reimport)
    cur.execute("DELETE FROM laborwerte")
    cur.execute("DELETE FROM befunde")

    # Get or create patient
    # We need patient info from the caller - use a default placeholder if not in DB
    row = cur.execute("SELECT id FROM patienten LIMIT 1").fetchone()
    if row:
        patient_id = row[0]
    else:
        # No patient exists yet - create a placeholder (will be updated by caller)
        cur.execute(
            "INSERT INTO patienten (vorname, nachname, geburtsdatum, geschlecht) VALUES (?, ?, ?, ?)",
            ("Unbekannt", "Unbekannt", "1900-01-01", "m")
        )
        patient_id = cur.lastrowid

    # Group records by source date → befund
    from collections import defaultdict
    records_by_date = defaultdict(list)
    for r in records:
        datum = r.get("Datum", "")
        records_by_date[datum].append(r)

    # Create befunde and insert laborwerte
    now = datetime.now().isoformat(timespec="seconds")

    try:
        for datum, date_records in sorted(records_by_date.items()):
            # Insert befund for this date
            cur.execute(
                """INSERT OR IGNORE INTO befunde (patient_id, datum, quelldatei, labor, format, nuechtern, importiert_am)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (patient_id, datum, f"{datum}_import", "Import", "auto", 1, now)
            )
            # Get befund_id (might already exist from OR IGNORE)
            befund_row = cur.execute(
                "SELECT id FROM befunde WHERE patient_id=? AND datum=? ORDER BY id DESC LIMIT 1",
                (patient_id, datum)
            ).fetchone()
            befund_id = befund_row[0] if befund_row else cur.lastrowid

            # Insert laborwerte
            for r in date_records:
                alter_val = r.get("Alter", "")
                try:
                    alter_int = int(alter_val) if alter_val else None
                except (ValueError, TypeError):
                    alter_int = None

                cur.execute(
                    """INSERT INTO laborwerte
                       (befund_id, patient_id, datum, alter_bei_messung, gruppe,
                        test_standard, test_original, wert_norm, einheit_norm,
                        wert_original, einheit_original, normbereich, flag)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        befund_id,
                        patient_id,
                        datum,
                        alter_int,
                        r.get("Gruppe", ""),
                        r.get("Test_Standard", ""),
                        r.get("Test", ""),
                        r.get("Wert_Norm", ""),
                        r.get("Einheit_Norm", ""),
                        r.get("Wert", ""),
                        r.get("Einheit", ""),
                        r.get("Normbereich", ""),
                        r.get("Flag", ""),
                    )
                )

        conn.commit()
        logger.info("DB: %d Laborwerte, %d Befunde geschrieben", len(records), len(records_by_date))
    except Exception:
        logger.exception("DB Insert fehlgeschlagen")
        conn.rollback()
        raise
    finally:
        conn.close()
