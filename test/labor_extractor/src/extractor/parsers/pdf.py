import re
from pathlib import Path


def parse_pdf_text_format(filepath: Path) -> list[dict]:
    """Parse das aus PDF extrahierte Format (2024-12-01, 2024-12-11).

    Zeilen wie:
      Leukozyten 13.7 10^9/l 4.20- 9.10 +
      CRP 5.28 mg/dl -0.49 +
      Kreatinin 0.89 mg/dl 0.70- 1.20
    """
    results = []
    text = filepath.read_text(encoding="utf-8", errors="replace")

    # Datum aus Dateinamen
    date_match = re.search(r"(\d{4})-(\d{2})-(\d{2})", filepath.name)
    if not date_match:
        return results
    file_date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"

    # Einheiten die in diesem Format vorkommen
    known_units = {
        "10^9/l", "10^12/l", "g/dl", "mg/dl", "mmol/l", "U/l", "fl", "pg",
        "%", "ml/min/kof", "sek", "ng/ml", "µg/l",
    }

    lines = text.splitlines()
    skip_lines = {"In", "ter", "pre", "ta", "ti", "on"}

    for line in lines:
        line = line.strip()

        # Mehrzeilige Header-Fragmente überspringen
        if line in skip_lines or not line:
            continue

        # Abschnitts-Header, Fußnoten, PDF-Metazeilen überspringen
        if line.startswith(("Hämatologie", "Blutbild", "Gerinnung", "Klinische Chemie",
                           "Proteindiagnostik", "Hämostaseologie", "Analyse", "PDF-",
                           "Patient:", "1)", "2)", "3)")):
            continue

        # Zeile mit Laborwert matchen
        # Pattern: Testname (ein oder mehr Wörter)  Wert  Einheit  [Referenz]  [Flag]
        # Strategie: Einheit in der Zeile finden und davon ausgehend parsen
        match = None
        for unit in known_units:
            # Einheit in der Zeile suchen (als ganzes Wort)
            unit_escaped = re.escape(unit)
            unit_match = re.search(rf"\s({unit_escaped})(?:\s|$)", line, re.IGNORECASE)
            if unit_match:
                # Alles vor der Einheit aufteilen: letzte "Zahl" ist der Wert, Rest ist Testname
                before_unit = line[: unit_match.start()].strip()
                after_unit = line[unit_match.end():].strip()

                # Wert ist das letzte Token vor der Einheit
                parts = before_unit.rsplit(None, 1)
                if len(parts) == 2:
                    test_name = parts[0].strip()
                    value = parts[1].strip()
                elif len(parts) == 1:
                    # Nur ein Token -> könnte Wert ohne Testname sein, skip
                    continue
                else:
                    continue

                # Prüfen ob Wert numerisch ist (oder mit < / > beginnt)
                if not re.match(r"[<>]?\d", value):
                    continue

                # Flag aus dem Ende extrahieren (+, -, *)
                flag = ""
                if after_unit and after_unit[-1] in ("+", "-", "*"):
                    flag = "H" if after_unit[-1] == "+" else ("L" if after_unit[-1] == "-" else "")
                    after_unit = after_unit[:-1].strip()

                # Referenzbereich: was nach der Einheit übrig ist
                # Format: "4.20- 9.10" oder "-0.49" oder ">80" oder "0.70- 1.20"
                norm = re.sub(r"\s*-\s*", "-", after_unit).strip()

                match = {
                    "Datum": file_date,
                    "Test": test_name,
                    "Wert": value.replace(",", "."),
                    "Einheit": unit,
                    "Normbereich": norm,
                    "Flag": flag,
                }
                break

        # Sonderfall: Werte ohne Einheit (z.B. INR 1.14, Quotient)
        if not match:
            m = re.match(r"^([\w\s.()\-/]+?)\s+(\d+[.,]?\d*)\s*$", line)
            if m:
                test_name = m.group(1).strip()
                value = m.group(2).replace(",", ".")
                # Nur wenn der Testname sinnvoll aussieht
                if len(test_name) > 2 and not test_name[0].isdigit():
                    match = {
                        "Datum": file_date,
                        "Test": test_name,
                        "Wert": value,
                        "Einheit": "",
                        "Normbereich": "",
                        "Flag": "",
                    }

        if match:
            results.append(match)

    return results
