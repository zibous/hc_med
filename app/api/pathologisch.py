"""API: /pathologisch – Auffällige Werte pro Test im Zeitraum."""

from fastapi import APIRouter

from app.config.settings import KURZNAMEN
from app.infrastructure.database import get_db

router = APIRouter(prefix="/api", tags=["labor"])


@router.get("/pathologisch")
async def pathologisch(befunde: int = 0):
    """Auffällige Werte – letzter auffälliger Wert pro Test im Zeitraum."""
    conn = get_db()
    try:
        # Befunde-basierter Filter
        datum_filter = ""
        if befunde > 0:
            befund_rows = conn.execute(
                "SELECT DISTINCT datum FROM befunde ORDER BY datum DESC LIMIT ?",
                (befunde,)
            ).fetchall()
            if befund_rows:
                aeltestes_datum = befund_rows[-1]["datum"]
                datum_filter = f" AND datum >= '{aeltestes_datum}'"

        # Letzter auffälliger Wert pro Test (unabhängig von Flag-Richtung)
        query = f"""
            SELECT l.datum, l.gruppe, l.test_standard, l.wert_norm, l.einheit_norm, l.normbereich, l.flag,
                   (SELECT COUNT(*) FROM laborwerte l2 
                    WHERE l2.test_standard = l.test_standard AND l2.flag IN ('H','L')
                    {datum_filter}) as anzahl
            FROM laborwerte l
            WHERE l.flag IN ('H', 'L')
            {datum_filter}
            AND l.datum = (
                SELECT MAX(l3.datum) FROM laborwerte l3 
                WHERE l3.test_standard = l.test_standard AND l3.flag IN ('H','L')
                {datum_filter}
            )
            GROUP BY l.test_standard
            ORDER BY l.datum DESC, l.gruppe
        """

        rows = conn.execute(query).fetchall()

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
