# output/writer.py
import csv
from pathlib import Path
from typing import Iterable, Dict

DEFAULT_FIELDS = ["Datum", "Alter", "Gruppe", "Test_Standard", "Test", "Wert_Norm", "Einheit_Norm", "Wert", "Einheit", "Normbereich", "Flag"]

def write_csv(records: Iterable[Dict], outpath: Path, include_empty: bool = False, fields: list = None):
    """
    Write records to CSV (semicolon-separated).
    - include_empty: if False, skip records without Wert and Wert_Norm.
    - fields: optional list of CSV columns (defaults to DEFAULT_FIELDS).
    """
    fields = fields or DEFAULT_FIELDS
    outpath.parent.mkdir(parents=True, exist_ok=True)

    def has_value(rec):
        # consider numeric normalized value first, fallback to raw Wert
        if rec.get("Wert_Norm") not in (None, ""):
            return True
        if rec.get("Wert") not in (None, ""):
            # avoid cases where Wert contains only unit names like '%' or 'mg/dL' without numeric
            v = str(rec.get("Wert")).strip()
            # treat pure non-digit strings as empty
            return any(ch.isdigit() for ch in v)
        return False

    with outpath.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, delimiter=";")
        writer.writeheader()
        for rec in records:
            if not include_empty and not has_value(rec):
                continue
            # ensure all fields exist
            row = {k: (rec.get(k, "") if rec.get(k, "") is not None else "") for k in fields}
            writer.writerow(row)
