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
async def gesamtbericht(request: Request, period: str = "1y"):
    """Rendert den umfassenden Laborbericht als druckoptimiertes HTML."""
    conn = get_db()
    try:
        data = build_report_data(conn, period=period)
        return templates.TemplateResponse("gesamtbericht.html", {
            "request": request,
            "period": period,
            **data,
        })
    finally:
        conn.close()
