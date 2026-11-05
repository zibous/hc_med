import re
from pathlib import Path

class SimpleCSVParser:
    """Parser für das einfache, standardisierte CSV-Format (Numbers/Excel-Vorlage).
    
    Header-Struktur: Gruppe;Test;Wert;Einheit;Normbereich;Flag
    Das Datum wird zwingend aus dem Dateinamen (Format: YYYY-MM-DD) extrahiert.
    """

    def __init__(self):
        # Reguläre Ausdrücke vorkompilieren
        self.date_pattern = re.compile(r"(\d{4})-(\d{2})-(\d{2})")

    def _extract_file_date(self, filename: str) -> str | None:
        """Hilfsmethode: Extrahiert das ISO-Datum aus dem Dateinamen."""
        match = self.date_pattern.search(filename)
        if match:
            return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
        return None

    def parse(self, filepath: Path) -> list[dict]:
        """Liest die einfache CSV-Datei ein und liefert die Datensätze zurück."""
        results = []
        
        # Datum bestimmen – bricht sofort ab, wenn kein valides Datum im Dateinamen steckt
        file_date = self._extract_file_date(filepath.name)
        if not file_date:
            return results

        try:
            text = filepath.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
        except (IOError, OSError):
            return results

        # Format-Erkennung anhand des Headers
        header = lines[0].strip() if lines else ""
        is_kh_format = header.startswith("Test;Wert;")

        for line in lines:
            line = line.strip()
            
            # Header, Kommentare und Leerzeilen überspringen
            if not line or line.startswith("Gruppe;Test") or line.startswith("Test;Wert") or line.startswith("#"):
                continue

            parts = line.split(";")
            if len(parts) < 2:
                continue

            if is_kh_format:
                # Format: Test;Wert;Flag;Einheit;Normbereich
                test = parts[0].strip()
                wert = parts[1].strip() if len(parts) > 1 else ""
                flag = parts[2].strip() if len(parts) > 2 else ""
                einheit = parts[3].strip() if len(parts) > 3 else ""
                norm = parts[4].strip() if len(parts) > 4 else ""
                gruppe = ""
            else:
                # Format: Gruppe;Test;Wert;Einheit;Normbereich;Flag
                if len(parts) < 3:
                    continue
                gruppe = parts[0].strip()
                test = parts[1].strip()
                wert = parts[2].strip()
                einheit = parts[3].strip() if len(parts) > 3 else ""
                norm = parts[4].strip() if len(parts) > 4 else ""
                flag = parts[5].strip() if len(parts) > 5 else ""

            # Validierung: Ohne Wert oder Testname überspringen wir die Zeile
            if not wert or not test:
                continue

            results.append({
                "Datum": file_date,
                "Gruppe": gruppe,  # Wird direkt injiziert, assign_group skippt das später
                "Test": test,
                "Wert": wert.replace(",", "."),
                "Einheit": einheit,
                "Normbereich": norm,
                "Flag": flag,
            })

        return results
