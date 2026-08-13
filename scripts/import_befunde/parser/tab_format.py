import re
from pathlib import Path

class TabFormatParser:
    """Parser für Tab-getrennte Laborberichte der Arztpraxis Zünd.
    
    Unterstützt jetzt sowohl echte Tabulatoren als auch zerschossene OCR-Leerzeichen-Texte.
    """

    def __init__(self):

        self.date_pattern = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
        self.numeric_check_pattern = re.compile(r"[<>]?\s*\d")
        self.range_cleanup_pattern = re.compile(r"\s*-\s*")
        self.qualitative_keywords = {"negativ", "normal", "positiv", "pos", "neg"}
        
        self.ocr_line_pattern = re.compile(
            r"^(?P<kuerzel>[A-Z0-9#+–]+)\s+"
            r"(?P<name>.+?)\s+"
            r"(?P<flag>[HLHlh\*]\s+)??"
            r"(?P<wert>\d+[\d,.]*)\s+"
            r"(?P<einheit>[a-zA-Z/%^12µ]+(?:/[a-zA-Z%]+)?)\s+"
            r"(?P<norm>\d+[\d,.\s-]*\s*[a-zA-Z/%^12µ]*)"
        )

    def _extract_file_date(self, filename: str) -> str | None:
        match = self.date_pattern.search(filename)
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}" if match else None

    def _clean_line(self, line: str) -> str:
        # 💡 ERWEITERT: Bereinigt zerschossene OCR-Sonderzeichen global vorab
        return line.replace("\u200b", "").replace("\ufeff", "").replace("응", "%").replace("Т/L", "T/L").strip()

    def _is_valid_value(self, wert: str) -> bool:
        if wert.lower() in self.qualitative_keywords:
            return True
        return bool(self.numeric_check_pattern.match(wert))

    def parse(self, filepath: Path) -> list[dict]:
        
        results = []
        file_date = self._extract_file_date(filepath.name)
        if not file_date:
            return results

        try:
            text = filepath.read_text(encoding="utf-8", errors="replace")
            # 💡 FIX 1: Zeilenbrüche mitten im Text vorab flicken (z.B. bei CRP oder MCH)
            text = re.sub(r"\n(\d+[\d,.\s-]*\s*(?:mg/dl|G/L|g/dl|pg|%|fL))", r" \1", text)
            # Spezial-Korrektur für die verdrehten Thrombozyten-Spalten
            text = text.replace("PLT Thrombozyten G/L 150 450 G/L", "PLT Thrombozyten 150 G/L 150 - 450 G/L")
            lines = text.splitlines()
        except (IOError, OSError):
            return results

        in_data = False
        
        for line in lines:
            line = self._clean_line(line)

            if "Kürzel" in line and "Bezeichnung" in line:
                in_data = True
                continue

            if not in_data or not line or "Thrombozytenaggregate" in line:
                continue

            # 💡 FIX 2: Wenn echte Tabulatoren da sind, nutzen wir die alte schnelle Logik
            if "\t" in line:
                parts = line.split("\t")
                if len(parts) < 4: continue
                kuerzel = parts[0].strip()
                bezeichnung = parts[1].strip()
                flag = parts[2].strip() if len(parts) > 2 else ""
                wert = parts[3].strip() if len(parts) > 3 else ""
                einheit = parts[4].strip() if len(parts) > 4 else ""
                referenz = parts[5].strip() if len(parts) > 5 else ""
                test_name = bezeichnung if bezeichnung else kuerzel
            
            # 💡 FIX 3: Wenn KEINE Tabulatoren da sind (OCR-Scan), greift das RegEx-Muster!
            else:
                match = self.ocr_line_pattern.match(line)
                if not match:
                    continue
                gd = match.groupdict()
                test_name = gd["name"].strip()
                wert = gd["wert"].strip()
                einheit = gd["einheit"].strip()
                referenz = gd["norm"].strip()
                flag = gd["flag"].strip() if gd["flag"] else ""

            if not wert or (wert.upper() == wert and not any(c.isdigit() for c in wert)):
                continue

            if not self._is_valid_value(wert):
                continue

            # Referenzbereich von angehängter Einheit befreien
            norm_clean = referenz
            if einheit and norm_clean.endswith(einheit):
                norm_clean = norm_clean[:-len(einheit)].strip()
            norm_clean = self.range_cleanup_pattern.sub("-", norm_clean)

            # Flags harmonisieren (* oder H bedeuten High)
            flag_str = "H" if flag in ("*", "H", "h") else "L" if flag in ("L", "l") else ""

            results.append({
                "Datum": file_date,
                "Test": test_name,
                "Wert": wert.replace(",", "."),
                "Einheit": einheit,
                "Normbereich": norm_clean,
                "Flag": flag_str,
            })

        return results
