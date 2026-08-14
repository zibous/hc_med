"""Einheiten-Konversion, Schreibweisen-Normalisierung und Auffüllung."""

from config.app_config import config


# ─── Kosmetische Normalisierung (Groß/Kleinschreibung) ─────────────────────────
COSMETIC_UNIT_MAP = {
    "mg/dl": "mg/dL",
    "ng/ml": "ng/mL",
    "u/l": "U/L",
    "ku/l": "KU/L",
    "µmol/l": "µmol/L",
    "g/dl": "g/dL",
    "g/l": "g/L",
    "g/l_": "g/L_",
    "ml/min": "mL/min",
    "10^9/l": "10^9/L",
    "10^12/l": "10^12/L",
    "mmol/l": "mmol/L",
    "miу/l": "mIU/L",
    "miu/l": "mIU/L",
    "pg/ml": "pg/mL",
    "ng/dl": "ng/dL",
    "µg/dl": "µg/dL",
    "µg/l": "µg/L",
    "mg/l": "mg/L",
}

# ─── Ziel-Einheiten-Normalisierung (nach Konversion) ──────────────────────────
TARGET_UNIT_MAP = {
    "u/l": "U/L",
    "ku/l": "U/L",
    "mg/dl": "mg/dL",
    "ng/ml": "ng/mL",
    "µmol/l": "µmol/L",
    "g/dl": "g/dL",
    "ml/min": "mL/min",
    "fl": "fL",
}


class UnitHandler:
    """Verantwortlich für Einheiten-Konversion und -Normalisierung."""

    def normalize_and_convert(self, row: dict) -> None:
        """Prüft die Einheit einer Zeile und rechnet den Wert bei Bedarf um."""
        test_name = row.get("Test_Standard", "")
        raw_unit = row.get("Einheit", "")
        if not raw_unit or not test_name:
            return

        cleaned_unit = "".join(raw_unit.split()).lower()
        lookup_key = (cleaned_unit, test_name)

        if lookup_key not in config.UNIT_CONVERSIONS:
            return

        target_unit, factor = config.UNIT_CONVERSIONS[lookup_key]

        # Sonderfall Hämatokrit: Nur konvertieren wenn Wert < 1 (Volumenanteil)
        if test_name == "Hämatokrit" and cleaned_unit in ("l/l", "/l"):
            try:
                val_str = row.get("Wert", "0").replace("<", "").replace(">", "")
                if float(val_str) >= 1.0:
                    return
            except (ValueError, TypeError):
                return

        try:
            if "Wert" in row and row["Wert"]:
                prefix = "<" if "<" in row["Wert"] else ">" if ">" in row["Wert"] else ""
                val_clean = row["Wert"].replace("<", "").replace(">", "")
                calculated_val = float(val_clean) * factor

                new_val_str = self._format_converted_value(test_name, target_unit, calculated_val)
                row["Wert_Norm"] = f"{prefix}{new_val_str}"

            # Einheit normalisieren
            row["Einheit_Norm"] = self._normalize_target_unit(target_unit)

        except (ValueError, TypeError):
            pass

    def fill_missing_standard_unit(self, row: dict) -> None:
        """Prüft, ob die Einheit fehlt und trägt den Standardwert ein."""
        test_name = row.get("Test_Standard", "")
        if not row.get("Einheit") and test_name in config.STANDARD_UNITS:
            row["Einheit"] = config.STANDARD_UNITS[test_name]

    def resolve_einheit_norm(self, row: dict) -> None:
        """Bestimmt die normalisierte Einheit (Einheit_Norm) für eine Zeile."""
        test_name = row.get("Test_Standard", "")
        raw_u = row.get("Einheit", "")

        # Bereits durch Konversion gesetzt? → Nicht überschreiben
        if row.get("Einheit_Norm"):
            return

        # 1. Einheitenlose Tests (Quotienten, INR, pH)
        std_unit = config.STANDARD_UNITS.get(test_name, None)
        if std_unit == "":
            # Spezialfall: Quotient LDL/HDL mit historischem Stern
            if test_name == "Quotient LDL/HDL":
                year_str = str(row.get("Datum", ""))[:4]
                if year_str.isdigit() and int(year_str) <= 2019:
                    row["Einheit"] = "*"
                    row["Einheit_Norm"] = "*"
                else:
                    row["Einheit"] = ""
                    row["Einheit_Norm"] = ""
            else:
                row["Einheit_Norm"] = ""
            return

        # 2. Keine Roh-Einheit vorhanden → Standard aus YAML nehmen
        if not raw_u and std_unit:
            row["Einheit_Norm"] = std_unit
            return

        # 3. Roh-Einheit vorhanden, KEINE Konversion erfolgt →
        #    Kosmetische Normalisierung der Schreibweise (mg/dl → mg/dL etc.)
        row["Einheit_Norm"] = self._cosmetic_normalize(raw_u)

    # ──────────────────────────────────────────────────────────────────────────
    # PRIVATE HILFSMETHODEN
    # ──────────────────────────────────────────────────────────────────────────
    def _format_converted_value(self, test_name: str, target_unit: str, value: float) -> str:
        """Formatiert einen konvertierten Wert passend zum Test/Einheit."""
        test_lower = test_name.lower()

        # Cholinesterase → ganzzahlig
        if "cholinesterase" in test_lower or "che" in test_lower:
            return str(int(round(value)))
        # Hämoglobin oder Prozent → eine Nachkommastelle
        if test_name == "Hämoglobin" or target_unit == "%":
            return f"{value:.1f}"
        # Standard → zwei Nachkommastellen
        return f"{value:.2f}"

    def _normalize_target_unit(self, target_unit: str) -> str:
        """Normalisiert die Schreibweise der Ziel-Einheit nach Konversion."""
        return TARGET_UNIT_MAP.get(target_unit.lower(), target_unit)

    def _cosmetic_normalize(self, raw_unit: str) -> str:
        """Normalisiert nur die Groß/Kleinschreibung gängiger Einheiten."""
        if not raw_unit:
            return ""
        cleaned = raw_unit.strip()
        return COSMETIC_UNIT_MAP.get(cleaned.lower(), cleaned)
