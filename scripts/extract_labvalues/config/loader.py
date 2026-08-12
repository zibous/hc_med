# config/loader.py
import yaml
import logging
from pathlib import Path

from .paths import resolve_data_dir

logger = logging.getLogger(__name__)

def load_yaml_optional(path: Path) -> dict:
    if not path.exists():
        logger.debug("Config file not found: %s", path)
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        logger.exception("Fehler beim Laden von YAML: %s", path)
        return {}

def load_config() -> tuple[dict, dict, Path]:
    """
    Returns (cfg, users, data_dir)
    - cfg: content of labor_config.yaml or {}
    - users: content of userlist.yaml or {}
    - data_dir: resolved Path to data directory
    """
    data_dir = resolve_data_dir()
    logger.info("Using data directory: %s", data_dir)

    config_path = data_dir / "labor_config.yaml"
    userlist_path = data_dir / "userlist.yaml"

    cfg = load_yaml_optional(config_path)
    users = load_yaml_optional(userlist_path)

    if not users:
        logger.warning("userlist.yaml is empty or missing in %s. Please create %s", data_dir, userlist_path)

    return cfg, users, data_dir
