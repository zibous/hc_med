"""API-Endpunkte für Laborwerte."""

import sqlite3
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api", tags=["labor"])

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "labor.db"
CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "labor_config.yaml"

# Konfiguration laden
_config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
GROUP_CONFIG = _config.get("gruppen", {})
TEST_DESCRIPTIONS = _config.get("tests", {})
EREIGNISSE = _config.get("ereignisse", [])
VERKNUEPFUNGEN = _config.get("verknuepfungen", [])

# Kompatibilitäts-Dicts aus der YAML-Struktur
GROUP_DESCRIPTIONS = {k: v.get("beschreibung", "").strip() for k, v in GROUP_CONFIG.items()}


def get_db() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise HTTPException(status_code=503, detail="Datenbank nicht gefunden")
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


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
                tests[t] = {"einheit": r["einheit_norm"], "normbereich": r["normbereich"], "werte": []}
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
        ratio = path_count / total if total > 0 else 0
        if ratio == 0:
            bewertung = "Alle Werte im Normbereich – keine Auffälligkeiten."
            bewertung_status = "gut"
        elif ratio < 0.1:
            bewertung = "Insgesamt gute Werte, vereinzelt leichte Abweichungen."
            bewertung_status = "gut"
        elif ratio < 0.25:
            bewertung = "Einige Werte leicht außerhalb der Norm – im Auge behalten."
            bewertung_status = "ok"
        elif ratio < 0.4:
            bewertung = "Mehrere Werte auffällig – beim nächsten Arztbesuch ansprechen."
            bewertung_status = "auffällig"
        else:
            bewertung = "Viele Werte außerhalb der Norm – ärztliche Abklärung empfohlen."
            bewertung_status = "kritisch"

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


@router.get("/trend/{test}")
async def trend(test: str):
    """Zeitreihe für einen einzelnen Test."""
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT datum, wert_norm, einheit_norm, normbereich, flag, alter_bei_messung
               FROM laborwerte WHERE test_standard=? ORDER BY datum""",
            (test,),
        ).fetchall()

        if not rows:
            raise HTTPException(status_code=404, detail=f"Test '{test}' nicht gefunden")

        # Ersten nicht-leeren Normbereich suchen
        normbereich = ""
        for r in rows:
            if r["normbereich"] and r["normbereich"].strip():
                normbereich = r["normbereich"]
                break

        # Relevante Ereignisse im Zeitraum der Messwerte
        datum_von = rows[0]["datum"]
        datum_bis = rows[-1]["datum"]
        relevante_ereignisse = [
            e for e in EREIGNISSE
            if e.get("von", "") <= datum_bis and e.get("bis", "") >= datum_von
        ]

        # Verwandte Verknüpfungen für diesen Test
        verwandte = [v["name"] for v in VERKNUEPFUNGEN if test in v.get("tests", [])]

        return {
            "test": test,
            "beschreibung": TEST_DESCRIPTIONS.get(test, ""),
            "einheit": rows[0]["einheit_norm"],
            "normbereich": normbereich,
            "werte": [dict(r) for r in rows],
            "ereignisse": relevante_ereignisse,
            "verknuepfungen": verwandte,
        }
    finally:
        conn.close()


@router.get("/tests")
async def list_tests():
    """Alle verfügbaren Tests."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT DISTINCT test_standard, gruppe FROM laborwerte ORDER BY gruppe, test_standard"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


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
            "tests": result_tests,
            "ereignisse": EREIGNISSE,
        }
    finally:
        conn.close()


@router.get("/kpidata")
async def kpidata():
    """KPI-Daten für das übergeordnete Dashboard (shared/dbo)."""
    conn = get_db()
    try:
        total = conn.execute("SELECT COUNT(*) FROM laborwerte").fetchone()[0]
        pathologisch = conn.execute("SELECT COUNT(*) FROM laborwerte WHERE flag IN ('H','L')").fetchone()[0]
        letztes = conn.execute("SELECT MAX(datum) FROM laborwerte").fetchone()[0]
        befunde = conn.execute("SELECT COUNT(*) FROM befunde").fetchone()[0]
        gruppen = conn.execute("SELECT COUNT(DISTINCT gruppe) FROM laborwerte").fetchone()[0]

        # Messungen pro Jahr für Barchart (letzte 7 Jahre)
        jahres_werte = conn.execute("""
            SELECT substr(datum,1,4) as jahr, COUNT(*) as n
            FROM laborwerte
            GROUP BY jahr ORDER BY jahr DESC LIMIT 7
        """).fetchall()
        bar_values = [r["n"] for r in reversed(jahres_werte)]

        return {
            "app_name": "Laborwerte",
            "icon": "fitness_center",
            "status": "ok",
            "hero": {
                "value": str(total),
                "unit": "Messwerte",
                "label": f"{befunde} Befunde · {pathologisch} auffällig",
            },
            "metrics": [
                {"label": "Befunde", "value": str(befunde), "unit": ""},
                {"label": "Auffällig", "value": str(pathologisch), "unit": ""},
                {"label": "Gruppen", "value": str(gruppen), "unit": ""},
            ],
            "detail": f"Letzter Befund: {letztes or '–'}",
            "indicator": {
                "type": "barchart",
                "values": bar_values,
                "label": "Messungen / Jahr",
                "period": "7 Jahre",
            },
        }
    finally:
        conn.close()


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
                "wert_norm": r["wert_norm"],
                "einheit_norm": r["einheit_norm"],
                "normbereich": r["normbereich"],
                "flag": r["flag"],
                "anzahl": r["anzahl"],
            })

        return results
    finally:
        conn.close()
