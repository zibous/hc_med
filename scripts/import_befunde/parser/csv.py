import re
from pathlib import Path

class CSVFormatParser:
    """Parser für das semikolon-getrennte Laborformat.

    Erwartetes Format: Tag;Test;Norm;Erst-Wert;Min-Wert;Max-Wert;Letzt-Wert;Einheit
    """

    def _parse_date(self, raw_date: str) -> str:
        """Hilfsmethode: Konvertiert DD.MM.YYYY in das Standardformat YYYY-MM-DD."""
        cleaned_date = raw_date.strip()
        date_match = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", cleaned_date)
        if date_match:
            return f"{date_match.group(3)}-{date_match.group(2)}-{date_match.group(1)}"
        return cleaned_date

    def _extract_value_and_unit(self, parts: list[str]) -> tuple[str, str]:
        """Hilfsmethode: Bestimmt den gültigen Messwert und die dazugehörige Einheit."""
        # Erst-Wert oder Letzt-Wert holen
        erst_wert = parts[3].strip() if len(parts) > 3 else ""
        letzt_wert = parts[6].strip() if len(parts) > 6 else ""
        value = letzt_wert if letzt_wert else erst_wert

        # Komma durch Punkt für spätere numerische Berechnungen ersetzen
        value_normalized = value.replace(",", ".") if value else ""

        # Einheit bestimmen (entweder das letzte Element oder Index 7)
        last_part = parts[-1].strip()
        fallback_part = parts[7].strip() if len(parts) > 7 else ""
        unit = last_part if last_part else fallback_part

        return value_normalized, unit

    def _parse_gesundenuntersuchung_date(self, year: str) -> str:
        """Hilfsmethode: Konvertiert Jahr in das Standardformat YYYY-MM-DD."""
        # Da nur das Jahr vorhanden ist, nehmen wir den 1. Januar des Jahres
        return f"{year}-01-01"

    def parse(self, filepath: Path) -> list[dict]:
        """Liest die CSV-Datei ein und extrahiert die Laborergebnisse."""
        results = []

        try:
            text = filepath.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
        except (IOError, OSError):
            return results

        # Determine the format of the CSV file
        if lines and lines[0].startswith("Jahr;"):
            # Parse Gesundheitsuntersuchung format
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
                date_str = self._parse_gesundenuntersuchung_date(year)

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
        else:
            # Parse original format
            for line in lines:
                # Header-Zeile und Leerzeilen überspringen
                if line.startswith("Tag;") or not line.strip():
                    continue

                parts = line.split(";")
                if len(parts) < 5:
                    continue

                # Daten über Hilfsmethoden extrahieren
                date_str = self._parse_date(parts[0])
                test_name = parts[1].strip()
                norm = parts[2].strip() if len(parts) > 2 else ""
                value, unit = self._extract_value_and_unit(parts)

                if value:
                    results.append({
                        "Datum": date_str,
                        "Test": test_name,
                        "Wert": value,
                        "Einheit": unit,
                        "Normbereich": norm,
                        "Flag": "",
                    })

        return results