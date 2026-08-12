"""API: /verknuepfungen und /verknuepfung/{name} – Verknüpfungs-Ansichten."""

import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config.settings import VERKNUEPFUNGEN, get_patient_config, get_ereignisse
from app.core.empfehlungen import generate_verknuepfung_empfehlung
from app.infrastructure.database import get_db

router = APIRouter(prefix="/api", tags=["labor"])

TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


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
        elif vk["name"] == "Stoffwechsel-Risiko":
            gefaess_score = _berechne_stoffwechsel_details(result_tests)

        return {
            "name": vk["name"],
            "beschreibung": vk.get("beschreibung", ""),
            "empfehlung": empfehlung,
            "gefaess_score": gefaess_score,
            "tests": result_tests,
            "ereignisse": get_ereignisse(),
        }
    finally:
        conn.close()


@router.get("/verknuepfung/{name}/print", response_class=HTMLResponse)
async def verknuepfung_print(request: Request, name: str):
    """Druckoptimierte Version einer Verknüpfung (Light-Mode, eigene Seite)."""
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
        gefaess_score = None
        if vk["name"] == "Gefäßgesundheit":
            gefaess_score = _berechne_gefaess_details(result_tests)
        elif vk["name"] == "Stoffwechsel-Risiko":
            gefaess_score = _berechne_stoffwechsel_details(result_tests)

        return templates.TemplateResponse("verknuepfung_print.html", {
            "request": request,
            "name": vk["name"],
            "beschreibung": vk.get("beschreibung", ""),
            "empfehlung": empfehlung,
            "gefaess_score": gefaess_score,
            "tests_json": json.dumps(result_tests, ensure_ascii=False),
            "patient": get_patient_config(),
            "now": datetime.now().strftime("%d.%m.%Y"),
        })
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


def _berechne_stoffwechsel_details(tests: dict) -> dict:
    """Berechnet Stoffwechsel-Risiko-Score mit Einzelfaktoren."""
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
    max_score = 10

    # Übergewicht: BMI > 30 oder Fettgehalt > 25%
    gewicht = get_last_val("Gewicht")
    fett = get_last_val("Fettgehalt")
    if fett is not None:
        aktiv = fett > 25
        if aktiv:
            score += 1
        faktoren.append({"name": "Fettgehalt", "wert": f"{fett:.1f}%", "punkte": 1 if aktiv else 0, "max": 1, "aktiv": aktiv})
    elif gewicht is not None:
        # Fallback: Gewicht ohne Fettgehalt (grobe Schätzung BMI > 30 ≈ > 95kg bei 1.78m)
        aktiv = gewicht > 95
        if aktiv:
            score += 1
        faktoren.append({"name": "Gewicht", "wert": f"{gewicht:.0f} kg", "punkte": 1 if aktiv else 0, "max": 1, "aktiv": aktiv})

    # HbA1c: > 5.7% = Prädiabetes (2 Punkte bei > 6.0%)
    hba1c = get_last_val("HbA1c")
    if hba1c is not None:
        if hba1c > 6.0:
            punkte = 2
        elif hba1c > 5.7:
            punkte = 1
        else:
            punkte = 0
        score += punkte
        faktoren.append({"name": "HbA1c", "wert": f"{hba1c:.1f}%", "punkte": punkte, "max": 2, "aktiv": punkte > 0})

    # Glucose: > 100 nüchtern = auffällig
    glucose = get_last_val("Glucose")
    if glucose is not None:
        aktiv = glucose > 100
        if aktiv:
            score += 1
        faktoren.append({"name": "Glucose", "wert": f"{glucose:.0f}", "punkte": 1 if aktiv else 0, "max": 1, "aktiv": aktiv})

    # Triglyceride: > 150 = metabolisches Syndrom (2 Punkte bei > 200)
    trig = get_last_val("Triglyceride")
    if trig is not None:
        if trig > 200:
            punkte = 2
        elif trig > 150:
            punkte = 1
        else:
            punkte = 0
        score += punkte
        faktoren.append({"name": "Triglyceride", "wert": f"{trig:.0f}", "punkte": punkte, "max": 2, "aktiv": punkte > 0})

    # Harnsäure: > 7.0 = Gichtrisiko
    hs = get_last_val("Harnsäure")
    if hs is not None:
        aktiv = hs > 7.0
        if aktiv:
            score += 1
        faktoren.append({"name": "Harnsäure", "wert": f"{hs:.1f}", "punkte": 1 if aktiv else 0, "max": 1, "aktiv": aktiv})

    # GGT: > 60 = Leber-Stoffwechsel belastet
    ggt = get_last_val("GGT")
    if ggt is not None:
        aktiv = ggt > 60
        if aktiv:
            score += 1
        faktoren.append({"name": "GGT", "wert": f"{ggt:.0f}", "punkte": 1 if aktiv else 0, "max": 1, "aktiv": aktiv})

    # GPT: > 50 = Leberzellschaden
    gpt = get_last_val("GPT")
    if gpt is not None:
        aktiv = gpt > 50
        if aktiv:
            score += 1
        faktoren.append({"name": "GPT", "wert": f"{gpt:.0f}", "punkte": 1 if aktiv else 0, "max": 1, "aktiv": aktiv})

    # GOT: > 50 = Leberzellschaden
    got = get_last_val("GOT")
    if got is not None:
        aktiv = got > 50
        if aktiv:
            score += 1
        faktoren.append({"name": "GOT", "wert": f"{got:.0f}", "punkte": 1 if aktiv else 0, "max": 1, "aktiv": aktiv})

    return {"score": score, "max": max_score, "faktoren": faktoren}
