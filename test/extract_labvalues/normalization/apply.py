# normalization/apply.py
import re
from datetime import date
from .gruppen import resolve_gruppe
from .aliases import resolve_test_standard, normalize_unit


def _calculate_flag(value: float, normbereich: str) -> str:
    """Calculate flag (H/L) from value vs normbereich string."""
    if not normbereich:
        return ""
    norm = normbereich.strip().replace(",", ".")

    # Pattern: "min-max" or "min - max"
    m = re.match(r"^([\d.]+)\s*-\s*([\d.]+)$", norm)
    if m:
        low, high = float(m.group(1)), float(m.group(2))
        if value < low:
            return "L"
        if value > high:
            return "H"
        return ""

    # Pattern: "<max" or "< max"
    m = re.match(r"^<\s*([\d.]+)$", norm)
    if m:
        high = float(m.group(1))
        if value > high:
            return "H"
        return ""

    # Pattern: ">min" or "> min"
    m = re.match(r"^>\s*([\d.]+)$", norm)
    if m:
        low = float(m.group(1))
        if value < low:
            return "L"
        return ""

    # Pattern: "-max" (e.g. "-0.49" meaning <0.49)
    m = re.match(r"^-([\d.]+)$", norm)
    if m:
        high = float(m.group(1))
        if value > high:
            return "H"
        return ""

    return ""


def normalize_record(r: dict, geburtsdatum: date | None = None) -> dict:
    """
    Normalisiert einen Laborwert-Record:
    - Testnamen → Standard-Name (Test_Standard)
    - Einheiten → Standard-Einheit mit Umrechnung
    - Wert_Norm: nur wenn Wert wirklich eine Zahl ist
    - Alter aus Geburtsdatum + Datum
    - Gruppe aus Test_Standard
    """

    raw_wert = (r.get("Wert") or "").strip()
    raw_einheit = (r.get("Einheit") or "").strip()
    raw_norm = (r.get("Normbereich") or "").strip()
    test_name = (r.get("Test") or "").strip()

    # --- 1) Testname normalisieren ---
    test_standard = resolve_test_standard(test_name)

    # --- 2) Wert normalisieren ---
    wert_norm = ""
    wert_numeric = None
    if raw_wert:
        m = re.match(r"^([<>]?)\s*([\d]+(?:[.,]\d+)?)", raw_wert)
        if m:
            prefix = m.group(1)
            num_str = m.group(2).replace(",", ".")
            wert_numeric = float(num_str)
            # Keep original string representation (preserves trailing zeros)
            wert_norm = f"{prefix}{num_str}"
        else:
            raw_wert = ""
    else:
        raw_wert = ""

    # --- 3) Einheit normalisieren + Wert umrechnen ---
    einheit_norm, converted_value = normalize_unit(raw_einheit, test_standard, wert_numeric)

    # Update wert_norm only if actual numeric conversion happened (factor != 1)
    if converted_value is not None and wert_numeric is not None and abs(converted_value - wert_numeric) > 0.0001:
        prefix = ""
        if wert_norm.startswith("<") or wert_norm.startswith(">"):
            prefix = wert_norm[0]
        # Format converted value preserving meaningful precision
        if converted_value == int(converted_value):
            # Whole number after conversion: use .1f to show it's a real measurement
            # e.g. 150 g/L -> 15.0 g/dL
            formatted = f"{converted_value:.1f}"
        else:
            formatted = f"{converted_value:g}"
        wert_norm = f"{prefix}{formatted}"

    # Fallback: if einheit_norm is empty but raw_einheit has no digits, use raw
    if not einheit_norm and raw_einheit:
        if not re.search(r"\d", raw_einheit):
            einheit_norm = raw_einheit

    # --- 4) Normbereich bleibt unverändert ---
    normbereich = raw_norm

    # --- 5) Alter berechnen ---
    alter = ""
    if geburtsdatum:
        datum_str = r.get("Datum") or ""
        m_date = re.match(r"(\d{4})-(\d{2})-(\d{2})", datum_str)
        if m_date:
            labor_date = date(int(m_date.group(1)), int(m_date.group(2)), int(m_date.group(3)))
            alter = labor_date.year - geburtsdatum.year
            if (labor_date.month, labor_date.day) < (geburtsdatum.month, geburtsdatum.day):
                alter -= 1
            alter = str(alter)

    # --- 6) Gruppe zuordnen (basierend auf Test_Standard) ---
    gruppe = r.get("Gruppe") or ""
    if not gruppe:
        gruppe = resolve_gruppe(test_standard)

    # --- 7) Flag normalisieren oder berechnen ---
    flag = (r.get("Flag") or "").strip()
    if flag == "+":
        flag = "H"
    elif flag == "-":
        flag = "L"
    elif flag.upper() in ("H", "L"):
        flag = flag.upper()
    elif flag in ("hämolyt.",):
        flag = ""  # nicht pathologisch, nur Hinweis

    # Wenn kein Flag vorhanden: aus Wert vs Normbereich berechnen
    if not flag and wert_numeric is not None and normbereich:
        flag = _calculate_flag(converted_value if converted_value is not None else wert_numeric, normbereich)

    return {
        "Datum": r.get("Datum"),
        "Alter": alter,
        "Gruppe": gruppe,
        "Test_Standard": test_standard,
        "Test": test_name,
        "Wert_Norm": wert_norm,
        "Einheit_Norm": einheit_norm,
        "Wert": raw_wert,
        "Einheit": raw_einheit,
        "Normbereich": normbereich,
        "Flag": flag,
    }
