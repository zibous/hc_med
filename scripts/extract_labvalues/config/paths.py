# config/paths.py
from pathlib import Path

def resolve_data_dir() -> Path:
    """
    Resolve the data directory as ../data relative to the scripts root.

    Assumes layout:
      /.../hc_med/
        data/
        scripts/
          extract_labvalues/
            config/
            main.py
    This returns /.../hc_med/data
    """
    # config file is at .../scripts/extract_labvalues/config
    config_dir = Path(__file__).parent            # .../scripts/extract_labvalues/config
    pkg_dir = config_dir.parent                   # .../scripts/extract_labvalues
    scripts_dir = pkg_dir.parent                  # .../scripts
    project_root = scripts_dir.parent             # .../hc_med

    data_dir = project_root / "data"
    return data_dir.resolve()

def get_paths(user_id: str) -> dict:
    data_dir = resolve_data_dir()
    user_dir = data_dir / "user" / user_id

    return {
        "data_dir": data_dir,
        "user": user_dir,
        "befunde": user_dir / "import",
        "output": user_dir / "laborwerte_gesamt.csv",
        "db": user_dir / "labor.db",
        "log": user_dir / "extract_labvalues.log",
    }
