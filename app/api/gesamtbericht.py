"""API: /gesamtbericht – Umfassender druckoptimierter Laborbericht."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.core.gesamtbericht_data import build_report_data
from app.infrastructure.database import get_db

router = APIRouter(prefix="/api", tags=["labor"])

TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


@router.get("/gesamtbericht", response_class=HTMLResponse)
async def gesamtbericht(request: Request, befunde: int = 2):
    """Rendert den umfassenden Laborbericht als druckoptimiertes HTML.
    
    Args:
        befunde: Anzahl der letzten Befunde die berücksichtigt werden (1, 2, 3, oder 0=alle).
    """
    conn = get_db()
    try:
        data = build_report_data(conn, befunde_count=befunde)
        return templates.TemplateResponse("gesamtbericht.html", {
            "request": request,
            "befunde_count": befunde,
            **data,
        })
    finally:
        conn.close()
