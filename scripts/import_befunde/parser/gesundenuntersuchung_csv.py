import re
from pathlib import Path

class GesundUntersuchungCSVParser:
    """Parser für das Gesundheitsuntersuchung CSV-Format."""

    def _parse_date(self, year: str) -> str:
        """Hilfsmethode: Konvertiert Jahr in das Standardformat YYYY-MM-DD."""
        # Da nur das Jahr vorhanden ist, nehmen wir den 1. Januar des Jahres
        return f"{year}-01-01"

    def parse(self, filepath: Path) -> list[dict]:
        """Liest die Gesundheitsuntersuchung CSV-Datei ein und extrahiert die Laborergebnisse."""
        results = []

        try:
            text = filepath.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
        except (IOError, OSError):
            return results

        for line in lines:
            # Header-Zeile und Leerzeilen überspringen
            if line.startswith("Jahr;") or not line.strip():
                continue

            parts = line.split(";")
            if len(parts) < 6:
                continue

            # Daten extrahieren
            year = parts[0].strip()
            kuerzel = parts[1].strip()
            bezeichnung = parts[2].strip()
            wert = parts[4].strip()
            einheit = parts[5].strip()
            referenz = parts[6].strip() if len(parts) > 6 else ""

            # Datum über Hilfsmethode extrahieren
            date_str = self._parse_date(year)

            # Komma durch Punkt für spätere numerische Berechnungen ersetzen
            wert_normalized = wert.replace(",", ".") if wert else ""

            if wert_normalized:
                results.append({
                    "Datum": date_str,
                    "Test": f"{kuerzel} ({bezeichnung})",
                    "Wert": wert_normalized,
                    "Einheit": einheit,
                    "Normbereich": referenz,
                    "Flag": "",
                })

        return results