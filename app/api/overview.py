"""API: /overview – Übersicht mit KPIs und Gruppen."""

from fastapi import APIRouter

from app.config.settings import GROUP_CONFIG, GROUP_DESCRIPTIONS
from app.infrastructure.database import get_db

router = APIRouter(prefix="/api", tags=["labor"])


@router.get("/overview")
async def overview():
    """Übersicht: KPIs + Gruppen mit Details."""
    conn = get_db()
    try:
        total = conn.execute("SELECT COUNT(*) FROM laborwerte").fetchone()[0]
        befunde = conn.execute("SELECT COUNT(*) FROM befunde").fetchone()[0]
        zeitraum = conn.execute("SELECT MIN(datum), MAX(datum) FROM laborwerte").fetchone()
        pathologisch = conn.execute("SELECT COUNT(*) FROM laborwerte WHERE flag IN ('H','L')").fetchone()[0]

        # Pro Gruppe: Anzahl, pathologische Werte, letzte Werte, Trend-Daten
        gruppen_raw = conn.execute("""
            SELECT gruppe, COUNT(*) as anzahl,
                   SUM(CASE WHEN flag IN ('H','L') THEN 1 ELSE 0 END) as path_count,
                   MAX(datum) as letztes_datum
            FROM laborwerte GROUP BY gruppe ORDER BY gruppe
        """).fetchall()

        gruppen = []
        for g in gruppen_raw:
            name = g["gruppe"]

            # Letzte 3 auffällige Tests dieser Gruppe
            letzte_path = conn.execute("""
                SELECT test_standard, wert_norm, einheit_norm, flag, datum
                FROM laborwerte
                WHERE gruppe=? AND flag IN ('H','L')
                ORDER BY datum DESC LIMIT 3
            """, (name,)).fetchall()

            # Trend: Anzahl Messungen pro Jahr für Sparkline
            jahres_trend = conn.execute("""
                SELECT substr(datum,1,4) as jahr, COUNT(*) as n
                FROM laborwerte WHERE gruppe=?
                GROUP BY jahr ORDER BY jahr
            """, (name,)).fetchall()

            # Bewertung: Anteil pathologischer Werte
            path_ratio = g["path_count"] / g["anzahl"] if g["anzahl"] > 0 else 0
            if path_ratio == 0:
                status = "gut"
            elif path_ratio < 0.15:
                status = "ok"
            elif path_ratio < 0.35:
                status = "auffällig"
            else:
                status = "kritisch"

            gc = GROUP_CONFIG.get(name, {})
            gruppen.append({
                "name": name,
                "beschreibung": GROUP_DESCRIPTIONS.get(name, ""),
                "icon": gc.get("icon", "📋"),
                "farbe": gc.get("farbe", "#64748b"),
                "anzahl": g["anzahl"],
                "pathologisch": g["path_count"],
                "status": status,
                "letztes_datum": g["letztes_datum"],
                "letzte_auffaellige": [dict(r) for r in letzte_path],
                "jahres_trend": [r["n"] for r in jahres_trend],
            })

        return {
            "kpis": {
                "messwerte": total,
                "befunde": befunde,
                "pathologisch": pathologisch,
                "zeitraum_von": zeitraum[0],
                "zeitraum_bis": zeitraum[1],
            },
            "gruppen": gruppen,
        }
    finally:
        conn.close()
