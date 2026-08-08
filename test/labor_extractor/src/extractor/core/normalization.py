from extract_labvalues import TEST_ALIASES, UNIT_CONVERSIONS, GROUP_RULES


def classify_test(test_name: str) -> str:
    """Ordnet einen Testnamen einer Gruppe zu."""
    name_lower = test_name.lower()
    for pattern, group in GROUP_RULES:
        if pattern in name_lower:
            return group
    return "Sonstige"


def normalize_unit_and_value(test_standard: str, value_str: str, unit: str) -> tuple[str, str, str]:
    """Normalisiert Einheit und Wert.

    Returns: (normalisierter_wert, normalisierte_einheit, original_einheit)
    """
    unit_lower = unit.lower().strip()

    # Prüfen ob Konversion definiert
    conv_key = (unit_lower, test_standard)
    if conv_key in UNIT_CONVERSIONS:
        target_unit, factor = UNIT_CONVERSIONS[conv_key]

        # Wert konvertieren (nur wenn numerisch)
        try:
            numeric_val = float(value_str.replace(",", ".").replace("<", "").replace(">", ""))
            # Spezialfall Hämatokrit: nur konvertieren wenn Wert < 1 (also in L/L)
            if test_standard == "Hämatokrit" and numeric_val > 1:
                return value_str, unit, unit
            converted = numeric_val * factor
            # Sinnvolle Rundung
            if converted >= 100:
                converted_str = str(int(round(converted)))
            elif converted >= 10:
                converted_str = f"{converted:.1f}"
            else:
                converted_str = f"{converted:.2f}"
            # Prefix (< oder >) beibehalten
            prefix = ""
            if value_str.startswith("<"):
                prefix = "<"
            elif value_str.startswith(">"):
                prefix = ">"
            return prefix + converted_str, target_unit, unit
        except ValueError:
            return value_str, unit, unit

    # Einheit standardisieren (nur Schreibweise)
    unit_map = {
        "mg/dl": "mg/dL", "mmol/l": "mmol/L", "u/l": "U/L",
        "g/dl": "g/dL", "ng/ml": "ng/mL", "pg/ml": "pg/mL",
        "ml/min/kof": "mL/min", "ml/min": "mL/min",
        "10^9/l": "10^9/L", "10^12/l": "10^12/L",
    }
    std_unit = unit_map.get(unit_lower, unit)
    return value_str, std_unit, unit


def normalize_test_name(test_name: str) -> str:
    """Normalisiert den Testnamen auf einen Standard-Namen."""
    name_lower = test_name.lower().strip()

    # Exakter Match (höchste Priorität)
    if name_lower in TEST_ALIASES:
        return TEST_ALIASES[name_lower]

    # Teilmatch: längere Patterns zuerst prüfen (spezifischer vor allgemein)
    sorted_aliases = sorted(TEST_ALIASES.items(), key=lambda x: -len(x[0]))
    for alias, standard in sorted_aliases:
        if alias in name_lower:
            # Schutz: kurze Aliases (<=3 Zeichen) nur am Wortanfang matchen
            if len(alias) <= 3:
                if name_lower.startswith(alias) and (len(name_lower) == len(alias) or not name_lower[len(alias)].isalnum()):
                    return standard
            else:
                return standard

    # Kein Match: Original zurückgeben (bereinigt)
    return test_name.strip()
