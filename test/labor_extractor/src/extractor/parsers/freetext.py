import re
from pathlib import Path


def parse_freetext_file(filepath: Path) -> list[dict]:
    """Parse das Freitext-Format (2018, 2024-02-08).

    Erkennt Zeilen wie:
      Natrium          140     mmol/L   136-145
      CRP              4.69 H  mg/dL    < 0.50
      Leukocyten       8.5     G/L      3.7-10.0
    """
    results = []
    text = filepath.read_text(encoding="utf-8", errors="replace")

    # Datum aus dem Header extrahieren: "Laborbefund vom DD.MM.YYYY HH:MM"
    date_pattern = re.compile(r"Laborbefund vom (\d{2})\.(\d{2})\.(\d{4})")

    # Zeilen mit Laborwerten matchen:
    # Testname  [opt.Zusatz]  Wert  [opt.Flag H/L]  Einheit  Normbereich
    # Robusteres Pattern: alles vor dem numerischen Wert ist Testname
    value_pattern = re.compile(
        r"^([A-Za-zÄÖÜäöüß()./\-\s]+?)\s+"  # Testname (nicht-gierig)
        r"([<>]?\d+[.,]?\d*)\s*"  # Wert (numerisch, evtl. mit < oder >)
        r"(H|L|hämolyt\.)?\s*"  # Flag (optional)
        r"([A-Za-z%µ/^_°응]+(?:[/][A-Za-z²³]+)?\.?)\s*"  # Einheit (inkl. 응, Punkt am Ende)
        r"([<>]?\s*\d+[.,]?\d*(?:\s*-\s*\d+[.,]?\d*)?)?$"  # Norm (optional)
    )

    # Spezielles Pattern für GFR-CKD (Testname enthält Zahlen und /)
    gfr_pattern = re.compile(
        r"^GFR-CKD[\w\s/.]*?\s+(\d+)\s*(L|H)?\s*mL/min\s*([<>]?\d+)?$"
    )

    # Pattern für PTT/Quick mit Sek. oder 응
    ptt_pattern = re.compile(
        r"^(Quick \(Prothrombinzeit\)|PTT Actin FS)\s+([<>]?\d+[.,]?\d*)\s*(H|L)?\s*(Sek\.|응|%)\s*([\d.\-\s]+)?$"
    )

    current_date = None

    # Fallback: Datum aus Dateinamen extrahieren
    fname_date = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", filepath.name)
    if not fname_date:
        # Auch DD.MM.YYYY im Dateinamen
        fname_date = re.search(r"(\d{4})-(\d{2})-(\d{2})", filepath.name)
        if fname_date:
            current_date = f"{fname_date.group(1)}-{fname_date.group(2)}-{fname_date.group(3)}"
    else:
        current_date = f"{fname_date.group(3)}-{fname_date.group(2)}-{fname_date.group(1)}"

    for line in text.splitlines():
        line = line.strip()

        # Datum suchen
        dm = date_pattern.search(line)
        if dm:
            day, month, year = dm.group(1), dm.group(2), dm.group(3)
            current_date = f"{year}-{month}-{day}"
            continue

        # Abschnitts-Header überspringen
        if "--------" in line or not line:
            continue
        if line.startswith("Text ") or line.startswith("Lupus"):
            continue

        # Wert-Zeile matchen
        # Erst spezielle Patterns probieren
        gfr_m = gfr_pattern.match(line)
        if gfr_m and current_date:
            results.append({
                "Datum": current_date,
                "Test": "GFR-CKD",
                "Wert": gfr_m.group(1),
                "Einheit": "mL/min",
                "Normbereich": gfr_m.group(3) or "",
                "Flag": gfr_m.group(2) or "",
            })
            continue

        ptt_m = ptt_pattern.match(line)
        if ptt_m and current_date:
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

        m = value_pattern.match(line)
        if m and current_date:
            test_name = m.group(1).strip()
            value = m.group(2).replace(",", ".")
            flag = m.group(3) or ""
            unit = m.group(4)
            norm = (m.group(5) or "").strip()

            # Texteinträge wie "neg", "pos" ausfiltern (kein numerischer Wert)
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
