import re
from pathlib import Path

class TableFormatParser:
    """Parser für das tabellarische, durch Whitespace getrennte Format.
    
    Header-Struktur: Test  Norm  Erst-Wert  Min-Wert  Max-Wert  Letzt-Wert  Einheit
    Wählt bevorzugt den aktuellsten Letzt-Wert, sonst den Erst-Wert als Fallback.
    """

    def __init__(self):
        # Reguläre Ausdrücke und Filter vorkompilieren
        self.date_pattern = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
        
        # Einheitsmuster für das letzte Feld der Tabellenzeile
        self.unit_pattern = re.compile(
            r"^(%|10\^[0-9]+/l|g/dl|mg/dl|mmol/l|U/l|fl|pg|ml/min/kof)$", 
            re.IGNORECASE
        )
        
        self.section_headers = ["Blutbild", "Klinische Chemie", "Gerinnung"]

    def _extract_file_date(self, filename: str) -> str | None:
        """Hilfsmethode: Extrahiert das ISO-Datum aus dem Dateinamen."""
        match = self.date_pattern.search(filename)
        if match:
            return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
        return None

    def _extract_unit_and_data(self, parts: list[str]) -> tuple[str, list[str]]:
        """Hilfsmethode: Prüft das Zeilenende auf eine Einheit und trennt die reinen Datenspalten."""
        data_parts = parts[2:]
        unit = ""
        
        if data_parts and self.unit_pattern.match(data_parts[-1]):
            unit = data_parts[-1]
            data_parts = data_parts[:-1]
            
        return unit, data_parts

    def _extract_best_value(self, data_parts: list[str]) -> str | None:
        """Hilfsmethode: Filtert numerische Werte und wählt Letzt-Wert vor Erst-Wert."""
        numeric_values = []
        for p in data_parts:
            try:
                # Komma für die Konvertierung ersetzen
                val_normalized = p.replace(",", ".")
                float(val_normalized)
                numeric_values.append(val_normalized)
            except ValueError:
                pass

        if not numeric_values:
            return None

        # Letzt-Wert (aktuellster am Ende) bevorzugen, sonst den einzigen Erst-Wert
        return numeric_values[-1] if len(numeric_values) > 1 else numeric_values[0]

    def parse(self, filepath: Path) -> list[dict]:
        """Liest das Tabellenformat ein und extrahiert die Ergebnisse."""
        results = []
        
        file_date = self._extract_file_date(filepath.name)
        if not file_date:
            return results

        try:
            text = filepath.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
        except (IOError, OSError):
            return results

        in_data = False

        for line in lines:
            line = line.strip()

            # Header-Zeile erkennen
            if line.startswith("Test") and "Norm" in line and "Einheit" in line:
                in_data = True
                continue

            # Medizinische Abschnitts-Überschriften überspringen
            if any(h in line for h in self.section_headers) and "Test" not in line:
                continue

            if not in_data or not line:
                continue

            # Zeile anhand von Whitespaces aufsplitten
            parts = line.split()
            if len(parts) < 3:
                continue

            test_name = parts[0]
            norm = parts[1] if len(parts) > 1 else ""

            # Einheit isolieren und Daten-Spalten bereinigen
            unit, data_parts = self._extract_unit_and_data(parts)

            # Den passenden Messwert ermitteln
            value = self._extract_best_value(data_parts)
            if not value:
                continue

            results.append({
                "Datum": file_date,
                "Test": test_name,
                "Wert": value,
                "Einheit": unit,
                "Normbereich": norm,
                "Flag": "",
            })

        return results
