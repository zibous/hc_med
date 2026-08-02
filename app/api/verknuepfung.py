"""API: /verknuepfungen und /verknuepfung/{name} – Verknüpfungs-Ansichten."""

from fastapi import APIRouter, HTTPException

from app.config.settings import EREIGNISSE, VERKNUEPFUNGEN
from app.core.empfehlungen import generate_verknuepfung_empfehlung
from app.infrastructure.database import get_db

router = APIRouter(prefix="/api", tags=["labor"])


@router.get("/verknuepfungen")
async def verknuepfungen_list():
    """Alle definierten Verknüpfungen."""
    return VERKNUEPFUNGEN


@router.get("/verknuepfung/{name}")
async def verknuepfung_detail(name: str):
    """Multi-Chart Daten für eine Verknüpfung."""
    # Verknüpfung finden
    vk = next((v for v in VERKNUEPFUNGEN if v["name"] == name), None)
    if not vk:
        raise HTTPException(status_code=404, detail=f"Verknüpfung '{name}' nicht gefunden")

    conn = get_db()
    try:
        result_tests = {}
        for test in vk["tests"]:
            rows = conn.execute(
                """SELECT datum, wert_norm, einheit_norm, normbereich, flag
                   FROM laborwerte WHERE test_standard=? ORDER BY datum""",
                (test,),
            ).fetchall()
            if rows:
                # Ersten nicht-leeren Normbereich
                norm = ""
                for r in rows:
                    if r["normbereich"] and r["normbereich"].strip():
                        norm = r["normbereich"]
                        break
                result_tests[test] = {
                    "einheit": rows[0]["einheit_norm"],
                    "normbereich": norm,
                    "werte": [{"datum": r["datum"], "wert": r["wert_norm"], "flag": r["flag"]} for r in rows],
                }

        return {
            "name": vk["name"],
            "beschreibung": vk.get("beschreibung", ""),
            "empfehlung": generate_verknuepfung_empfehlung(vk["name"], result_tests),
            "tests": result_tests,
            "ereignisse": EREIGNISSE,
        }
    finally:
        conn.close()
