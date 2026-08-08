import re
from pathlib import Path


def parse_kuerzel_space_format(filepath: Path) -> list[dict]:
    """Parse OCR-gescannte Befunde im Kürzel-Format mit Leerzeichen.

    Zeilen wie:
      KREA Kreatinin 1,01 mg/dl 0,70- 1,20 mg/dl
      WBC Leukozyten H 13,4 G/L 4,0 - 11,0 G/L
    """
    results = []
    text = filepath.read_text(encoding="utf-8", errors="replace")

    # Datum aus Dateinamen: "Peter 07.04.2019 Laborwerte.txt" oder "Peter 10.7.2019"
    date_match = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", filepath.name)
    if not date_match:
        return results
    day = date_match.group(1).zfill(2)
    month = date_match.group(2).zfill(2)
    year = date_match.group(3)
    file_date = f"{year}-{month}-{day}"

    # Mehrzeilige Einträge zusammenführen (OCR bricht manchmal Zeilen)
    lines = text.splitlines()
    merged_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Zeilen die mit Kürzel beginnen (Großbuchstaben, evtl. mit # oder Zahl)
        if re.match(r"^[A-Z][A-Z0-9#/]*\s", line) or line.startswith("Kürzel"):
            merged_lines.append(line)
        elif merged_lines:
            # Fortsetzungszeile an letzte anhängen
            merged_lines[-1] += " " + line

    # Bekannte Einheiten für die Erkennung
    unit_patterns = re.compile(
        r"\b(mg/dl|mg/d1|ng/ml|ug/dl|µg/dl|G/L|T/L|Т/L|g/dl|g/d1|fL|fl|pg|U/L|KU/l|"
        r"ml/Min|mm|mmol/mol|µmol/l|10[³3]/µl|10[⁶6]/µl|%|응)\b",
        re.IGNORECASE,
    )

    for line in merged_lines:
        if line.startswith("Kürzel") or "Thrombozytenaggregate" in line:
            continue

        # Pattern: KÜRZEL Bezeichnung [H|L] Wert Einheit [Referenz]
        m = re.match(
            r"^([A-Z][A-Z0-9#/]*)\s+"  # Kürzel
            r"(.+?)\s+"  # Bezeichnung
            r"(H|L)?\s*"  # Flag (optional)
            r"(\d+[.,]?\d*)\s*"  # Wert
            r"(.+)$",  # Rest (Einheit + Referenz)
            line,
        )
        if not m:
            continue

        bezeichnung = m.group(2).strip()
        flag = m.group(3) or ""
        wert = m.group(4).replace(",", ".")
        rest = m.group(5).strip()

        # Einheit aus Rest extrahieren (erste Einheit die wir finden)
        unit_match = unit_patterns.search(rest)
        unit = unit_match.group(1) if unit_match else ""

        # OCR-Korrekturen
        unit = unit.replace("응", "%").replace("d1", "dL").replace("Т/L", "T/L")

        # Referenzbereich: alles nach der Einheit bis zur nächsten Einheit
        norm = ""
        if unit_match:
            after_unit = rest[unit_match.end():].strip()
            # Referenz extrahieren: "0,70- 1,20 mg/dl" oder "0,1 - 0,6 mg/dl"
            norm_match = re.search(r"([\d,.<>]+\s*-?\s*[\d,.]*)", after_unit)
            if norm_match:
                norm = norm_match.group(1).replace(",", ".").strip()
                norm = re.sub(r"\s*-\s*", "-", norm)

        results.append({
            "Datum": file_date,
            "Test": bezeichnung,
            "Wert": wert,
            "Einheit": unit,
            "Normbereich": norm,
            "Flag": flag,
        })

    return results
