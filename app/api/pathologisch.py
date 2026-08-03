"""API: /pathologisch – Auffällige Werte pro Test im Zeitraum."""

from fastapi import APIRouter

from app.config.settings import KURZNAMEN
from app.infrastructure.database import get_db

router = APIRouter(prefix="/api", tags=["labor"])


@router.get("/pathologisch")
async def pathologisch(period: str = "all"):
    """Auffällige Werte – nur der schlechteste Wert pro Test im Zeitraum."""
    conn = get_db()
    try:
        query = """
            SELECT l.datum, l.gruppe, l.test_standard, l.wert_norm, l.einheit_norm, l.normbereich, l.flag,
                   (SELECT COUNT(*) FROM laborwerte l2 
                    WHERE l2.test_standard = l.test_standard AND l2.flag = l.flag
        """

        if period == "1m":
            query += " AND l2.datum >= date('now', '-1 month')"
        elif period == "6m":
            query += " AND l2.datum >= date('now', '-6 months')"
        elif period == "1y":
            query += " AND l2.datum >= date('now', '-1 year')"

        query += """) as anzahl
            FROM laborwerte l
            WHERE l.flag IN ('H', 'L')
        """

        if period == "1m":
            query += " AND l.datum >= date('now', '-1 month')"
        elif period == "6m":
            query += " AND l.datum >= date('now', '-6 months')"
        elif period == "1y":
            query += " AND l.datum >= date('now', '-1 year')"

        # Letzter Wert pro Test+Flag
        query += """
            AND l.datum = (
                SELECT MAX(l3.datum) FROM laborwerte l3 
                WHERE l3.test_standard = l.test_standard AND l3.flag = l.flag
        """
        if period == "1m":
            query += " AND l3.datum >= date('now', '-1 month')"
        elif period == "6m":
            query += " AND l3.datum >= date('now', '-6 months')"
        elif period == "1y":
            query += " AND l3.datum >= date('now', '-1 year')"

        query += """
            )
            GROUP BY l.test_standard, l.flag
            ORDER BY l.datum DESC, l.gruppe
        """

        rows = conn.execute(query).fetchall()

        # Pro Test den letzten auffälligen Wert + Anzahl
        results = []
        for r in rows:
            results.append({
                "datum": r["datum"],
                "gruppe": r["gruppe"],
                "test_standard": r["test_standard"],
                "kurzname": KURZNAMEN.get(r["test_standard"], ""),
                "wert_norm": r["wert_norm"],
                "einheit_norm": r["einheit_norm"],
                "normbereich": r["normbereich"],
                "flag": r["flag"],
                "anzahl": r["anzahl"],
            })

        return results
    finally:
        conn.close()
