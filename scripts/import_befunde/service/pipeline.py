"""Labor-Pipeline: Orchestriert Parsing, Normalisierung und Export."""

import logging
import re
from pathlib import Path

from config.app_config import config
from service.normalizer import LaborDataNormalizer
from service.unit_handler import UnitHandler
from service.norm_flags import NormFlagResolver
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

log = logging.getLogger("labor_pipeline")


class LaborDataPipeline:
    """Verarbeitet rohe Laborbefunde durch eine strukturierte Reinigungs-Pipeline."""

    # Parser-Registry: Format-String → Klasse
    PARSER_REGISTRY = {
        "simple_csv": SimpleCSVParser,
        "csv": CSVFormatParser,
        "pivot": PivotFormatParser,
        "table": TableFormatParser,
        "tab": TabFormatParser,
        "kuerzel_space": KuerzelSpaceParser,
        "pdf_text": PDFTextFormatParser,
    }

    def __init__(self):
        self.normalizer = LaborDataNormalizer()
        self.unit_handler = UnitHandler()
        self.norm_resolver = NormFlagResolver()
        self.age_calc = PatientAgeCalculator(config.PATIENT_GEBURTSDATUM)
        self.lipid_calc = LipidCalculator()
        self.csv_exporter = LaborCSVExporter()

        self.BLACKLIST = getattr(config, "PIPELINE_BLACKLIST", set())
        self.KOERPERDATEN_BLACKLIST = getattr(config, "KOERPERDATEN_BLACKLIST", set())

    # ──────────────────────────────────────────────────────────────────────────
    # ÖFFENTLICHE METHODE
    # ──────────────────────────────────────────────────────────────────────────
    def process_all_files(self, txt_files: list) -> tuple[list, list]:
        """Hauptmethode: Iteriert über alle Dateien und führt die Pipeline aus."""
        all_results = []
        file_results = []

        for filepath in txt_files:
            fmt = detect_format(filepath)
            file_text = filepath.read_text(encoding="utf-8", errors="replace")
            nuechtern = self._detect_nuechtern(file_text)

            results = self._parse_by_format(filepath, fmt)
            log.info(f"{filepath.name}  ->  {len(results)} Werte extrahiert")

            processed_rows = []
            for row in results:
                row["Nuechtern"] = nuechtern
                row = self._normalize_row(row)
                if self._is_valid_row(row):
                    processed_rows.append(row)

            # Normbereiche & Flags in separatem Durchlauf
            validated = self._finalize_rows(processed_rows)
            file_results.append((filepath.name, fmt, validated, nuechtern))
            all_results.extend(validated)

        all_results = self.lipid_calc.calculate_metrics(all_results)
        self.lipid_calc.print_summary()
        self.csv_exporter.export(all_results)

        return file_results, all_results

    # ──────────────────────────────────────────────────────────────────────────
    # PRIVATE: PARSING
    # ──────────────────────────────────────────────────────────────────────────
    def _detect_nuechtern(self, file_text: str) -> int:
        """Erkennt, ob der Befund nüchtern abgenommen wurde."""
        match = re.search(r"#\s*nüchtern\s*:\s*(nein|ja|no|yes)", file_text, re.IGNORECASE)
        if match and match.group(1).lower() in ("nein", "no"):
            return 0
        return 1

    def _parse_by_format(self, filepath: Path, fmt: str) -> list[dict]:
        """Dynamischer Parser-Wechsler basierend auf dem erkannten Format."""
        parser_class = self.PARSER_REGISTRY.get(fmt, FreeTextParser)
        return parser_class().parse(filepath)

    # ──────────────────────────────────────────────────────────────────────────
    # PRIVATE: NORMALISIERUNG PRO ZEILE
    # ──────────────────────────────────────────────────────────────────────────
    def _normalize_row(self, row: dict) -> dict:
        """Orchestriert die Normalisierung einer einzelnen Zeile."""
        # 1. Testname normalisieren
        row["Test_Standard"] = self.normalizer.normalize_test_name(row["Test"])

        # 2. Einheiten-Konversion & Auffüllung
        self.unit_handler.normalize_and_convert(row)
        self.unit_handler.fill_missing_standard_unit(row)

        # 3. Gruppe zuweisen
        if not row.get("Gruppe") or row.get("Gruppe") == "Sonstige":
            self.normalizer.assign_group(row)

        # 4. Medizinische Korrekturen
        self.normalizer.apply_medical_corrections(row)

        # 5. Alter berechnen
        age = self.age_calc.age_at(row["Datum"])
        row["Alter"] = str(age) if age else ""
        return row

    # ──────────────────────────────────────────────────────────────────────────
    # PRIVATE: FINALISIERUNG (EINHEIT_NORM, NORMBEREICH, FLAGS)
    # ──────────────────────────────────────────────────────────────────────────
    def _finalize_rows(self, rows: list[dict]) -> list[dict]:
        """Setzt Einheit_Norm, Normbereich und Flags für alle Zeilen."""
        for row in rows:
            self.unit_handler.resolve_einheit_norm(row)
            self.norm_resolver.resolve_normbereich(row)
            self.norm_resolver.calculate_flag(row)
        return rows

    # ──────────────────────────────────────────────────────────────────────────
    # PRIVATE: VALIDIERUNG
    # ──────────────────────────────────────────────────────────────────────────
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
