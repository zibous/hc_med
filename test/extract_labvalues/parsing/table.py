import re
from pathlib import Path

_WHITESPACE_SPLIT = re.compile(r"\t+|\s{2,}")  # tabs or 2+ spaces

def _clean(s: str) -> str:
    if s is None:
        return ""
    return s.replace("\ufeff", "").replace("\xa0", " ").strip()

def parse_table_format(filepath: Path) -> list[dict]:
    text = filepath.read_text(encoding="utf-8", errors="replace")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [l for l in text.splitlines() if l.strip()]
    results = []
    if not lines:
        return results

    # find header line index (first occurrence of Gruppe/Test/Wert or Test/Norm/Erst-Wert)
    header_idx = 0
    for i, line in enumerate(lines[:8]):
        low = line.lower()
        if ("gruppe" in low and "test" in low and "wert" in low) or \
           ("test" in low and "norm" in low and "erst-wert" in low):
            header_idx = i
            break

    header_line = lines[header_idx]
    header_cols = _WHITESPACE_SPLIT.split(header_line)
    header_cols = [ _clean(h).lower() for h in header_cols ]

    def idx(name):
        try:
            return header_cols.index(name)
        except ValueError:
            return None

    i_gr = idx("gruppe")
    i_te = idx("test")
    i_we = idx("wert") if idx("wert") is not None else idx("letzt-wert")
    i_ei = idx("einheit")
    i_no = idx("normbereich") if idx("normbereich") is not None else idx("norm")
    i_fl = idx("flag")

    for line in lines[header_idx+1:]:
        parts = _WHITESPACE_SPLIT.split(line)
        parts = [ _clean(p) for p in parts ]
        if len(parts) < 2:
            continue

        get = lambda i: parts[i] if (i is not None and i < len(parts)) else ""
        gruppe = get(i_gr)
        test = get(i_te)
        wert = get(i_we)
        einheit = get(i_ei)
        norm = get(i_no)
        flag = get(i_fl)

        # normalize numeric: comma -> dot, remove spaces
        wert_norm = (wert or "").replace(",", ".").replace(" ", "")
        wert_num = ""
        if wert_norm:
            m = re.search(r"[<>]?\s*[\d\.]+", wert_norm)
            if m:
                wert_num = m.group(0)

        results.append({
            "Datum": None,
            "Gruppe": gruppe,
            "Test": test,
            "Wert": wert,
            "Wert_Norm": wert_num,
            "Einheit": einheit,
            "Normbereich": norm,
            "Flag": flag,
        })

    # optional: extract date from filename if present (YYYY-MM-DD)
    m = re.search(r"(\d{4}-\d{2}-\d{2})", filepath.name)
    if m:
        for r in results:
            if not r.get("Datum"):
                r["Datum"] = m.group(1)

    return results
