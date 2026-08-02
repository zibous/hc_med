"""API: /kpidata – KPI-Daten für das übergeordnete Dashboard."""

from fastapi import APIRouter

from app.infrastructure.database import get_db

router = APIRouter(prefix="/api", tags=["labor"])


@router.get("/kpidata")
async def kpidata():
    """KPI-Daten für das übergeordnete Dashboard (shared/dbo)."""
    conn = get_db()
    try:
        total = conn.execute("SELECT COUNT(*) FROM laborwerte").fetchone()[0]
        pathologisch = conn.execute("SELECT COUNT(*) FROM laborwerte WHERE flag IN ('H','L')").fetchone()[0]
        letztes = conn.execute("SELECT MAX(datum) FROM laborwerte").fetchone()[0]
        befunde = conn.execute("SELECT COUNT(*) FROM befunde").fetchone()[0]
        gruppen = conn.execute("SELECT COUNT(DISTINCT gruppe) FROM laborwerte").fetchone()[0]

        # Messungen pro Jahr für Barchart (letzte 7 Jahre)
        jahres_werte = conn.execute("""
            SELECT substr(datum,1,4) as jahr, COUNT(*) as n
            FROM laborwerte
            GROUP BY jahr ORDER BY jahr DESC LIMIT 7
        """).fetchall()
        bar_values = [r["n"] for r in reversed(jahres_werte)]

        return {
            "app_name": "Laborwerte",
            "icon": "fitness_center",
            "status": "ok",
            "hero": {
                "value": str(total),
                "unit": "Messwerte",
                "label": f"{befunde} Befunde · {pathologisch} auffällig",
            },
            "metrics": [
                {"label": "Befunde", "value": str(befunde), "unit": ""},
                {"label": "Auffällig", "value": str(pathologisch), "unit": ""},
                {"label": "Gruppen", "value": str(gruppen), "unit": ""},
            ],
            "detail": f"Letzter Befund: {letztes or '–'}",
            "indicator": {
                "type": "barchart",
                "values": bar_values,
                "label": "Messungen / Jahr",
                "period": "7 Jahre",
            },
        }
    finally:
        conn.close()
