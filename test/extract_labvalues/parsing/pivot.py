import re
from pathlib import Path


def parse_pivot_format(filepath: Path) -> list[dict]:
    text = filepath.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    results = []

    header = lines[0].split(";")
    dates = []

    for h in header[3:]:
        dm = re.match(r"(\d{2})\.(\d{2})\.(\d{2,4})", h.strip())
        if dm:
            year = dm.group(3)
            if len(year) == 2:
                year = "20" + year
            dates.append(f"{year}-{dm.group(2)}-{dm.group(1)}")
        else:
            dates.append("")

    for line in lines[1:]:
        parts = line.split(";")
        if len(parts) < 4:
            continue

        test_name = parts[0].strip()
        unit = parts[1].strip()
        norm = parts[2].strip().replace(",", ".")

        # Fix: if unit is empty but norm looks like a unit (no digits), swap
        if not unit and norm and not any(ch.isdigit() for ch in norm):
            unit = norm
            norm = ""

        for idx, date_str in enumerate(dates):
            if not date_str:
                continue

            col = idx + 3
            if col >= len(parts):
                break

            value = parts[col].strip().replace(",", ".")
            if not re.match(r"[<>]?\d", value):
                continue

            results.append({
                "Datum": date_str,
                "Test": test_name,
                "Wert": value,
                "Einheit": unit,
                "Normbereich": norm,
                "Flag": "",
            })

    return results
