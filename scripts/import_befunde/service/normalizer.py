"""Testnamen-Normalisierung, Gruppen-Zuordnung und medizinische Korrekturen."""

from config.app_config import config


class LaborDataNormalizer:
    """Kapselt die Funktionen zur Namens-Normalisierung und Gruppenzuweisung."""

    def normalize_test_name(self, raw_name: str) -> str:
        """Bereinigt den String und gibt den Standardnamen zurück."""
        if not raw_name or not isinstance(raw_name, str):
            return ""
        cleaned_name = " ".join(raw_name.split()).lower()
        return config.TEST_ALIASES.get(cleaned_name, raw_name.strip())

    def assign_group(self, row: dict) -> None:
        """Bestimmt die Gruppe basierend auf den Gruppen-Regeln der Config."""
        test_name = row.get("Test_Standard", row.get("Test", "")).lower()
        for pattern, group_name in config.GROUP_RULES:
            if pattern in test_name:
                row["Gruppe"] = group_name
                return
        row["Gruppe"] = row.get("Gruppe", "Sonstige")

    def apply_medical_corrections(self, row: dict) -> None:
        """Medizinische Plausibilitätskorrekturen anhand von Einheit und Wert."""
        unit_lower = row.get("Einheit", "").lower().strip()
        test_std = row["Test_Standard"]
        current_value = row.get("Wert", "")

        # abs/rel Korrektur basierend auf Einheit
        if test_std.endswith(" abs.") and unit_lower in ("%", "응"):
            row["Test_Standard"] = test_std.replace(" abs.", " rel.")
        elif test_std.endswith(" rel.") and unit_lower in ("g/l", "10^9/l", "10^9/L"):
            row["Test_Standard"] = test_std.replace(" rel.", " abs.")

        # Hämoglobin-Differenzierung (MCH vs HbA1c IFCC)
        if row["Test_Standard"] == "Hämoglobin":
            if unit_lower == "pg":
                row["Test_Standard"] = "MCH"
            elif not unit_lower and current_value:
                try:
                    v = float(str(current_value).replace("<", "").replace(">", ""))
                    if v > 20:
                        row["Test_Standard"] = "HbA1c (IFCC)"
                        row["Einheit_Norm"] = config.STANDARD_UNITS.get(
                            "HbA1c (IFCC)", "mmol/mol"
                        )
                except ValueError:
                    pass

        # HbA1c IFCC-Erkennung anhand Wertebereich
        if row["Test_Standard"] == "HbA1c" and current_value:
            try:
                v = float(str(current_value).replace("<", "").replace(">", ""))
                if v > 15:
                    row["Test_Standard"] = "HbA1c (IFCC)"
                    row["Einheit_Norm"] = config.STANDARD_UNITS.get(
                        "HbA1c (IFCC)", "mmol/mol"
                    )
            except ValueError:
                pass

        # HbA1c (IFCC) → HbA1c (NGSP): mmol/mol in % umrechnen und zusammenführen
        # Formel: NGSP(%) = IFCC(mmol/mol) / 10.929 + 2.15
        if row["Test_Standard"] == "HbA1c (IFCC)":
            try:
                v = float(
                    str(row.get("Wert_Norm") or row.get("Wert", ""))
                    .replace("<", "")
                    .replace(">", "")
                )
                ngsp = round(v / 10.929 + 2.15, 1)
                row["Test_Standard"] = "HbA1c"
                row["Wert_Norm"] = str(ngsp)
                row["Einheit_Norm"] = "%"
                row["Normbereich"] = "4.0 - 5.6"
            except (ValueError, TypeError):
                pass
