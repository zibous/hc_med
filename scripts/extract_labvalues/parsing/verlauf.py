import re
from pathlib import Path


def parse_verlauf_format(filepath: Path) -> list[dict]:
    """
    Parse 'Verlaufs-Tabelle' format:
      Test Norm Erst-Wert Min-Wert Max-Wert Letzt-Wert Einheit
      Leuko 4.20-9.10 13.7 11 13.7 13.3 10^9/l

    Uses Letzt-Wert as the current value. Falls back to Erst-Wert if fewer columns.
    Date is extracted from filename.
    """
    text = filepath.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    results = []

    # Date from filename
    date_str = ""
    dm = re.match(r"(\d{4})-(\d{2})-(\d{2})", filepath.stem)
    if dm:
        date_str = f"{dm.group(1)}-{dm.group(2)}-{dm.group(3)}"

    # Full pattern: Test Norm Erst Min Max Letzt Einheit
    full_pattern = re.compile(
        r'^(.+?)\s+'
        r'([<>]?[\d.]+(?:-[\d.]+)?)\s+'  # Norm
        r'([\d.]+)\s+'                     # Erst-Wert
        r'([\d.]+)\s+'                     # Min-Wert
        r'([\d.]+)\s+'                     # Max-Wert
        r'([\d.]+)\s+'                     # Letzt-Wert
        r'(\S+)$'                          # Einheit
    )

    # Partial: Test Norm Wert Einheit (only one value present)
    partial_pattern = re.compile(
        r'^(.+?)\s+'
        r'([<>]?[\d.]+(?:-[\d.]+)?)\s+'  # Norm
        r'([\d.]+)\s+'                     # single value
        r'(\S+)$'                          # Einheit
    )

    # No norm: Test Wert1 Wert2 ... Einheit (e.g. "INR 1.14 1.14 1.25 1.25")
    no_norm_pattern = re.compile(
        r'^([A-Za-zÄÖÜäöüß][\w.%-]*(?:\s+\w+)?)\s+'
        r'([\d.]+(?:\s+[\d.]+)*)\s+'
        r'(\S+)$'
    )

    skip_lines = {"blutbild", "klinische chemie", "gerinnung", "proteindiagnostik",
                  "hämatologie", "hämostaseologie"}

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.lower() in skip_lines:
            continue
        if line.lower().startswith("test ") and "norm" in line.lower():
            continue

        m = full_pattern.match(line)
        if m:
            results.append({
                "Datum": date_str,
                "Test": m.group(1).strip(),
                "Wert": m.group(6),  # Letzt-Wert
                "Einheit": m.group(7),
                "Normbereich": m.group(2),
                "Flag": "",
            })
            continue

        m = partial_pattern.match(line)
        if m:
            results.append({
                "Datum": date_str,
                "Test": m.group(1).strip(),
                "Wert": m.group(3),
                "Einheit": m.group(4),
                "Normbereich": m.group(2),
                "Flag": "",
            })
            continue

        m = no_norm_pattern.match(line)
        if m:
            values = m.group(2).split()
            # Last numeric value is the most recent
            wert = values[-1] if values else ""
            results.append({
                "Datum": date_str,
                "Test": m.group(1).strip(),
                "Wert": wert,
                "Einheit": m.group(3),
                "Normbereich": "",
                "Flag": "",
            })

    return results
