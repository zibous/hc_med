"""SQLite-Datenbank für Laborwerte.

Schema:
- patienten: Stammdaten (Geburtsdatum, Geschlecht, Name)
- befunde: Quelldateien mit Datum und Labor/Arzt
- laborwerte: Einzelne Messwerte mit Normalisierung und Gruppenzuordnung

Nutzung:
    from labor_db import LaborDB
    db = LaborDB()
    db.import_results(all_results, source_file="2024-02-08-Laborbefund.txt")
    db.export_csv(output_path)
"""

import sqlite3
from datetime import date
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "labor.db"


SCHEMA = """
CREATE TABLE IF NOT EXISTS patienten (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vorname TEXT NOT NULL,
    nachname TEXT NOT NULL,
    geburtsdatum TEXT NOT NULL,  -- ISO: YYYY-MM-DD
    geschlecht TEXT NOT NULL CHECK(geschlecht IN ('m', 'w', 'd')),
    UNIQUE(vorname, nachname, geburtsdatum)
);

CREATE TABLE IF NOT EXISTS befunde (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patienten(id),
    datum TEXT NOT NULL,          -- ISO: YYYY-MM-DD
    quelldatei TEXT NOT NULL,     -- Dateiname
    labor TEXT,                   -- Labor/Arztpraxis
    format TEXT,                  -- Erkanntes Dateiformat
    nuechtern INTEGER DEFAULT 1, -- 1=ja/unbekannt, 0=nein
    importiert_am TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(patient_id, quelldatei)
);

CREATE TABLE IF NOT EXISTS laborwerte (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    befund_id INTEGER NOT NULL REFERENCES befunde(id),
    patient_id INTEGER NOT NULL REFERENCES patienten(id),
    datum TEXT NOT NULL,          -- ISO: YYYY-MM-DD
    alter_bei_messung INTEGER,    -- Alter in Jahren
    gruppe TEXT NOT NULL,         -- Medizinische Gruppe
    test_standard TEXT NOT NULL,  -- Normalisierter Testname
    test_original TEXT NOT NULL,  -- Original-Testname aus Befund
    wert_norm TEXT NOT NULL,      -- Normalisierter Wert
    einheit_norm TEXT,            -- Normalisierte Einheit
    wert_original TEXT NOT NULL,  -- Original-Wert
    einheit_original TEXT,        -- Original-Einheit
    normbereich TEXT,             -- Referenzbereich
    flag TEXT                     -- H=hoch, L=niedrig
);

-- Indizes für häufige Abfragen
CREATE INDEX IF NOT EXISTS idx_laborwerte_datum ON laborwerte(datum);
CREATE INDEX IF NOT EXISTS idx_laborwerte_test ON laborwerte(test_standard);
CREATE INDEX IF NOT EXISTS idx_laborwerte_gruppe ON laborwerte(gruppe);
CREATE INDEX IF NOT EXISTS idx_laborwerte_patient_test ON laborwerte(patient_id, test_standard, datum);
CREATE INDEX IF NOT EXISTS idx_befunde_patient ON befunde(patient_id);

-- View: Zeitreihe pro Test
CREATE VIEW IF NOT EXISTS v_zeitreihe AS
SELECT
    p.nachname || ', ' || p.vorname AS patient,
    l.datum,
    l.alter_bei_messung AS alter_jahre,
    l.gruppe,
    l.test_standard AS test,
    l.wert_norm AS wert,
    l.einheit_norm AS einheit,
    l.normbereich,
    l.flag,
    b.quelldatei
FROM laborwerte l
JOIN patienten p ON p.id = l.patient_id
JOIN befunde b ON b.id = l.befund_id
ORDER BY l.test_standard, l.datum;

-- View: Letzte Werte pro Test
CREATE VIEW IF NOT EXISTS v_aktuell AS
SELECT
    l.gruppe,
    l.test_standard AS test,
    l.wert_norm AS wert,
    l.einheit_norm AS einheit,
    l.normbereich,
    l.flag,
    l.datum,
    l.alter_bei_messung AS alter_jahre
FROM laborwerte l
WHERE l.id IN (
    SELECT id FROM laborwerte l2
    WHERE l2.patient_id = l.patient_id AND l2.test_standard = l.test_standard
    ORDER BY l2.datum DESC
    LIMIT 1
)
ORDER BY l.gruppe, l.test_standard;

-- View: Pathologische Werte
CREATE VIEW IF NOT EXISTS v_pathologisch AS
SELECT
    l.datum,
    l.gruppe,
    l.test_standard AS test,
    l.wert_norm AS wert,
    l.einheit_norm AS einheit,
    l.normbereich,
    l.flag,
    b.quelldatei
FROM laborwerte l
JOIN befunde b ON b.id = l.befund_id
WHERE l.flag IN ('H', 'L')
ORDER BY l.datum DESC, l.gruppe;
"""


class LaborDB:
    """Verwaltung der Laborwerte-Datenbank."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self):
        """Erstellt Tabellen und Views falls noch nicht vorhanden."""
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def get_or_create_patient(
        self, vorname: str, nachname: str, geburtsdatum: date, geschlecht: str
    ) -> int:
        """Gibt die Patient-ID zurück, erstellt den Patienten falls nötig."""
        cursor = self.conn.execute(
            "SELECT id FROM patienten WHERE vorname=? AND nachname=? AND geburtsdatum=?",
            (vorname, nachname, geburtsdatum.isoformat()),
        )
        row = cursor.fetchone()
        if row:
            return row[0]

        cursor = self.conn.execute(
            "INSERT INTO patienten (vorname, nachname, geburtsdatum, geschlecht) VALUES (?, ?, ?, ?)",
            (vorname, nachname, geburtsdatum.isoformat(), geschlecht),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_or_create_befund(
        self, patient_id: int, datum: str, quelldatei: str, labor: str = "", format: str = "", nuechtern: int = 1
    ) -> int:
        """Gibt die Befund-ID zurück, erstellt den Befund falls nötig."""
        cursor = self.conn.execute(
            "SELECT id FROM befunde WHERE patient_id=? AND quelldatei=?",
            (patient_id, quelldatei),
        )
        row = cursor.fetchone()
        if row:
            # nuechtern-Flag aktualisieren
            self.conn.execute("UPDATE befunde SET nuechtern=? WHERE id=?", (nuechtern, row[0]))
            self.conn.commit()
            return row[0]

        cursor = self.conn.execute(
            "INSERT INTO befunde (patient_id, datum, quelldatei, labor, format, nuechtern) VALUES (?, ?, ?, ?, ?, ?)",
            (patient_id, datum, quelldatei, labor, format, nuechtern),
        )
        self.conn.commit()
        return cursor.lastrowid

    def import_results(
        self,
        results: list[dict],
        quelldatei: str,
        patient_id: int,
        format: str = "",
        labor: str = "",
        nuechtern: int = 1,
    ) -> int:
        """Importiert eine Liste von Laborwerten in die Datenbank.

        Returns: Anzahl der importierten Werte.
        """
        if not results:
            return 0

        # Befund-Datum: erstes Datum aus den Ergebnissen
        datum = results[0].get("Datum", "")
        befund_id = self.get_or_create_befund(patient_id, datum, quelldatei, labor, format, nuechtern)

        # Alte Werte für diesen Befund löschen (Reimport)
        self.conn.execute("DELETE FROM laborwerte WHERE befund_id=?", (befund_id,))

        rows = []
        for r in results:
            rows.append((
                befund_id,
                patient_id,
                r.get("Datum", ""),
                r.get("Alter", None),
                r.get("Gruppe", ""),
                r.get("Test_Standard", ""),
                r.get("Test", ""),
                r.get("Wert_Norm", ""),
                r.get("Einheit_Norm", ""),
                r.get("Wert", ""),
                r.get("Einheit", ""),
                r.get("Normbereich", ""),
                r.get("Flag", ""),
            ))

        self.conn.executemany(
            """INSERT INTO laborwerte
            (befund_id, patient_id, datum, alter_bei_messung, gruppe,
             test_standard, test_original, wert_norm, einheit_norm,
             wert_original, einheit_original, normbereich, flag)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        self.conn.commit()
        return len(rows)

    def export_csv(self, output_path: Path, patient_id: int | None = None):
        """Exportiert alle Laborwerte als CSV."""
        query = """
            SELECT datum, alter_bei_messung, gruppe, test_standard, test_original,
                   wert_norm, einheit_norm, wert_original, einheit_original, normbereich, flag
            FROM laborwerte
        """
        params = ()
        if patient_id:
            query += " WHERE patient_id=?"
            params = (patient_id,)
        query += " ORDER BY gruppe, test_standard, datum"

        cursor = self.conn.execute(query, params)
        rows = cursor.fetchall()

        import csv

        fieldnames = [
            "Datum", "Alter", "Gruppe", "Test_Standard", "Test",
            "Wert_Norm", "Einheit_Norm", "Wert", "Einheit", "Normbereich", "Flag",
        ]
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(fieldnames)
            writer.writerows(rows)

    def query(self, sql: str, params: tuple = ()) -> list[tuple]:
        """Führt eine beliebige SQL-Abfrage aus."""
        cursor = self.conn.execute(sql, params)
        return cursor.fetchall()

    def stats(self) -> dict:
        """Gibt Statistiken zur Datenbank zurück."""
        patienten = self.conn.execute("SELECT COUNT(*) FROM patienten").fetchone()[0]
        befunde = self.conn.execute("SELECT COUNT(*) FROM befunde").fetchone()[0]
        laborwerte = self.conn.execute("SELECT COUNT(*) FROM laborwerte").fetchone()[0]
        gruppen = self.conn.execute(
            "SELECT gruppe, COUNT(*) FROM laborwerte GROUP BY gruppe ORDER BY gruppe"
        ).fetchall()
        datum_range = self.conn.execute(
            "SELECT MIN(datum), MAX(datum) FROM laborwerte"
        ).fetchone()

        return {
            "patienten": patienten,
            "befunde": befunde,
            "laborwerte": laborwerte,
            "gruppen": dict(gruppen),
            "zeitraum": {"von": datum_range[0], "bis": datum_range[1]} if datum_range[0] else None,
        }

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
