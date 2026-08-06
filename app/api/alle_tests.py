"""API: /alle-tests – Alle Laborwerte als sortierbare Tabelle mit Jahres-Filter."""

from fastapi import APIRouter, Query

from app.config.settings import KURZNAMEN
from app.infrastructure.database import get_db

router = APIRouter(prefix="/api", tags=["labor"])


@router.get("/alle-tests")
async def get_alle_tests(
    von: str = Query("", description="Start-Jahr (YYYY), leer = ab Anfang"),
    bis: str = Query("", description="End-Jahr (YYYY), leer = bis heute"),
):
    """Gibt eine Detail-Tabelle aller Tests zurück, gefiltert nach Jahr-Bereich."""
    conn = get_db()
    try:
        # Verfügbare Jahre
        jahre_rows = conn.execute(
            "SELECT DISTINCT substr(datum, 1, 4) AS jahr FROM laborwerte ORDER BY jahr DESC"
        ).fetchall()
        verfuegbare_jahre = [r["jahr"] for r in jahre_rows]

        # Datum-Filter aufbauen
        datum_filter = ""
        params_filter = []

        if von and bis:
            datum_filter = " AND l2.datum >= ? AND l2.datum <= ?"
            params_filter = [f"{von}-01-01", f"{bis}-12-31"]
        elif von:
            datum_filter = " AND l2.datum >= ?"
            params_filter = [f"{von}-01-01"]
        elif bis:
            datum_filter = " AND l2.datum <= ?"
            params_filter = [f"{bis}-12-31"]

        # Letzter Wert pro Test im gewählten Zeitraum
        query = f"""
            SELECT l.test_standard, l.gruppe, l.wert_norm, l.einheit_norm, 
                   l.normbereich, l.flag, l.datum
            FROM laborwerte l
            WHERE l.datum = (
                SELECT MAX(l2.datum) FROM laborwerte l2 
                WHERE l2.test_standard = l.test_standard
                {datum_filter}
            )
            GROUP BY l.test_standard
            ORDER BY l.gruppe, l.test_standard
        """

        rows = conn.execute(query, params_filter).fetchall()

        result = []
        for row in rows:
            test = row["test_standard"]
            if not row["datum"]:
                continue

            # Vorwert
            vorwert_row = conn.execute(
                "SELECT wert_norm, datum FROM laborwerte WHERE test_standard=? AND datum < ? ORDER BY datum DESC LIMIT 1",
                (test, row["datum"]),
            ).fetchone()

            # Besten Normbereich für diesen Test finden (nicht nur vom letzten Wert)
            normbereich = (row["normbereich"] or "").strip()
            if not normbereich or not any(c.isdigit() for c in normbereich):
                norm_row = conn.execute(
                    """SELECT normbereich FROM laborwerte 
                       WHERE test_standard=? AND normbereich IS NOT NULL AND normbereich != ''
                       ORDER BY datum DESC""",
                    (test,),
                ).fetchall()
                for nr in norm_row:
                    nb = (nr["normbereich"] or "").strip()
                    if nb and any(c.isdigit() for c in nb):
                        normbereich = nb
                        break

            # Trend
            trend = ""
            try:
                val_akt = float(str(row["wert_norm"]).replace(",", ".").replace("<", "").replace(">", ""))
                if vorwert_row:
                    val_vor = float(str(vorwert_row["wert_norm"]).replace(",", ".").replace("<", "").replace(">", ""))
                    if val_vor != 0:
                        pct = round((val_akt - val_vor) / val_vor * 100)
                        if pct > 5:
                            trend = f"↑ +{pct}%"
                        elif pct < -5:
                            trend = f"↓ {pct}%"
                        else:
                            trend = "→ unverändert"
            except (ValueError, TypeError):
                pass

            # Gesamtanzahl
            total_count = conn.execute(
                "SELECT COUNT(*) FROM laborwerte WHERE test_standard=?",
                (test,),
            ).fetchone()[0]

            result.append({
                "test": test,
                "kurzname": KURZNAMEN.get(test, ""),
                "gruppe": row["gruppe"],
                "wert": row["wert_norm"],
                "einheit": row["einheit_norm"] or "",
                "flag": row["flag"] or "",
                "datum": row["datum"],
                "normbereich": normbereich,
                "vorwert": vorwert_row["wert_norm"] if vorwert_row else "",
                "vor_datum": vorwert_row["datum"] if vorwert_row else "",
                "trend": trend,
                "messungen": total_count,
            })

        return {
            "tests": result,
            "anzahl": len(result),
            "verfuegbare_jahre": verfuegbare_jahre,
            "von": von,
            "bis": bis,
        }
    finally:
        conn.close()
