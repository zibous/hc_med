import re
from pathlib import Path


def parse_pivot_format(filepath: Path) -> list[dict]:
    """Parse das Pivot-Tabellen-Format (laborwerte_2013-2029).

    Header: Parameter;Einheit;Referenz;18.10.13;12.12.13;24.10.14;...
    Zeilen: Testname;Einheit;Normbereich;Wert1;Wert2;Wert3;...

    Jede Spalte ab Position 3 ist ein Datum mit zugehörigem Wert.
    """
    results = []
    text = filepath.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    if not lines:
        return results

    # Header-Zeile parsen: Datumsspalten ab Index 3
    header_parts = lines[0].split(";")
    dates: list[str] = []
    for i, h in enumerate(header_parts[3:], start=3):
        h = h.strip()
        if not h:
            dates.append("")
            continue
        # Datum parsen: DD.MM.YY oder DD.MM.YYYY
        dm = re.match(r"(\d{2})\.(\d{2})\.(\d{2,4})", h)
        if dm:
            day, month, year = dm.group(1), dm.group(2), dm.group(3)
            if len(year) == 2:
                year = "20" + year if int(year) < 50 else "19" + year
            dates.append(f"{year}-{month}-{day}")
        else:
            dates.append("")

    # Daten-Zeilen parsen
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue

        parts = line.split(";")
        if len(parts) < 4:
            continue

        test_name = parts[0].strip()
        # Klammer-Kürzel entfernen: "Leukozyten (WBC)" -> "Leukozyten"
        clean_name = re.sub(r"\s*\([^)]+\)\s*$", "", test_name).strip()
        if not clean_name:
            continue

        unit = parts[1].strip() if len(parts) > 1 else ""
        norm_raw = parts[2].strip() if len(parts) > 2 else ""

        # Korrektur: Wenn Einheit leer und Norm wie eine Einheit aussieht (enthält /)
        if not unit and norm_raw and "/" in norm_raw and not any(c.isdigit() for c in norm_raw):
            unit = norm_raw
            norm_raw = ""

        # Referenz bereinigen: Einheit am Ende entfernen, Komma->Punkt
        norm = norm_raw
        # Einheit aus Norm entfernen (z.B. "0,70 - 1,20 mg/dl" -> "0.70-1.20")
        if unit and norm.lower().endswith(unit.lower()):
            norm = norm[:-len(unit)].strip()
        if unit and norm.endswith("%"):
            norm = norm[:-1].strip()
        norm = norm.replace(",", ".").strip()
        norm = re.sub(r"\s*-\s*", "-", norm)

        # Werte pro Datum
        for idx, date_str in enumerate(dates):
            if not date_str:
                continue
            col_idx = idx + 3
            if col_idx >= len(parts):
                break

            value = parts[col_idx].strip().replace(",", ".")
            if not value:
                continue

            # Nicht-numerische Werte überspringen (z.B. "Thrombozytenaggregate vorhanden")
            if not re.match(r"[<>]?\d", value):
                continue

            results.append({
                "Datum": date_str,
                "Test": clean_name,
                "Wert": value,
                "Einheit": unit,
                "Normbereich": norm,
                "Flag": "",
            })

    return results


def parse_table_format(filepath: Path) -> list[dict]:
    """Parse das Tabellenformat (2024-12-06).

    Header: Test  Norm  Erst-Wert  Min-Wert  Max-Wert  Letzt-Wert  Einheit
    Wir nehmen den Letzt-Wert (aktuellster), oder Erst-Wert als Fallback.
    """
    results = []
    text = filepath.read_text(encoding="utf-8", errors="replace")

    # Datum aus Dateinamen extrahieren
    date_match = re.search(r"(\d{4})-(\d{2})-(\d{2})", filepath.name)
    if not date_match:
        return results
    file_date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"

    # Zeilen mit Tabellenwerten matchen
    # Format: Testname  Norm  Erst-Wert  [Min]  [Max]  [Letzt]  Einheit
    lines = text.splitlines()
    in_data = False

    for line in lines:
        line = line.strip()

        # Header-Zeile erkennen
        if line.startswith("Test") and "Norm" in line and "Einheit" in line:
            in_data = True
            continue

        # Abschnitts-Header
        if any(h in line for h in ["Blutbild", "Klinische Chemie", "Gerinnung"]) and "Test" not in line:
            continue

        if not in_data or not line:
            continue

        # Tabellen-Zeile parsen (durch Whitespace getrennt)
        parts = line.split()
        if len(parts) < 3:
            continue

        test_name = parts[0]
        # Norm ist das zweite Feld
        norm = parts[1] if len(parts) > 1 else ""

        # Einheit ist das letzte Feld (wenn es typische Einheitsmuster hat)
        unit_pattern = re.compile(r"^(%|10\^[0-9]+/l|g/dl|mg/dl|mmol/l|U/l|fl|pg|ml/min/kof)$", re.IGNORECASE)
        unit = ""
        data_parts = parts[2:]

        if data_parts and unit_pattern.match(data_parts[-1]):
            unit = data_parts[-1]
            data_parts = data_parts[:-1]

        # Werte: Erst-Wert ist der erste numerische Wert nach Norm
        # Letzt-Wert ist der letzte
        numeric_values = []
        for p in data_parts:
            try:
                float(p.replace(",", "."))
                numeric_values.append(p.replace(",", "."))
            except ValueError:
                pass

        if not numeric_values:
            continue

        # Letzt-Wert bevorzugen, sonst Erst-Wert
        value = numeric_values[-1] if len(numeric_values) > 1 else numeric_values[0]

        results.append({
            "Datum": file_date,
            "Test": test_name,
            "Wert": value,
            "Einheit": unit,
            "Normbereich": norm,
            "Flag": "",
        })

    return results
