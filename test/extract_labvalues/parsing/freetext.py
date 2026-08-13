import re
from pathlib import Path


def parse_freetext_file(filepath: Path) -> list[dict]:
    text = filepath.read_text(encoding="utf-8", errors="replace")
    results = []

    date_pattern = re.compile(r"Laborbefund vom (\d{2})\.(\d{2})\.(\d{4})")

    # Flexible value pattern:
    # TestName  Wert [Flag] Einheit [Normbereich] [Flag]
    value_pattern = re.compile(
        r"^([A-Za-zÄÖÜäöüß()./\-\s0-9]+?)\s+"    # Test name (allows digits for "BSG nach 2 h")
        r"([<>]?\d+[.,]?\d*)\s*"                    # Value
        r"(H|L|hämolyt\.)?\s*"                      # Flag (optional, before unit)
        r"([A-Za-z%µ/^_°0-9응]+(?:[/][A-Za-z²³0-9µ]+)*\.?)\s*"  # Unit (allows digits for 10^9/l)
        r"([-<>]?\s*\d+[.,]?\d*(?:\s*-\s*\d+[.,]?\d*)?)?\s*"    # Normbereich (optional, allows leading -)
        r"([+\-HL])?$"                              # Flag at end (optional)
    )

    # Fallback: date from filename (e.g. 2024-12-01_laborbefund_...)
    file_date = None
    dm_file = re.match(r"(\d{4})-(\d{2})-(\d{2})", filepath.stem)
    if dm_file:
        file_date = f"{dm_file.group(1)}-{dm_file.group(2)}-{dm_file.group(3)}"

    current_date = None

    for line in text.splitlines():
        line = line.strip()

        # Skip known non-data lines
        if not line or line.startswith("#") or line.startswith("PDF-Erstellung"):
            continue
        if re.match(r"^(Analyse|Patient:|Hämatologie|Klinische Chemie|Gerinnung|Proteindiagnostik)", line):
            continue
        if re.match(r"^(Blutbild|Hämostaseologie|Hämostaseologie Globaltests|ter|pre|ta|ti|on)\s*$", line):
            continue
        if re.match(r"^\d+\)", line):  # footnotes like "1) falsche Abnahme"
            continue

        dm = date_pattern.search(line)
        if dm:
            current_date = f"{dm.group(3)}-{dm.group(2)}-{dm.group(1)}"
            continue

        # Use file date as fallback if no "Laborbefund vom" found
        effective_date = current_date or file_date

        m = value_pattern.match(line)
        if m and effective_date:
            flag = m.group(3) or m.group(6) or ""
            # Normalize flag
            if flag == "+":
                flag = "H"
            elif flag == "-":
                flag = "L"
            results.append({
                "Datum": effective_date,
                "Test": m.group(1).strip(),
                "Wert": m.group(2).replace(",", "."),
                "Einheit": m.group(4),
                "Normbereich": (m.group(5) or "").strip(),
                "Flag": flag,
            })

    return results
