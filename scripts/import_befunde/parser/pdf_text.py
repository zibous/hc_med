import re
from pathlib import Path

class PDFTextFormatParser:
    """Parser für aus PDFs extrahierte Textstrukturen.
    
    Nutzt bekannte Maßeinheiten als Parsing-Anker, um davor liegende 
    Messwerte und danach folgende PDF-Spezifische Flags (+/-) zu trennen.
    """

    def __init__(self):
        # Reguläre Ausdrücke und Tabellen-Filter vorkompilieren
        self.date_pattern = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
        self.value_start_pattern = re.compile(r"[<>]?\d")
        self.no_unit_pattern = re.compile(r"^([\w\s.()\-/]+?)\s+(\d+[.,]?\d*)\s*$")
        self.range_cleanup_pattern = re.compile(r"\s*-\s*")
        
        self.skip_lines = {"In", "ter", "pre", "ta", "ti", "on"}
        self.header_prefixes = (
            "Hämatologie", "Blutbild", "Gerinnung", "Klinische Chemie",
            "Proteindiagnostik", "Hämostaseologie", "Analyse", "PDF-",
            "Patient:", "1)", "2)", "3)"
        )
        
        # Einheiten-Set für die Anker-Suche
        self.known_units = {
            "10^9/l", "10^12/l", "g/dl", "mg/dl", "mmol/l", "U/l", "fl", "pg",
            "%", "ml/min/kof", "sek", "ng/ml", "µg/l",
        }

    def _extract_file_date(self, filename: str) -> str | None:
        """Hilfsmethode: Holt das ISO-Datum (YYYY-MM-DD) aus dem Dateinamen."""
        match = self.date_pattern.search(filename)
        if match:
            return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
        return None

    def _should_skip_line(self, line: str) -> bool:
        """Hilfsmethode: Sortiert PDF-Metadaten und Tabellenkopfzeilen aus."""
        if not line or line in self.skip_lines:
            return True
        if line.startswith(self.header_prefixes):
            return True
        return False

    def _parse_with_unit_anchor(self, line: str, file_date: str) -> dict | None:
        """Hilfsmethode: Sucht nach einer bekannten Einheit und schneidet die Zeile auseinander."""
        for unit in self.known_units:
            unit_escaped = re.escape(unit)
            # Einheit als separates Wort in der Zeile suchen
            unit_match = re.search(rf"\s({unit_escaped})(?:\s|$)", line, re.IGNORECASE)
            
            if not unit_match:
                continue

            before_unit = line[:unit_match.start()].strip()
            after_unit = line[unit_match.end():].strip()

            # Wert ist das letzte Element direkt vor der Maßeinheit
            parts = before_unit.rsplit(None, 1)
            if len(parts) != 2:
                continue
                
            test_name, value = parts[0].strip(), parts[1].strip()

            # Validierung: Beginnt der Wert numerisch (oder mit Operator)?
            if not self.value_start_pattern.match(value):
                continue

            # PDF-Flag am Ende extrahieren (+ / - / *)
            flag = ""
            if after_unit and after_unit[-1] in ("+", "-", "*"):
                flag = "H" if after_unit[-1] == "+" else ("L" if after_unit[-1] == "-" else "")
                after_unit = after_unit[:-1].strip()

            # Referenzbereich säubern ("4.20- 9.10" -> "4.20-9.10")
            norm = self.range_cleanup_pattern.sub("-", after_unit).strip()

            return {
                "Datum": file_date,
                "Test": test_name,
                "Wert": value.replace(",", "."),
                "Einheit": unit,
                "Normbereich": norm,
                "Flag": flag,
            }
        return None

    def _parse_without_unit(self, line: str, file_date: str) -> dict | None:
        """Hilfsmethode: Spezialfall für Werte ohne Einheit (z.B. INR oder Quotienten)."""
        m = self.no_unit_pattern.match(line)
        if m:
            test_name = m.group(1).strip()
            value = m.group(2).replace(",", ".")
            
            # Syntaktische Plausibilitätsprüfung des Testnamens
            if len(test_name) > 2 and not test_name[0].isdigit():
                return {
                    "Datum": file_date,
                    "Test": test_name,
                    "Wert": value,
                    "Einheit": "",
                    "Normbereich": "",
                    "Flag": "",
                }
        return None

    def parse(self, filepath: Path) -> list[dict]:
        """Liest den PDF-Textextrakt ein und liefert die bereinigten Datensätze."""
        results = []
        
        file_date = self._extract_file_date(filepath.name)
        if not file_date:
            return results

        try:
            text = filepath.read_text(encoding="utf-8", errors="replace")
        except (IOError, OSError):
            return results

        for line in text.splitlines():
            line = line.strip()

            if self._should_skip_line(line):
                continue

            # Strategie 1: Parsing über Einheiten-Anker versuchen
            match = self._parse_with_unit_anchor(line, file_date)
            
            # Strategie 2: Falls kein Match, nach einheitslosen Messwerten suchen
            if not match:
                match = self._parse_without_unit(line, file_date)

            if match:
                results.append(match)

        return results
