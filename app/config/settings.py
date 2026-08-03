"""Zentrale Konfiguration – lädt labor_config.yaml."""

from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "labor_config.yaml"

_config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))

GROUP_CONFIG = _config.get("gruppen", {})
TEST_DESCRIPTIONS = _config.get("tests", {})
EREIGNISSE = _config.get("ereignisse", [])
VERKNUEPFUNGEN = _config.get("verknuepfungen", [])
PATIENT_CONFIG = _config.get("patient", {})
EMPFEHLUNGEN_TESTS = _config.get("empfehlungen_tests", {})
KURZNAMEN = _config.get("kurznamen", {})

GROUP_DESCRIPTIONS = {k: v.get("beschreibung", "").strip() for k, v in GROUP_CONFIG.items()}
