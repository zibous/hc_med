import re
from pathlib import Path


def parse_kuerzel_space_format(filepath: Path) -> list[dict]:
    text = filepath.read_text(encoding="utf-8", errors="replace")
    results = []

    date_match = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", filepath.name)
    if date_match:
        file_date = f"{date_match.group(3)}-{date_match.group(2).zfill(2)}-{date_match.group(1).zfill(2)}"
    else:
        # Try ISO format: 2019-04-07
        date_match2 = re.search(r"(\d{4})-(\d{2})-(\d{2})", filepath.name)
        if date_match2:
            file_date = f"{date_match2.group(1)}-{date_match2.group(2)}-{date_match2.group(3)}"
        else:
            return results

    lines = text.splitlines()
    merged = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if re.match(r"^[A-Z][A-Z0-9#/]*\s", line):
            merged.append(line)
        elif merged:
            merged[-1] += " " + line

    for line in merged:
        m = re.match(
            r"^([A-Z][A-Z0-9#/]*)\s+(.+?)\s+(H|L)?\s*(\d+[.,]?\d*)\s+(.+)$",
            line
        )
        if not m:
            continue

        bezeichnung = m.group(2).strip()
        flag = m.group(3) or ""
        wert = m.group(4).replace(",", ".")
        rest = m.group(5)

        unit_match = re.search(r"\b(mg/dl|G/L|T/L|g/dl|fL|pg|U/L|%|mmol/l)\b", rest, re.IGNORECASE)
        unit = unit_match.group(1) if unit_match else ""

        norm = ""
        if unit_match:
            after = rest[unit_match.end():].strip()
            nm = re.search(r"([\d.,<>]+\s*-?\s*[\d.,]*)", after)
            if nm:
                norm = nm.group(1).replace(",", ".").strip()

        results.append({
            "Datum": file_date,
            "Test": bezeichnung,
            "Wert": wert,
            "Einheit": unit,
            "Normbereich": norm,
            "Flag": flag,
        })

    return results
