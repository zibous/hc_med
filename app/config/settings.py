"""Zentrale Konfiguration – lädt labor_config.yaml."""

from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "labor_config.yaml"
DATA_ROOT = Path(__file__).resolve().parent.parent.parent / "data"

_config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))

GROUP_CONFIG = _config.get("gruppen", {})
TEST_DESCRIPTIONS = _config.get("tests", {})
VERKNUEPFUNGEN = _config.get("verknuepfungen", [])
PATIENT_CONFIG = _config.get("patient", {})  # Fallback – wird dynamisch überschrieben
EMPFEHLUNGEN_TESTS = _config.get("empfehlungen_tests", {})
KURZNAMEN = _config.get("kurznamen", {})
NUECHTERN_SENSITIV = _config.get("nuechtern_sensitiv", [])

GROUP_DESCRIPTIONS = {k: v.get("beschreibung", "").strip() for k, v in GROUP_CONFIG.items()}


def _load_user_config() -> dict:
    """Lädt die user-spezifische config.yaml."""
    from app.infrastructure.database import get_current_user
    user_config_path = DATA_ROOT / "user" / get_current_user() / "config.yaml"
    if not user_config_path.exists():
        return {}
    return yaml.safe_load(user_config_path.read_text(encoding="utf-8")) or {}


def get_ereignisse() -> list:
    """Gibt die Ereignisse des aktiven Users zurück."""
    return _load_user_config().get("ereignisse", [])


def get_gesamtbericht_bemerkung() -> str:
    """Gibt die Gesamtbericht-Bemerkung des aktiven Users zurück."""
    return _load_user_config().get("gesamtbericht_bemerkung", "")


def get_patient_config() -> dict:
    """Gibt die Patientendaten des aktiven Users zurück (dynamisch aus userlist.yaml)."""
    from app.infrastructure.database import get_current_user

    userlist_path = DATA_ROOT / "userlist.yaml"
    if not userlist_path.exists():
        return PATIENT_CONFIG  # Fallback
    data = yaml.safe_load(userlist_path.read_text(encoding="utf-8")) or {}
    patients = data.get("patient", {})
    return patients.get(get_current_user(), PATIENT_CONFIG)
