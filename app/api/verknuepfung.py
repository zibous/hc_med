"""API: /verknuepfungen und /verknuepfung/{name} – Verknüpfungs-Ansichten."""

import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config.settings import VERKNUEPFUNGEN, get_patient_config, get_ereignisse
from app.core.empfehlungen import generate_verknuepfung_empfehlung
from app.core.gesamtbericht_data import (
    berechne_gefaess_score,
    berechne_stoffwechsel_score,
)
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
        raise HTTPException(
            status_code=404, detail=f"Verknüpfung '{name}' nicht gefunden"
        )

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
                    "werte": [
                        {"datum": r["datum"], "wert": r["wert_norm"], "flag": r["flag"]}
                        for r in rows
                    ],
                }

        # Körperdaten auf Labortermine beschränken:
        # Wenn ein Test >3x so viele Datenpunkte hat wie der Median der anderen,
        # wird er auf die Termine der anderen Tests gefiltert (nächstgelegener Wert).
        if len(result_tests) >= 2:
            counts = {t: len(d["werte"]) for t, d in result_tests.items()}
            sorted_counts = sorted(counts.values())
            median_count = sorted_counts[len(sorted_counts) // 2]

            if median_count > 0:
                # Sammle alle Termine der "normalen" Tests (wenige Datenpunkte)
                reference_dates = set()
                for t, d in result_tests.items():
                    if counts[t] <= median_count * 3:
                        for w in d["werte"]:
                            reference_dates.add(w["datum"])
                reference_dates = sorted(reference_dates)

                # Tests mit zu vielen Datenpunkten auf nächstgelegene Labortermine filtern
                if reference_dates:
                    for t in list(result_tests.keys()):
                        if counts[t] > median_count * 3:
                            result_tests[t]["werte"] = _filter_to_nearest(
                                result_tests[t]["werte"], reference_dates
                            )

        empfehlung = generate_verknuepfung_empfehlung(vk["name"], result_tests)

        # Gefäßgesundheit/Stoffwechsel: zentrale Score-Berechnung
        gefaess_score = None
        if vk["name"] == "Gefäßgesundheit":
            gefaess_score = berechne_gefaess_score(conn)
        elif vk["name"] == "Stoffwechsel-Risiko":
            gefaess_score = berechne_stoffwechsel_score(conn)

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


def _filter_to_nearest(werte: list[dict], reference_dates: list[str]) -> list[dict]:
    """Filtert eine Werteliste auf die jeweils nächstgelegenen Referenz-Termine.

    Für jeden Referenz-Termin wird der Wert mit dem geringsten Datumsabstand gewählt
    (maximal 90 Tage Abstand).
    """
    if not werte or not reference_dates:
        return werte

    filtered = []
    used_indices = set()

    for ref_date in reference_dates:
        best_idx = None
        best_diff = None
        for i, w in enumerate(werte):
            if i in used_indices:
                continue
            try:
                diff = abs(
                    (
                        datetime.strptime(w["datum"], "%Y-%m-%d")
                        - datetime.strptime(ref_date, "%Y-%m-%d")
                    ).days
                )
            except ValueError:
                continue
            if best_diff is None or diff < best_diff:
                best_diff = diff
                best_idx = i
        # Maximal 90 Tage Abstand
        if best_idx is not None and best_diff <= 90:
            filtered.append(werte[best_idx])
            used_indices.add(best_idx)

    return filtered


@router.get("/verknuepfung/{name}/print", response_class=HTMLResponse)
async def verknuepfung_print(request: Request, name: str):
    """Druckoptimierte Version einer Verknüpfung (Light-Mode, eigene Seite)."""
    vk = next((v for v in VERKNUEPFUNGEN if v["name"] == name), None)
    if not vk:
        raise HTTPException(
            status_code=404, detail=f"Verknüpfung '{name}' nicht gefunden"
        )

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
                    "werte": [
                        {"datum": r["datum"], "wert": r["wert_norm"], "flag": r["flag"]}
                        for r in rows
                    ],
                }

        empfehlung = generate_verknuepfung_empfehlung(vk["name"], result_tests)
        gefaess_score = None
        if vk["name"] == "Gefäßgesundheit":
            gefaess_score = berechne_gefaess_score(conn)
        elif vk["name"] == "Stoffwechsel-Risiko":
            gefaess_score = berechne_stoffwechsel_score(conn)

        return templates.TemplateResponse(
            "verknuepfung_print.html",
            {
                "request": request,
                "name": vk["name"],
                "beschreibung": vk.get("beschreibung", ""),
                "empfehlung": empfehlung,
                "gefaess_score": gefaess_score,
                "tests_json": json.dumps(result_tests, ensure_ascii=False),
                "patient": get_patient_config(),
                "now": datetime.now().strftime("%d.%m.%Y"),
            },
        )
    finally:
        conn.close()
