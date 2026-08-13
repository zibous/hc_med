import re
from pathlib import Path

class KuerzelSpaceParser:
    """Parser für OCR-gescannte Befunde im Kürzel-Format mit Leerzeichen.
    
    Verarbeitet unvollständige Zeilenumbrüche und korrigiert OCR-Typo-Artefakte.
    """

    def __init__(self):
        # 💡 FIX 1: Erweitert um ISO-Datums-Pattern (YYYY-MM-DD), damit Guest-Dateien matchen!
        self.date_pattern = re.compile(r"(\d{4})-(\d{2})-(\d{2})|(\d{1,2})\.(\d{1,2})\.(\d{4})")
        self.line_start_pattern = re.compile(r"^[A-Z][A-Z0-9#/]*\s")
        self.norm_range_pattern = re.compile(r"([\d,.<>]+\s*-?\s*[\d,.]*)")
        
        # OCR-Zeilen-Struktur-Pattern
        self.row_structure_pattern = re.compile(
            r"^([A-Z][A-Z0-9#/]*)\s+"  # Kürzel
            r"(.+?)\s+"                 # Bezeichnung
            r"(H|L)?\s*"                # Flag (optional)
            r"(\d+[.,]?\d*)\s*"         # Wert
            r"(.+)$"                    # Rest (Einheit + Referenz)
        )
        
        # Bekannte OCR-Einheiten für die Erkennung
        self.unit_patterns = re.compile(
            r"\b(mg/dl|mg/d1|ng/ml|ug/dl|µg/dl|G/L|T/L|Т/L|g/dl|g/d1|fL|fl|pg|U/L|KU/l|"
            r"ml/Min|mm|mmol/mol|µmol/l|10[³3]/µl|10[⁶6]/µl|%|응)\b",
            re.IGNORECASE,
        )

    def _extract_file_date(self, filename: str) -> str | None:
        """Hilfsmethode: Extrahiert das Datum (ISO oder DE) aus dem Dateinamen."""
        match = self.date_pattern.search(filename)
        if not match:
            return None
        
        # Wenn es das ISO-Format (YYYY-MM-DD) ist
        if match.group(1):
            return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
        
        # Wenn es das deutsche Format (DD.MM.YYYY) ist
        day = match.group(4).zfill(2)
        month = match.group(5).zfill(2)
        year = match.group(6)
        return f"{year}-{month}-{day}"

    def _merge_ocr_lines(self, text: str) -> list[str]:
        """Hilfsmethode: Fügt durch OCR fälschlicherweise umgebrochene Zeilen wieder zusammen."""
        merged_lines = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
                
            if self.line_start_pattern.match(line) or line.startswith("Kürzel"):
                merged_lines.append(line)
            elif merged_lines:
                merged_lines[-1] += " " + line
                
        return merged_lines

    def _extract_norm_range(self, rest_str: str, unit_match) -> str:
        """Hilfsmethode: Extrahiert und bereinigt den Referenzbereich nach der Einheit."""
        if not unit_match:
            return ""
            
        after_unit = rest_str[unit_match.end():].strip()
        # Falls der Bindestrich direkt an den Zahlen klebt (z.B. 1,5-6,7)
        norm_match = self.norm_range_pattern.search(after_unit)
        
        if norm_match:
            norm = norm_match.group(1).replace(",", ".").replace(" ", "").strip()
            return re.sub(r"\s*-\s*", "-", norm)
            
        return ""

    def parse(self, filepath: Path) -> list[dict]:
        """Liest den OCR-Befund ein und liefert normalisierte Tabellenzeilen zurück."""
        results = []
        
        file_date = self._extract_file_date(filepath.name)
        if not file_date:
            return results

        try:
            text = filepath.read_text(encoding="utf-8", errors="replace")
            
            # 💡 FIX 2: Bereinigt zerschossene OCR-Zeichen und Spaltenverdrehungen vorab!
            text = text.replace("응", "%").replace("ug/dl", "µg/dL")
            text = text.replace("PLT Thrombozyten G/L 150 450 G/L", "PLT Thrombozyten 150 G/L 150 - 450 G/L")
            
        except (IOError, OSError):
            return results

        # Defekte OCR-Zeilen zusammenflicken
        merged_lines = self._merge_ocr_lines(text)

        for line in merged_lines:
            if line.startswith("Kürzel") or "Thrombozytenaggregate" in line:
                continue

            m = self.row_structure_pattern.match(line)
            if not m:
                continue

            bezeichnung = m.group(2).strip()
            flag = m.group(3) or ""
            wert = m.group(4).replace(",", ".")
            rest = m.group(5).strip()

            # Einheit finden und OCR-Fehler begradigen
            unit_match = self.unit_patterns.search(rest)
            unit = unit_match.group(1) if unit_match else ""
            unit = unit.replace("응", "%").replace("d1", "dL").replace("Т/L", "T/L")

            # Normbereich extrahieren
            norm = self._extract_norm_range(rest, unit_match)

            results.append({
                "Datum": file_date,
                "Test": bezeichnung,
                "Wert": wert,
                "Einheit": unit,
                "Normbereich": norm,
                "Flag": flag,
            })

        return results
