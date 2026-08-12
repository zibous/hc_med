import re
from pathlib import Path


def parse_pdf_text_format(filepath: Path) -> list[dict]:
    text = filepath.read_text(encoding="utf-8", errors="replace")
    results = []

    dm = re.search(r"(\d{4})-(\d{2})-(\d{2})", filepath.name)
    if not dm:
        return results

    file_date = f"{dm.group(1)}-{dm.group(2)}-{dm.group(3)}"

    known_units = {
        "10^9/l", "10^12/l", "g/dl", "mg/dl", "mmol/l", "U/l", "fl", "pg", "%"
    }

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        for unit in known_units:
            um = re.search(rf"\s({re.escape(unit)})\s", line, re.IGNORECASE)
            if um:
                before = line[:um.start()].strip()
                after = line[um.end():].strip()

                parts = before.rsplit(None, 1)
                if len(parts) != 2:
                    continue

                test_name, value = parts
                if not re.match(r"[<>]?\d", value):
                    continue

                flag = ""
                if after.endswith("+"):
                    flag = "H"
                elif after.endswith("-"):
                    flag = "L"

                norm = after.rstrip("+-").strip().replace(" ", "").replace(",", ".")

                results.append({
                    "Datum": file_date,
                    "Test": test_name,
                    "Wert": value.replace(",", "."),
                    "Einheit": unit,
                    "Normbereich": norm,
                    "Flag": flag,
                })
                break

    return results
