import re
from pathlib import Path

class FreeTextParser:
    """Parser für unstrukturierte Freitext-Laborberichte.
    
    Erkennt Zeilen über reguläre Ausdrücke und extrahiert Datum,
    Testnamen, Messwerte, Einheiten und Normbereiche.
    """

    def __init__(self):
        # Reguläre Ausdrücke einmalig beim Erstellen der Instanz kompilieren
        self.date_pattern = re.compile(r"Laborbefund vom (\d{2})\.(\d{2})\.(\d{4})")
        
        self.value_pattern = re.compile(
            r"^([A-Za-zÄÖÜäöüß()./\-\s]+?)\s+"  # Testname (nicht-gierig)
            r"([<>]?\d+[.,]?\d*)\s*"            # Wert (numerisch)
            r"(H|L|hämolyt\.)?\s*"              # Flag (optional)
            r"([A-Za-z%µ/^_°응]+(?:[/][A-Za-z²³]+)?\.?)\s*"  # Einheit (inkl. 응)
            r"([<>]?\s*\d+[.,]?\d*(?:\s*-\s*\d+[.,]?\d*)?)?$"  # Norm (optional)
        )
        
        self.gfr_pattern = re.compile(
            r"^GFR-CKD[\w\s/.]*?\s+(\d+)\s*(L|H)?\s*mL/min\s*([<>]?\d+)?$"
        )
        
        self.ptt_pattern = re.compile(
            r"^(Quick \(Prothrombinzeit\)|PTT Actin FS)\s+([<>]?\d+[.,]?\d*)\s*(H|L)?\s*(Sek\.|응|%)\s*([\d.\-\s]+)?$"
        )

    def _extract_fallback_date(self, filename: str) -> str | None:
        """Hilfsmethode: Extrahiert das Datum aus dem Dateinamen (DD.MM.YYYY oder YYYY-MM-DD)."""
        fname_date = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", filename)
        if fname_date:
            return f"{fname_date.group(3)}-{fname_date.group(2)}-{fname_date.group(1)}"
            
        fname_date_iso = re.search(r"(\d{4})-(\d{2})-(\d{2})", filename)
        if fname_date_iso:
            return f"{fname_date_iso.group(1)}-{fname_date_iso.group(2)}-{fname_date_iso.group(3)}"
            
        return None

    def _should_skip_line(self, line: str) -> bool:
        """Hilfsmethode: Filtert Trennlinien und bekannte Text-Artefakte."""
        if "--------" in line or not line:
            return True
        if line.startswith("Text ") or line.startswith("Lupus"):
            return True
        return False

    def parse(self, filepath: Path) -> list[dict]:
        """Liest das Freitext-File ein und extrahiert alle matchenden Laborzeilen."""
        results = []
        
        try:
            text = filepath.read_text(encoding="utf-8", errors="replace")
        except (IOError, OSError):
            return results

        # Initialer Datums-Fallback aus dem Dateinamen
        current_date = self._extract_fallback_date(filepath.name)

        for line in text.splitlines():
            line = line.strip()

            # 1. Datum im Text suchen (überschreibt ggf. den Dateinamen)
            dm = self.date_pattern.search(line)
            if dm:
                current_date = f"{dm.group(3)}-{dm.group(2)}-{dm.group(1)}"
                continue

            # 2. Ignorierbare Zeilen filtern
            if self._should_skip_line(line):
                continue

            # Ohne gültiges Datum können keine Werte zugewiesen werden
            if not current_date:
                continue

            # 3. Spezialfall: GFR-CKD Match
            gfr_m = self.gfr_pattern.match(line)
            if gfr_m:
                results.append({
                    "Datum": current_date,
                    "Test": "GFR-CKD",
                    "Wert": gfr_m.group(1),
                    "Einheit": "mL/min",
                    "Normbereich": gfr_m.group(3) or "",
                    "Flag": gfr_m.group(2) or "",
                })
                continue

            # 4. Spezialfall: PTT / Quick Match
            ptt_m = self.ptt_pattern.match(line)
            if ptt_m:
                unit = ptt_m.group(4)
                if unit == "응":
                    unit = "%"
                results.append({
                    "Datum": current_date,
                    "Test": ptt_m.group(1),
                    "Wert": ptt_m.group(2).replace(",", "."),
                    "Einheit": unit,
                    "Normbereich": (ptt_m.group(5) or "").strip(),
                    "Flag": ptt_m.group(3) or "",
                })
                continue

            # 5. Standard-Laborzeile matchen
            m = self.value_pattern.match(line)
            if m:
                test_name = m.group(1).strip()
                value = m.group(2).replace(",", ".")
                flag = m.group(3) or ""
                unit = m.group(4)
                norm = (m.group(5) or "").strip()

                if test_name and value:
                    results.append({
                        "Datum": current_date,
                        "Test": test_name,
                        "Wert": value,
                        "Einheit": unit,
                        "Normbereich": norm,
                        "Flag": flag,
                    })

        return results
