"""SQLite Datenbank-Zugriff."""

import sqlite3
from pathlib import Path

from fastapi import HTTPException

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "labor.db"


def get_db() -> sqlite3.Connection:
    """Öffnet eine Verbindung zur Labor-Datenbank."""
    if not DB_PATH.exists():
        raise HTTPException(status_code=503, detail="Datenbank nicht gefunden")
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn
