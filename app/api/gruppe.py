"""API: /gruppe/{gruppe} – Detail-Ansicht einer Laborgruppe."""

from fastapi import APIRouter, HTTPException

from app.config.settings import GROUP_DESCRIPTIONS, TEST_DESCRIPTIONS, KURZNAMEN
from app.core.bewertung import bewerte_gruppe
from app.infrastructure.database import get_db

router = APIRouter(prefix="/api", tags=["labor"])


@router.get("/gruppe/{gruppe}")
async def gruppe_detail(gruppe: str):
    """Alle Tests einer Gruppe mit Zeitreihen + KPIs."""
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT datum, test_standard, wert_norm, einheit_norm, normbereich, flag, alter_bei_messung
               FROM laborwerte WHERE gruppe=? ORDER BY test_standard, datum""",
            (gruppe,),
        ).fetchall()

        if not rows:
            raise HTTPException(status_code=404, detail=f"Gruppe '{gruppe}' nicht gefunden")

        # Gruppieren nach Test
        tests: dict = {}
        total = 0
        path_count = 0
        for r in rows:
            t = r["test_standard"]
            if t not in tests:
                tests[t] = {
                    "einheit": r["einheit_norm"],
                    "normbereich": "",
                    "beschreibung": TEST_DESCRIPTIONS.get(t, ""),
                    "kurzname": KURZNAMEN.get(t, ""),
                    "werte": [],
                }
            # Ersten nicht-leeren, gültigen Normbereich übernehmen
            if not tests[t]["normbereich"]:
                nb = (r["normbereich"] or "").strip()
                if nb and any(c.isdigit() for c in nb):
                    tests[t]["normbereich"] = nb
            tests[t]["werte"].append({
                "datum": r["datum"],
                "wert": r["wert_norm"],
                "flag": r["flag"],
                "alter": r["alter_bei_messung"],
            })
            total += 1
            if r["flag"] in ("H", "L"):
                path_count += 1

        # Bewertung
        ok_count = total - path_count
        bewertung, bewertung_status = bewerte_gruppe(ok_count, path_count, total)

        return {
            "gruppe": gruppe,
            "beschreibung": GROUP_DESCRIPTIONS.get(gruppe, ""),
            "kpis": {
                "ok": ok_count,
                "auffaellig": path_count,
                "gesamt": total,
                "bewertung": bewertung,
                "bewertung_status": bewertung_status,
            },
            "tests": tests,
        }
    finally:
        conn.close()
