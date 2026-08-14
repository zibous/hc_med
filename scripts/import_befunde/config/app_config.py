import sys
import logging
from datetime import date
from pathlib import Path
import yaml


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Konfiguriert das zentrale Logging für die Pipeline."""
    logger = logging.getLogger("labor_pipeline")
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logger.level)

    # Kompaktes Format: nur Nachricht (wie bisherige print-Ausgaben)
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    return logger

class AppConfig:

    """Zentrale, moderne Konfigurationsverwaltung für die Labor-Pipeline."""
    
    def __init__(self):
        
        # 1. Pfade berechnen
        self.CONFIG_DIR = Path(__file__).parent
        self.PROJECT_DIR = self.CONFIG_DIR.parent
        self.ROOT_DIR = self.PROJECT_DIR.parent.parent
        self.DATA_DIR = self.ROOT_DIR / "data"
        
        # 2. Modus & User bestimmen
        self.test_mode = "--test" in sys.argv
        args = [arg for arg in sys.argv[1:] if arg not in ("--test", "--debug", "--quiet")]
        self.user_id = args[0] if args else "peter"

        # 3. Logging konfigurieren (--debug → DEBUG, --quiet → WARNING, default → INFO)
        if "--debug" in sys.argv:
            log_level = "DEBUG"
        elif "--quiet" in sys.argv:
            log_level = "WARNING"
        else:
            log_level = "INFO"
        self.log = setup_logging(log_level)

        # 3. Dynamische User-Pfade festlegen
        self.USER_DIR = self.DATA_DIR / "user" / self.user_id
        self.BEFUNDE_DIR = self.USER_DIR / "import"
        
        suffix = "_test" if self.test_mode else ""
        self.OUTPUT_FILE = self.USER_DIR / f"laborwerte_gesamt{suffix}.csv"
        self.DB_FILE = self.USER_DIR / f"labor{suffix}.db"
        
        # 4. User-Stammdaten laden
        userlist_path = self.DATA_DIR / "userlist.yaml"
        userlist = self._load_yaml(userlist_path)
        self._patient = userlist.get("patient", {}).get(self.user_id, {})
        
        if not self._patient:
            self.log.error(f"User '{self.user_id}' nicht in userlist.yaml gefunden")
            self.log.error(f"   Verfügbar: {', '.join(userlist.get('patient', {}).keys())}")
            sys.exit(1)
            
        self.PATIENT_GEBURTSDATUM = date(*[int(x) for x in self._patient.get("geburtsdatum", "1960-01-01").split("-")])
        self.PATIENT_GESCHLECHT = self._patient.get("geschlecht", "m")
        self.HAS_SCALE_DB = bool(self._patient.get("scaledb", "").strip().replace('"', ''))

        # 5. Pipeline-Konfigurationen aus YAMLs laden & flachklopfen
        self._load_pipeline_configs()

    def _load_yaml(self, path: Path) -> dict:
        """Hilfsfunktion zum sicheren Laden von YAML-Dateien."""
        if not path.exists():
            return {}
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    def _load_pipeline_configs(self):
        # A) Einheiten, Normbereiche & Konversionen (units_neu.yaml = Haupt-Quelle)
        units_cfg = self._load_yaml(self.CONFIG_DIR / "units_neu.yaml")
        self.STANDARD_UNITS = units_cfg.get("standard_units", {})
        self.UNIT_CONVERSIONS = {
            (item["von_einheit"].strip().lower(), item["test_standard"]): (item["ziel_einheit"], float(item["faktor"]))
            for item in units_cfg.get("unit_conversions", [])
        }

        # Normbereiche: geschlechtsspezifisch auflösen
        # Struktur: { allgemein: {...}, maennlich: {...}, weiblich: {...} }
        # → Flachklopfen zu einem Dict, geschlechtsspezifisch überschreibt allgemein
        ranges_raw = units_cfg.get("standard_ranges", {})
        geschlecht_key = "maennlich" if self.PATIENT_GESCHLECHT == "m" else "weiblich"
        self.STANDARD_RANGES = {}
        self.STANDARD_RANGES.update(ranges_raw.get("allgemein", {}))
        self.STANDARD_RANGES.update(ranges_raw.get(geschlecht_key, {}))

        # B) Test-Aliase (Flachklopfen der Kategorien)
        aliases_yaml = self._load_yaml(self.CONFIG_DIR / "testnamen.yaml").get("test_aliases_by_category", {})
        self.TEST_ALIASES = {
            alias: std_name
            for cat_dict in aliases_yaml.values()
            for std_name, aliases in cat_dict.items()
            for alias in aliases
        }

        # C) Gruppen-Regeln (Flachklopfen mit .lower().strip())
        groups_yaml = self._load_yaml(self.CONFIG_DIR / "groups.yaml").get("group_rules_by_category", {})
        self.GROUP_RULES = [
            (pattern.lower().strip(), category)
            for category, patterns in groups_yaml.items()
            for pattern in patterns
        ]

        # D) Plausibilitäts-Grenzwerte
        self.PLAUSIBLE_RANGES = self._load_yaml(self.CONFIG_DIR / "ranges.yaml").get("plausible_ranges", {})

        # E) Text- & Norm-Filter
        filters_yaml = self._load_yaml(self.CONFIG_DIR / "filters.yaml").get("pipeline_filters", {})
        self.PIPELINE_BLACKLIST = set(filters_yaml.get("blacklist", []))
        self.KOERPERDATEN_BLACKLIST = set(filters_yaml.get("koerperdaten_blacklist", []))
        self.INVALID_NORMS = set(filters_yaml.get("invalid_norms", []))


# Instanziiere das Konfigurations-Objekt direkt beim Import
config = AppConfig()
