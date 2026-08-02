"""API: /tests – Alle verfügbaren Tests auflisten."""

from fastapi import APIRouter

from app.infrastructure.database import get_db

router = APIRouter(prefix="/api", tags=["labor"])


@router.get("/tests")
async def list_tests():
    """Alle verfügbaren Tests."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT DISTINCT test_standard, gruppe FROM laborwerte ORDER BY gruppe, test_standard"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
