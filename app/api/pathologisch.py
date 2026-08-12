"""API: /pathologisch – Auffällige Werte pro Test im Zeitraum."""

from fastapi import APIRouter, Query

from app.config.settings import KURZNAMEN
from app.infrastructure.database import get_db

router = APIRouter(prefix="/api", tags=["labor"])


@router.get("/pathologisch")
async def pathologisch(
    von: str = Query("", description="Start-Jahr (YYYY)"),
    bis: str = Query("", description="End-Jahr (YYYY)"),
):
    """Auffällige Werte – letzter auffälliger Wert pro Test im Zeitraum."""
    conn = get_db()
    try:
        # Jahres-Filter aufbauen
        datum_filter = ""
        if von and bis:
            datum_filter = f" AND datum >= '{von}-01-01' AND datum <= '{bis}-12-31'"
        elif von:
            datum_filter = f" AND datum >= '{von}-01-01'"
        elif bis:
            datum_filter = f" AND datum <= '{bis}-12-31'"

        # Letzter Wert pro Test prüfen – nur anzeigen wenn der AKTUELLE Wert auffällig ist
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
                WHERE l3.test_standard = l.test_standard
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

        # Verfügbare Jahre
        jahre_rows = conn.execute(
            "SELECT DISTINCT substr(datum, 1, 4) AS jahr FROM laborwerte ORDER BY jahr DESC"
        ).fetchall()

        return {"items": results, "verfuegbare_jahre": [r["jahr"] for r in jahre_rows]}
    finally:
        conn.close()
