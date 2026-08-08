"""SQLite Datenbank-Zugriff – Multi-User über Cookie (hc_user).

Der aktive User wird per Middleware in einer ContextVar gesetzt.
Alle Aufrufe von get_db() nutzen automatisch den richtigen Pfad.
"""

import sqlite3
from contextvars import ContextVar
from pathlib import Path

from fastapi import HTTPException

DATA_ROOT = Path(__file__).resolve().parent.parent.parent / "data"
DEFAULT_USER = "peter"

# Context-Variable: wird pro Request in der Middleware gesetzt
_current_user: ContextVar[str] = ContextVar("current_user", default=DEFAULT_USER)


def set_current_user(user: str) -> None:
    """Setzt den aktiven User für den aktuellen Request-Kontext."""
    user_dir = DATA_ROOT / "user" / user
    if user_dir.is_dir():
        _current_user.set(user)
    else:
        _current_user.set(DEFAULT_USER)


def get_current_user() -> str:
    """Gibt den aktiven User zurück."""
    return _current_user.get()


def get_user_data_path() -> Path:
    """Gibt den Data-Pfad des aktiven Users zurück."""
    return DATA_ROOT / "user" / get_current_user()


def get_db() -> sqlite3.Connection:
    """Öffnet eine Verbindung zur Labor-Datenbank des aktiven Users."""
    user = get_current_user()
    db_path = DATA_ROOT / "user" / user / "labor.db"
    if not db_path.exists():
        raise HTTPException(status_code=503, detail=f"Datenbank nicht gefunden für User '{user}'")
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn
