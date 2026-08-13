import re
from pathlib import Path

# ─── 1. IMPORTS AUS DEINEN NEUEN MODUL-ORDNERN ────────────────────────────────
from config.app_config import config
from service.calc_age import PatientAgeCalculator
from service.none_hdl import LipidCalculator
from writer.csv_export import LaborCSVExporter

# Parser-Imports
from parser.autodetect import detect_format
from parser.simple_csv import SimpleCSVParser
from parser.csv import CSVFormatParser
from parser.ocr import KuerzelSpaceParser
from parser.pdf_text import PDFTextFormatParser
from parser.pivot import PivotFormatParser
from parser.tab_format import TabFormatParser
from parser.freetext import FreeTextParser
from parser.table import TableFormatParser


# ─── 2. HILFSKLASSE FÜR YAML-LOOKUPS ──────────────────────────────────────────
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


# ─── 3. HAUPT-PIPELINE KLASSE ─────────────────────────────────────────────────
class LaborDataPipeline:
    """Verarbeitet rohe Laborbefunde durch eine strukturierte Reinigungs-Pipeline."""
    
    def __init__(self):
        self.normalizer = LaborDataNormalizer()
        self.age_calc = PatientAgeCalculator(config.PATIENT_GEBURTSDATUM)
        self.lipid_calc = LipidCalculator()
        self.csv_exporter = LaborCSVExporter()
        
        self.BLACKLIST = getattr(config, "PIPELINE_BLACKLIST", set())
        self.KOERPERDATEN_BLACKLIST = getattr(config, "KOERPERDATEN_BLACKLIST", set())
        self.INVALID_NORMS = getattr(config, "INVALID_NORMS", set())
        
    def process_all_files(self, txt_files: list) -> tuple[list, list]:
        """Hauptmethode: Iteriert über alle Dateien und führt die Pipeline aus."""
        all_results = []
        file_results = []
        
        for filepath in txt_files:
            
            fmt = detect_format(filepath)
            # print(f"  {filepath.name} -> Format: {fmt}")

            file_text = filepath.read_text(encoding="utf-8", errors="replace")
            nuechtern = self._detect_nuechtern(file_text)

            results = self._parse_by_format(filepath, fmt)
            print(f"{filepath.name}  ->  {len(results)} Werte extrahiert")

            processed_rows = []
            for row in results:
                row["Nuechtern"] = nuechtern
                row = self._normalize_and_correct_row(row)
                if self._is_valid_row(row):
                    processed_rows.append(row)

            self._apply_norm_and_flags_logic(
                processed_rows, file_results, all_results, filepath, fmt, nuechtern
            )

        all_results = self.lipid_calc.calculate_metrics(all_results)
        self.lipid_calc.print_summary()
        self.csv_exporter.export(all_results)
        
        return file_results, all_results

    def _detect_nuechtern(self, file_text: str) -> int:
        """Erkennt, ob der Befund nüchtern abgenommen wurde."""
        match = re.search(r"#\s*nüchtern\s*:\s*(nein|ja|no|yes)", file_text, re.IGNORECASE)
        if match and match.group(1).lower() in ("nein", "no"):
            return 0
        return 1

    def _parse_by_format(self, filepath: Path, fmt: str) -> list[dict]:
        """Dynamischer Parser-Wechsler basierend auf dem erkannten Format."""        
        # print(f"{filepath.name}  ->  {fmt} ")
        parsers = {
            "simple_csv": SimpleCSVParser, 
            "csv": CSVFormatParser,
            "pivot": PivotFormatParser, 
            "table": TableFormatParser,
            "tab": TabFormatParser, 
            "kuerzel_space": KuerzelSpaceParser,            
            "pdf_text": PDFTextFormatParser
        }
        parser_class = parsers.get(fmt, FreeTextParser)
        return parser_class().parse(filepath)

    def _normalize_and_correct_row(self, row: dict) -> dict:
        """Kapselt die gesamte textuelle und medizinische Korrektur-Logik pro Zeile."""
        
        # 1. Namen über das lokale Normalizer-Objekt vereinheitlichen
        row["Test_Standard"] = self.normalizer.normalize_test_name(row["Test"])
        
        # 2. Lokale Klassen-Methoden aufrufen
        self._normalize_and_convert_unit(row)
        self._fill_missing_standard_unit(row)
        
        # 3. Gruppe zuweisen
        if not row.get("Gruppe") or row.get("Gruppe") == "Sonstige":
            self.normalizer.assign_group(row)

        # Medizinische Plausibilitätskorrekturen anhand der Einheit
        unit_lower = row.get("Einheit", "").lower().strip()
        test_std = row["Test_Standard"]

        if test_std.endswith(" abs.") and unit_lower in ("%", "응"):
            row["Test_Standard"] = test_std.replace(" abs.", " rel.")
        elif test_std.endswith(" rel.") and unit_lower in ("g/l", "10^9/l", "10^9/L"):
            row["Test_Standard"] = test_std.replace(" rel.", " abs.")

        current_value = row.get("Wert", "")

        if row["Test_Standard"] == "Hämoglobin":
            if unit_lower == "pg":
                row["Test_Standard"] = "MCH"
            elif not unit_lower and current_value:
                try:
                    v = float(str(current_value).replace("<", "").replace(">", ""))
                    if v > 20:
                        row["Test_Standard"] = "HbA1c (IFCC)"
                        row["Einheit_Norm"] = "mmol/mol"
                except ValueError:
                    pass

        if row["Test_Standard"] == "HbA1c" and current_value:
            try:
                v = float(str(current_value).replace("<", "").replace(">", ""))
                if v > 15:
                    row["Test_Standard"] = "HbA1c (IFCC)"
                    row["Einheit_Norm"] = "mmol/mol"
            except ValueError:
                pass

        age = self.age_calc.age_at(row["Datum"])
        row["Alter"] = str(age) if age else ""
        return row

    def _normalize_and_convert_unit(self, row: dict) -> None:
        """Prüft die Einheit einer Zeile und rechnet den Wert bei Bedarf um."""
        test_name = row.get("Test_Standard", "")
        raw_unit = row.get("Einheit", "")
        if not raw_unit or not test_name:
            return

        cleaned_unit = "".join(raw_unit.split()).lower()
        lookup_key = (cleaned_unit, test_name)

        if lookup_key in config.UNIT_CONVERSIONS:
            target_unit, factor = config.UNIT_CONVERSIONS[lookup_key]
            
            if test_name == "Hämatokrit" and cleaned_unit in ("l/l", "/l"):
                try:
                    val_str = row.get("Wert", "0").replace("<", "").replace(">", "")
                    if float(val_str) >= 1.0:
                        return
                except (ValueError, TypeError, KeyError):
                    return

            try:
                if "Wert" in row and row["Wert"]:
                    prefix = "<" if "<" in row["Wert"] else ">" if ">" in row["Wert"] else ""
                    val_clean = row["Wert"].replace("<", "").replace(">", "")
                    calculated_val = float(val_clean) * factor
                    
                    # 💡 FIX 1: Robust gegen jeden Cholinesterase-Namen (CHE, Cholinesterase) vorgehen
                    test_lower = str(test_name).lower() or str(row.get("Test", "")).lower()
                    if "cholinesterase" in test_lower or "che" in test_lower:
                        new_val_str = str(int(round(calculated_val)))
                    elif test_name == "Hämoglobin" or target_unit == "%":
                        new_val_str = f"{calculated_val:.1f}"
                    else:
                        new_val_str = f"{calculated_val:.2f}"
                            
                    row["Wert_Norm"] = f"{prefix}{new_val_str}"
                
                # 💡 FIX 2: Erzwingt U/L für Cholinesterase bei Einheiten-Konversionen
                if target_unit.lower() == "u/l":
                    row["Einheit_Norm"] = "U/L"
                elif target_unit.lower() == "ku/l":
                    row["Einheit_Norm"] = "U/L"
                else:
                    row["Einheit_Norm"] = target_unit

            except (ValueError, TypeError):
                pass


    def _fill_missing_standard_unit(self, row: dict) -> None:
        """Prüft, ob die Einheit fehlt und trägt den Standardwert ein."""
        test_name = row.get("Test_Standard", "")
        if not row.get("Einheit") and test_name in config.STANDARD_UNITS:
            std_unit = config.STANDARD_UNITS[test_name]
            row["Einheit"] = std_unit

    def _is_valid_row(self, row: dict) -> bool:
        """Filtert ungültige Text-Artefakte und bedingt Körperdaten heraus."""
        test_std_lower = row["Test_Standard"].lower()
        if any(bl in test_std_lower for bl in self.BLACKLIST):
            return False
        if config.HAS_SCALE_DB and test_std_lower in self.KOERPERDATEN_BLACKLIST:
            return False
            
        raw_value = row.get("Wert", "")
        if not raw_value:
            return False
            
        wert_clean = str(raw_value).replace("<", "").replace(">", "").strip()
        try:
            float(wert_clean)
            return True
        except ValueError:
            return False

    def _apply_norm_and_flags_logic(self, results: list[dict], file_results: list, all_results: list, filepath: Path, fmt: str, nuechtern: int) -> None:
        """Flags berechnen/korrigieren anhand des Normbereichs."""
        import re as _re
        fallback_norms = config.STANDARD_UNITS
        
        validated_results = []
        
        for row in results:
            test_name = row.get("Test_Standard", "")
            raw_u = row.get("Einheit", "")
            norm = row.get("Normbereich", "").strip()

            # ─── 1. EINHEIT_NORM INTELLIGENT BESTIMMEN ────────────────────────
            cleaned_raw_u = raw_u.lower().strip()
            
            # 💡 KORREKTUR: INR bleibt leer, der Quotient LDL/HDL erhält das vom Monolithen erwartete Sternchen '*'!
            if test_name == "INR":
                row["Einheit"] = ""
                row["Einheit_Norm"] = ""
            elif test_name == "Quotient LDL/HDL":                
                year_str = str(row.get("Datum", ""))[:4]
                if year_str.isdigit() and int(year_str) <= 2019:
                    row["Einheit"] = "*"
                    row["Einheit_Norm"] = "*"
                else:
                    row["Einheit"] = ""
                    row["Einheit_Norm"] = ""
            elif test_name == "Cholinesterase":
                row["Einheit_Norm"] = "U/L"
            elif cleaned_raw_u in ("103/µl", "106/µl", "/ľl", "sek.", "%hb", "ng/ml", "mg/dl", "u/l", "ku/l", "µmol/l"):
                if cleaned_raw_u == "mg/dl": row["Einheit_Norm"] = "mg/dL"
                elif cleaned_raw_u == "ng/ml": row["Einheit_Norm"] = "ng/mL"
                elif cleaned_raw_u == "u/l": row["Einheit_Norm"] = "U/L"
                elif cleaned_raw_u == "ku/l": row["Einheit_Norm"] = "KU/L"
                elif cleaned_raw_u == "µmol/l": row["Einheit_Norm"] = "µmol/L"
                else: row["Einheit_Norm"] = raw_u
            else:
                yaml_val = fallback_norms.get(test_name, "")
                if yaml_val and "-" not in str(yaml_val) and "<" not in str(yaml_val) and ">" not in str(yaml_val):
                    row["Einheit_Norm"] = yaml_val
                else:
                    row["Einheit_Norm"] = raw_u.replace("/l", "/L").replace("/l_", "/L") if "/l" in raw_u.lower() else raw_u

            # Kosmetische Korrekturen für Hämoglobin & MPV Einheiten
            if row.get("Einheit_Norm") == "g/dl":
                row["Einheit_Norm"] = "g/dL"
            if test_name == "MPV" and row.get("Einheit_Norm") == "g/dL":
                row["Einheit_Norm"] = "fL"

            # ─── 2. NORMBEREICH INTELLIGENT BEREINIGEN & AUFFÜLLEN ────────────
            if "Norm" in row and not norm:
                row["Normbereich"] = row["Norm"]
                norm = row["Norm"].strip()

            if norm.lower() in self.INVALID_NORMS:
                norm = ""
                row["Normbereich"] = ""

            if norm:
                norm = _re.sub(r"^(<\s*)-\s*", r"\1", norm)
                row["Normbereich"] = norm

            if norm and _re.match(r"^\d+\.?\d*$", norm):
                norm = f"< {norm}"
                row["Normbereich"] = norm

            # Wenn der Befund leer war (oder das unsaubere Wort 'Quotient' enthält), holen wir uns die Norm aus der YAML!
            if not norm or norm.lower() == "quotient":
                yaml_val = fallback_norms.get(test_name, "")
                if test_name == "Testosteron":
                    norm = "2.5-8.0"
                    row["Normbereich"] = norm
                elif yaml_val and ("-" in str(yaml_val) or "<" in str(yaml_val) or ">" in str(yaml_val)):
                    norm = yaml_val
                    row["Normbereich"] = norm
                else:
                    row["Normbereich"] = ""
                    norm = ""

            if not row.get("Wert_Norm"):
                row["Wert_Norm"] = row.get("Wert", "")

            wert_str = row.get("Wert_Norm", "").replace("<", "").replace(">", "").strip()
            if not norm or not wert_str:
                validated_results.append(row)
                continue
                
            try:
                wert = float(wert_str)
            except ValueError:
                validated_results.append(row)
                continue

            norm_lo, norm_hi = None, None
            m = _re.match(r"^([\d.]+)\s*-\s*([\d.]+)$", norm)
            if m:
                norm_lo, norm_hi = float(m.group(1)), float(m.group(2))
                
            if test_name == "Hämatokrit" and norm_hi is not None and norm_hi < 1:
                norm_lo = norm_lo * 100 if norm_lo else None
                norm_hi = norm_hi * 100
                row["Normbereich"] = f"{norm_lo:.0f}-{norm_hi:.0f}" if norm_lo else f"<{norm_hi:.0f}"

            if test_name in ("Hämoglobin", "MCHC") and norm_hi is not None and norm_hi > 50:
                norm_lo = norm_lo / 10 if norm_lo else None
                norm_hi = norm_hi / 10
                row["Normbereich"] = f"{norm_lo:.1f}-{norm_hi:.1f}" if norm_lo else f"<{norm_hi:.1f}"

            if test_name == "Cholinesterase" and norm_hi is not None and norm_hi < 20:
                norm_lo = norm_lo * 1000 if norm_lo else None
                norm_hi = norm_hi * 1000
                row["Normbereich"] = f"{norm_lo:.0f}-{norm_hi:.0f}" if norm_lo else f"<{norm_hi:.0f}"
                
            m2 = _re.match(r"^[<]\s*-?\s*([\d.]+)$", norm)
            if m2: norm_hi = float(m2.group(1))
                
            m3 = _re.match(r"^[>]\s*-?\s*([\d.]+)$", norm)
            if m3: norm_lo = float(m3.group(1))
                
            m4 = _re.match(r"^-\s*([\d.]+)$", norm)
            if m4 and not m: norm_hi = float(m4.group(1))

            if test_name == "GFR" and norm_lo == 90.0:
                if wert >= 85.0:
                    norm_lo = None
                else:
                    norm_lo = 85.0

            if norm_hi is not None and wert > norm_hi:
                row["Flag"] = "H"
            elif norm_lo is not None and wert < norm_lo:
                row["Flag"] = "L"
            else:
                row["Flag"] = ""

            validated_results.append(row)

        file_results.append((filepath.name, fmt, validated_results, nuechtern))
        all_results.extend(validated_results)
