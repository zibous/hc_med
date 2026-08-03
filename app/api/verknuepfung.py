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

        empfehlung = generate_verknuepfung_empfehlung(vk["name"], result_tests)

        # Gefäßgesundheit: Score-Daten separat mitliefern
        gefaess_score = None
        if vk["name"] == "Gefäßgesundheit":
            gefaess_score = _berechne_gefaess_details(result_tests)

        return {
            "name": vk["name"],
            "beschreibung": vk.get("beschreibung", ""),
            "empfehlung": empfehlung,
            "gefaess_score": gefaess_score,
            "tests": result_tests,
            "ereignisse": EREIGNISSE,
        }
    finally:
        conn.close()


def _berechne_gefaess_details(tests: dict) -> dict:
    """Berechnet Gefäßgesundheit-Score mit Einzelfaktoren."""
    def get_last_val(test_name):
        if test_name not in tests:
            return None
        werte = tests[test_name]["werte"]
        if not werte:
            return None
        try:
            return float(str(werte[-1]["wert"]).replace(",", ".").replace("<", "").replace(">", ""))
        except (ValueError, TypeError):
            return None

    faktoren = []
    score = 0
    max_score = 8

    trig = get_last_val("Triglyceride")
    if trig is not None:
        aktiv = trig > 200
        if aktiv:
            score += 2
        faktoren.append({"name": "Triglyceride", "wert": f"{trig:.0f}", "punkte": 2 if aktiv else 0, "max": 2, "aktiv": aktiv})

    crp = get_last_val("CRP")
    if crp is not None:
        aktiv = crp > 0.5
        if aktiv:
            score += 2
        faktoren.append({"name": "CRP", "wert": f"{crp:.2f}", "punkte": 2 if aktiv else 0, "max": 2, "aktiv": aktiv})

    hba1c = get_last_val("HbA1c")
    if hba1c is not None:
        aktiv = hba1c > 5.7
        if aktiv:
            score += 1
        faktoren.append({"name": "HbA1c", "wert": f"{hba1c:.1f}%", "punkte": 1 if aktiv else 0, "max": 1, "aktiv": aktiv})

    ldl = get_last_val("LDL")
    if ldl is not None:
        aktiv = ldl > 130
        if aktiv:
            score += 1
        faktoren.append({"name": "LDL", "wert": f"{ldl:.0f}", "punkte": 1 if aktiv else 0, "max": 1, "aktiv": aktiv})

    hs = get_last_val("Harnsäure")
    if hs is not None:
        aktiv = hs > 7.0
        if aktiv:
            score += 1
        faktoren.append({"name": "Harnsäure", "wert": f"{hs:.1f}", "punkte": 1 if aktiv else 0, "max": 1, "aktiv": aktiv})

    hdl = get_last_val("HDL")
    if hdl is not None:
        aktiv = hdl < 40
        if aktiv:
            score += 1
        faktoren.append({"name": "HDL", "wert": f"{hdl:.0f}", "punkte": 1 if aktiv else 0, "max": 1, "aktiv": aktiv})

    return {"score": score, "max": max_score, "faktoren": faktoren}
