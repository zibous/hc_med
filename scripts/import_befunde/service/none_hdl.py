import logging
from collections import defaultdict

log = logging.getLogger("labor_pipeline")

class LipidCalculator:
    """Berechnet fehlende Lipid-Kennzahlen (Non-HDL, Quotienten) aus bestehenden Laborwerten."""
    
    def __init__(self):
        self.non_hdl_added = 0
        self.chol_hdl_added = 0
        self.ldl_hdl_added = 0

    def _parse_value(self, test_dict: dict) -> float | None:
        """Hilfsmethode: Extrahiert und bereinigt den numerischen Wert."""
        try:
            val_str = test_dict["Wert_Norm"].replace("<", "").replace(">", "")
            return float(val_str)
        except (ValueError, TypeError, KeyError):
            return None

    def _create_result_row(self, datum: str, age: str, test_name: str, wert: float, normbereich: str, flag: str, einheit: str = "") -> dict:
        """Hilfsmethode: Generiert standardisiert das neue Zeilen-Dictionary."""
        return {
            "Datum": datum, 
            "Alter": age, 
            "Gruppe": "Lipide",
            "Test_Standard": test_name,
            "Test": f"{test_name} (berechnet)",
            "Wert_Norm": str(wert), 
            "Einheit_Norm": einheit,
            "Wert": str(wert), 
            "Einheit": einheit,
            "Normbereich": normbereich, 
            "Flag": flag,
        }

    def calculate_metrics(self, all_results: list[dict]) -> list[dict]:
        """Verarbeitet die Laborliste und fügt berechnete Werte hinzu."""
        # Instanz-Zähler bei jedem Lauf zurücksetzen
        self.non_hdl_added = 0
        self.chol_hdl_added = 0
        self.ldl_hdl_added = 0

        # Gruppierung nach Datum
        by_datum = defaultdict(dict)
        for row in all_results:
            by_datum[row["Datum"]][row["Test_Standard"]] = row

        # Neue Ergebnisse sammeln, um all_results während der Iteration nicht zu manipulieren
        new_results = []

        for datum, tests in by_datum.items():
            # 1. Non-HDL-Cholesterin = Cholesterin - HDL
            if "Non-HDL-Cholesterin" not in tests and "Cholesterin" in tests and "HDL" in tests:
                chol_val = self._parse_value(tests["Cholesterin"])
                hdl_val = self._parse_value(tests["HDL"])
                
                if chol_val is not None and hdl_val is not None:
                    non_hdl = round(chol_val - hdl_val, 1)
                    flag = "H" if non_hdl >= 160 else ""
                    age = tests["Cholesterin"].get("Alter", "")
                    
                    new_results.append(self._create_result_row(
                        datum, age, "Non-HDL-Cholesterin", non_hdl, "<160", flag, "mg/dL"
                    ))
                    self.non_hdl_added += 1

            # 2. Quotient Chol/HDL = Cholesterin / HDL
            if "Quotient Chol/HDL" not in tests and "Cholesterin" in tests and "HDL" in tests:
                chol_val = self._parse_value(tests["Cholesterin"])
                hdl_val = self._parse_value(tests["HDL"])
                
                if chol_val is not None and hdl_val is not None and hdl_val > 0:
                    quot = round(chol_val / hdl_val, 1)
                    flag = "H" if quot > 5.0 else ""
                    age = tests["Cholesterin"].get("Alter", "")
                    
                    new_results.append(self._create_result_row(
                        datum, age, "Quotient Chol/HDL", quot, "0.0-5.0", flag
                    ))
                    self.chol_hdl_added += 1

            # 3. Quotient LDL/HDL = LDL / HDL
            if "Quotient LDL/HDL" not in tests and "LDL" in tests and "HDL" in tests:
                ldl_val = self._parse_value(tests["LDL"])
                hdl_val = self._parse_value(tests["HDL"])
                
                if ldl_val is not None and hdl_val is not None and hdl_val > 0:
                    quot = round(ldl_val / hdl_val, 1)
                    flag = "H" if quot > 3.0 else ""
                    age = tests["LDL"].get("Alter", "")
                    
                    new_results.append(self._create_result_row(
                        datum, age, "Quotient LDL/HDL", quot, "0.0-3.0", flag
                    ))
                    self.ldl_hdl_added += 1

        # Ergebnisse anhängen und zurückgeben
        all_results.extend(new_results)
        return all_results

    def print_summary(self):
        """Gibt die Zusammenfassung der berechneten Lipid-Werte aus."""
        berechnet_total = self.non_hdl_added + self.chol_hdl_added + self.ldl_hdl_added
        if berechnet_total:
            log.info("\n  📐 Berechnete Werte:")
            if self.non_hdl_added:
                log.info(f"    Non-HDL-Cholesterin: {self.non_hdl_added} (Cholesterin − HDL)")
            if self.chol_hdl_added:
                log.info(f"    Quotient Chol/HDL: {self.chol_hdl_added} (Cholesterin ÷ HDL)")
            if self.ldl_hdl_added:
                log.info(f"    Quotient LDL/HDL: {self.ldl_hdl_added} (LDL ÷ HDL)")
