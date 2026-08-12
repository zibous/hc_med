import re
from pathlib import Path


def parse_csv_format(filepath: Path) -> list[dict]:
    text = filepath.read_text(encoding="utf-8", errors="replace")
    results = []
    lines = text.splitlines()
    
    # Detect header to determine column layout
    header_line = lines[0].strip() if lines else ""
    header_parts = [h.strip().lower() for h in header_line.split(";")]
    
    # Build column index map from header
    col_map = {name: idx for idx, name in enumerate(header_parts)}
    
    # Determine if this is a header-based CSV or legacy format
    has_header = any(k in col_map for k in ("test", "wert", "gruppe"))
    
    if has_header:
        return _parse_with_header(lines[1:], col_map, filepath)
    else:
        return _parse_legacy(lines, filepath)


def _parse_with_header(lines: list[str], col_map: dict, filepath: Path) -> list[dict]:
    """Parse CSV where first line is a recognized header."""
    results = []
    
    # Extract date from filename (e.g. 2013-12-20_laborbefund_...)
    date_str = ""
    dm = re.match(r"(\d{4}-\d{2}-\d{2})", filepath.stem)
    if dm:
        date_str = dm.group(1)
    else:
        dm2 = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", filepath.stem)
        if dm2:
            date_str = f"{dm2.group(3)}-{dm2.group(2)}-{dm2.group(1)}"
    
    # Determine value column: prefer "letzt-wert" (aktuellster Wert) over "wert" over "erst-wert"
    value_col = None
    for candidate in ("letzt-wert", "wert", "erst-wert"):
        if candidate in col_map:
            value_col = candidate
            break
    
    for line in lines:
        if not line.strip():
            continue
        parts = line.split(";")
        
        # Handle lines with extra columns (e.g. "Baso;Abs;..." where Test is "Baso Abs")
        expected_cols = len(col_map)
        if len(parts) > expected_cols:
            # Extra fields in test name area - merge them
            extra = len(parts) - expected_cols
            merged_test = " ".join(parts[col_map["test"]:col_map["test"] + extra + 1])
            parts = parts[:col_map["test"]] + [merged_test] + parts[col_map["test"] + extra + 1:]
        
        test = parts[col_map["test"]].strip() if "test" in col_map and col_map["test"] < len(parts) else ""
        
        # Value from best available column
        wert = ""
        if value_col and col_map[value_col] < len(parts):
            wert = parts[col_map[value_col]].strip()
        
        einheit = parts[col_map["einheit"]].strip() if "einheit" in col_map and col_map["einheit"] < len(parts) else ""
        
        # Normbereich: try "normbereich" then "norm"
        norm = ""
        for norm_key in ("normbereich", "norm"):
            if norm_key in col_map and col_map[norm_key] < len(parts):
                norm = parts[col_map[norm_key]].strip()
                break
        
        flag = parts[col_map["flag"]].strip() if "flag" in col_map and col_map["flag"] < len(parts) else ""
        gruppe = parts[col_map["gruppe"]].strip() if "gruppe" in col_map and col_map["gruppe"] < len(parts) else ""
        
        # Datum: from "tag" or "datum" column, or from filename
        datum = ""
        for date_key in ("tag", "datum"):
            if date_key in col_map and col_map[date_key] < len(parts):
                raw = parts[col_map[date_key]].strip()
                dm = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", raw)
                if dm:
                    datum = f"{dm.group(3)}-{dm.group(2)}-{dm.group(1)}"
                elif re.match(r"\d{4}-\d{2}-\d{2}", raw):
                    datum = raw
                break
        if not datum:
            datum = date_str
        
        if not test:
            continue
            
        results.append({
            "Datum": datum,
            "Test": test,
            "Gruppe": gruppe,
            "Wert": wert.replace(",", "."),
            "Einheit": einheit,
            "Normbereich": norm,
            "Flag": flag,
        })
    
    return results


def _parse_legacy(lines: list[str], filepath: Path) -> list[dict]:
    """Legacy format: Tag;Test;Norm;...;Value;Unit (7+ columns, no recognized header)."""
    results = []

    for line in lines:
        if line.startswith("Tag;"):
            continue

        parts = line.split(";")
        if len(parts) < 5:
            continue

        raw_date = parts[0].strip()
        dm = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", raw_date)
        if dm:
            date_str = f"{dm.group(3)}-{dm.group(2)}-{dm.group(1)}"
        else:
            date_str = raw_date

        test_name = parts[1].strip()
        norm = parts[2].strip()

        # Safely access value column
        if len(parts) > 6:
            value = parts[6].strip() or parts[3].strip()
        else:
            value = parts[3].strip() if len(parts) > 3 else ""
        unit = parts[-1].strip()

        results.append({
            "Datum": date_str,
            "Test": test_name,
            "Wert": value.replace(",", "."),
            "Einheit": unit,
            "Normbereich": norm,
            "Flag": "",
        })

    return results
