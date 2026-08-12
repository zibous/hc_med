from pathlib import Path
import re
import logging

from .freetext import parse_freetext_file
from .table import parse_table_format
from .kuerzel import parse_kuerzel_space_format
from .pivot import parse_pivot_format
from .csv_format import parse_csv_format
from .pdf_text import parse_pdf_text_format
from .tab_format import parse_tab_format
from .verlauf import parse_verlauf_format

PARSER_MAP = {
    "freetext": parse_freetext_file,
    "table": parse_table_format,
    "kuerzel": parse_kuerzel_space_format,
    "pivot": parse_pivot_format,
    "csv": parse_csv_format,
    "pdf_text": parse_pdf_text_format,
    "tab": parse_tab_format,
    "verlauf": parse_verlauf_format,
}

def detect_format_for_file(filepath: Path) -> str:
    name = filepath.name.lower()
    text = filepath.read_text(encoding="utf-8", errors="replace")[:8000]
    lower = text.lower()

    # 1) Robust header detection: "gruppe <whitespace> test <whitespace> wert"
    if re.search(r"gruppe\s+test\s+wert", lower):
        return "table"

    # 2) Freetext with "Laborbefund vom" date headers (must come before kuerzel check)
    if re.search(r"laborbefund vom \d{2}\.\d{2}\.\d{4}", lower):
        return "freetext"

    # 2b) PDF text export: "Analyse Ergebnis Einheit Referenzbereiche"
    if re.search(r"analyse\s+ergebnis\s+einheit\s+referenz", lower):
        return "freetext"

    # 2c) Verlaufs-Tabelle: "Test Norm Erst-Wert ... Letzt-Wert Einheit" (space-separated)
    if re.search(r"test\s+norm\s+erst-wert", lower):
        return "verlauf"

    # 3) CSV with semicolon (including .txt files with semicolon-separated data)
    if ";" in text:
        first_line = text.splitlines()[0] if text.splitlines() else ""
        # Explicit CSV-like header with "Tag;" or file is .csv
        if first_line.startswith("Tag;") or filepath.suffix.lower() == ".csv":
            return "csv"

    # 3) Pivot-like (Parameter; ...)
    if "parameter;" in lower or (lower.splitlines() and lower.splitlines()[0].count(";") > 2):
        return "pivot"

    # 4) Tab-format with specific header token
    if "\t" in text and "kürzel" in lower:
        return "tab"

    # 5) Freetext vs. Kürzel heuristic
    if re.search(r"\b(leuko|krea|crp|gfr-ckd)\b", text, re.IGNORECASE) and re.search(r"\d[,\.]\d", text):
        if re.search(r"^[A-ZÄÖÜ]{2,6}\s", text, re.MULTILINE):
            return "kuerzel"
        return "freetext"

    # 6) PDF text heuristic
    if re.search(r"\d{4}-\d{2}-\d{2}", name) and re.search(r"(10\^9\/l|mg\/dl|mmol\/l)", text, re.IGNORECASE):
        return "pdf_text"

    # 7) Table header tokens
    if re.search(r"test\s+norm\s+einheit", lower):
        return "table"

    logging.getLogger("auto_detect").debug("Fallback für %s", filepath)
    return "freetext"
