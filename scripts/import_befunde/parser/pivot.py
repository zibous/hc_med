import re
from pathlib import Path

class PivotFormatParser:
    """Parser für Kreuztabellen / Pivot-Formate.
    
    Header enthält die Datumsangaben ab Spalte 4 (Index 3).
    Zeilen enthalten die Teststrukturen. Transformiert Spaltenwerte in flache Zeilen.
    """

    def __init__(self):
        # Reguläre Ausdrücke vorkompilieren
        self.date_pattern = re.compile(r"(\d{2})\.(\d{2})\.(\d{2,4})")
        self.bracket_cleanup_pattern = re.compile(r"\s*\([^)]+\)\s*$")
        self.range_cleanup_pattern = re.compile(r"\s*-\s*")
        self.numeric_start_pattern = re.compile(r"[<>]?\d")

    def _parse_headers(self, header_line: str) -> list[str]:
        """Hilfsmethode: Extrahiert alle Datumsspalten ab Index 3 und konvertiert sie zu YYYY-MM-DD."""
        header_parts = header_line.split(";")
        dates: list[str] = []
        
        for h in header_parts[3:]:
            h = h.strip()
            if not h:
                dates.append("")
                continue
                
            dm = self.date_pattern.match(h)
            if dm:
                day, month, year = dm.group(1), dm.group(2), dm.group(3)
                # 2-stellige Jahreszahlen ins 21. Jahrhundert holen
                if len(year) == 2:
                    year = "20" + year if int(year) < 50 else "19" + year
                dates.append(f"{year}-{month}-{day}")
            else:
                dates.append("")
                
        return dates

    def _clean_test_metadata(self, parts: list[str]) -> tuple[str, str, str]:
        """Hilfsmethode: Bereinigt Testnamen, korrigiert Einheiten-Rutscher und säubert die Norm."""
        test_name = parts[0].strip()
        # Klammer-Kürzel entfernen: "Leukozyten (WBC)" -> "Leukozyten"
        clean_name = self.bracket_cleanup_pattern.sub("", test_name).strip()
        
        unit = parts[1].strip() if len(parts) > 1 else ""
        norm_raw = parts[2].strip() if len(parts) > 2 else ""

        # Korrektur: Wenn Einheit leer und Norm wie eine Einheit aussieht (enthält / aber keine Zahlen)
        if not unit and norm_raw and "/" in norm_raw and not any(c.isdigit() for c in norm_raw):
            unit = norm_raw
            norm_raw = ""

        # Referenz bereinigen: Einheit am Ende entfernen, Komma -> Punkt
        norm = norm_raw
        if unit and norm.lower().endswith(unit.lower()):
            norm = norm[:-len(unit)].strip()
        if unit and norm.endswith("%"):
            norm = norm[:-1].strip()
            
        norm = norm.replace(",", ".").strip()
        norm = self.range_cleanup_pattern.sub("-", norm)
        
        return clean_name, unit, norm

    def parse(self, filepath: Path) -> list[dict]:
        """Liest das Pivot-Format ein und bricht die Zeit-Spalten in einzelne Datensätze auf."""
        results = []
        
        try:
            text = filepath.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
        except (IOError, OSError):
            return results

        if not lines:
            return results

        # 1. Header-Zeile parsen, um die Zeitachse (Datumsliste) zu bekommen
        dates = self._parse_headers(lines[0])

        # 2. Daten-Zeilen parsen
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue

            parts = line.split(";")
            if len(parts) < 4:
                continue

            # Metadaten reinigen
            clean_name, unit, norm = self._clean_test_metadata(parts)
            if not clean_name:
                continue

            # 3. Werte pro Datum aus den Spalten extrahieren (Matrix auflösen)
            for idx, date_str in enumerate(dates):
                if not date_str:
                    continue
                    
                col_idx = idx + 3
                if col_idx >= len(parts):
                    break

                value = parts[col_idx].strip().replace(",", ".")
                if not value:
                    continue

                # Nicht-numerische OCR-Artefakte / Texte überspringen
                if not self.numeric_start_pattern.match(value):
                    continue

                results.append({
                    "Datum": date_str,
                    "Test": clean_name,
                    "Wert": value,
                    "Einheit": unit,
                    "Normbereich": norm,
                    "Flag": "",
                })

        return results
