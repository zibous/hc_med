"""API: /gesamtbericht – Umfassender druckoptimierter Laborbericht."""

from pathlib import Path

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.core.gesamtbericht_data import build_report_data
from app.infrastructure.database import get_db

router = APIRouter(prefix="/api", tags=["labor"])

TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


@router.get("/gesamtbericht", response_class=HTMLResponse)
async def gesamtbericht(
    request: Request,
    befunde: int = 0,
    von: str = Query("", description="Start-Jahr (YYYY)"),
    bis: str = Query("", description="End-Jahr (YYYY)"),
):
    """Rendert den umfassenden Laborbericht als druckoptimiertes HTML."""
    conn = get_db()
    try:
        data = build_report_data(conn, befunde_count=befunde, von=von, bis=bis)
        # Verfügbare Jahre für Dropdown
        jahre_rows = conn.execute(
            "SELECT DISTINCT substr(datum, 1, 4) AS jahr FROM laborwerte ORDER BY jahr DESC"
        ).fetchall()
        verfuegbare_jahre = [r["jahr"] for r in jahre_rows]

        return templates.TemplateResponse("gesamtbericht.html", {
            "request": request,
            "befunde_count": befunde,
            "von": von,
            "bis": bis,
            "verfuegbare_jahre": verfuegbare_jahre,
            **data,
        })
    finally:
        conn.close()
