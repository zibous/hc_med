"""API-Endpunkte für Laborwerte."""

import sqlite3
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse

router = APIRouter(prefix="/api", tags=["labor"])

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "labor.db"
CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "labor_config.yaml"

# Konfiguration laden
_config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
GROUP_CONFIG = _config.get("gruppen", {})
TEST_DESCRIPTIONS = _config.get("tests", {})
EREIGNISSE = _config.get("ereignisse", [])
VERKNUEPFUNGEN = _config.get("verknuepfungen", [])
PATIENT_CONFIG = _config.get("patient", {})
EMPFEHLUNGEN_TESTS = _config.get("empfehlungen_tests", {})

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
                tests[t] = {
                    "einheit": r["einheit_norm"],
                    "normbereich": r["normbereich"],
                    "beschreibung": TEST_DESCRIPTIONS.get(t, ""),
                    "werte": [],
                }
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


def _get_test_empfehlung(test: str, last_val: str, last_flag: str, norm: str, conn) -> str:
    """Generiert eine test-spezifische Empfehlung für die Trend-Ansicht."""
    if not last_flag:
        return ""

    try:
        val = float(str(last_val).replace(",", ".").replace("<", "").replace(">", ""))
    except (ValueError, TypeError):
        return ""

    # Statische Empfehlung aus YAML laden
    emp_config = _config.get("empfehlungen_tests", {}).get(test, {})
    static_text = emp_config.get("text", "")
    is_dynamic = emp_config.get("dynamisch", False)

    # Bedingung prüfen (erhöht/erniedrigt)
    bedingung = emp_config.get("bedingung", "")
    if bedingung == "erhöht" and last_flag != "H":
        return ""
    if bedingung == "erniedrigt" and last_flag != "L":
        return ""

    # Dynamische Ergänzung für bestimmte Tests
    dynamic_text = ""
    if is_dynamic and test == "Cholesterin":
        hdl_row = conn.execute("SELECT wert_norm FROM laborwerte WHERE test_standard='HDL' ORDER BY datum DESC LIMIT 1").fetchone()
        ldl_row = conn.execute("SELECT wert_norm FROM laborwerte WHERE test_standard='LDL' ORDER BY datum DESC LIMIT 1").fetchone()
        trig_row = conn.execute("SELECT wert_norm FROM laborwerte WHERE test_standard='Triglyceride' ORDER BY datum DESC LIMIT 1").fetchone()
        if hdl_row and ldl_row and trig_row:
            hdl = float(str(hdl_row[0]).replace(",", "."))
            ldl = float(str(ldl_row[0]).replace(",", "."))
            trig = float(str(trig_row[0]).replace(",", "."))
            berechnet = hdl + ldl + (trig / 5)
            dynamic_text = f"Aktuell: HDL {hdl:.0f} + LDL {ldl:.0f} + Trig÷5 ({trig:.0f}÷5={trig/5:.0f}) = {berechnet:.0f} mg/dL (gemessen: {val:.0f}). "
            if trig > 200 and ldl < 150:
                dynamic_text += f"Haupttreiber des hohen Gesamtwerts sind die Triglyceride ({trig:.0f}), LDL ({ldl:.0f}) ist OK. Triglyceride separat behandeln. "

    # Zusammensetzen
    parts = []
    if dynamic_text:
        parts.append(dynamic_text)
    if static_text:
        parts.append(static_text)
    return " ".join(parts)


@router.get("/trend/{test:path}")
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

        # Ersten nicht-leeren UND gültigen Normbereich suchen
        normbereich = ""
        for r in rows:
            nb = (r["normbereich"] or "").strip()
            if nb and any(c.isdigit() for c in nb):
                normbereich = nb
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

        # Bewertung basierend auf den letzten 5 Werten
        recent = rows[-5:] if len(rows) >= 5 else rows
        recent_path = sum(1 for r in recent if r["flag"] in ("H", "L"))
        recent_ratio = recent_path / len(recent) if recent else 0

        last_val = rows[-1]["wert_norm"] if rows else ""
        last_flag = rows[-1]["flag"] if rows else ""

        if recent_ratio == 0:
            bewertung = f"✅ Aktuell unauffällig – letzter Wert {last_val} {rows[-1]['einheit_norm'] or ''} im Normbereich."
            bewertung_status = "gut"
        elif recent_ratio < 0.4:
            bewertung = f"⚠️ Teilweise auffällig – letzter Wert {last_val} {rows[-1]['einheit_norm'] or ''}{' (erhöht)' if last_flag == 'H' else ' (erniedrigt)' if last_flag == 'L' else ''}. Beim nächsten Termin ansprechen."
            bewertung_status = "auffällig"
        else:
            bewertung = f"🚨 Kritisch – letzter Wert {last_val} {rows[-1]['einheit_norm'] or ''}{' (erhöht)' if last_flag == 'H' else ' (erniedrigt)' if last_flag == 'L' else ''}. Norm: {normbereich}. Ärztliche Abklärung empfohlen."
            bewertung_status = "kritisch"

        # Historischer Kontext
        all_path = sum(1 for r in rows if r["flag"] in ("H", "L"))
        if all_path > 0 and recent_ratio == 0:
            bewertung += f" Historisch {all_path}× außerhalb der Norm (von {len(rows)} Messungen)."

        # Test-spezifische Empfehlung
        trend_empfehlung = _get_test_empfehlung(test, last_val, last_flag, normbereich, conn)

        return {
            "test": test,
            "beschreibung": TEST_DESCRIPTIONS.get(test, ""),
            "einheit": rows[0]["einheit_norm"],
            "normbereich": normbereich,
            "bewertung": bewertung,
            "bewertung_empfehlung": trend_empfehlung,
            "bewertung_status": bewertung_status,
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


def _generate_empfehlung(name: str, tests: dict) -> str:
    """Generiert eine detaillierte Empfehlung basierend auf den aktuellen Werten."""

    def get_latest(test_name):
        if test_name not in tests:
            return None, None
        werte = tests[test_name]["werte"]
        if not werte:
            return None, None
        last = werte[-1]
        try:
            return float(str(last["wert"]).replace(",", ".").replace("<", "").replace(">", "")), last.get("flag", "")
        except (ValueError, TypeError):
            return None, None

    empfehlungen = []

    if name == "Gewicht & Stoffwechsel":
        gewicht, _ = get_latest("Gewicht")
        bmi, _ = get_latest("BMI")
        glucose, gf = get_latest("Glucose")
        hba1c, hf = get_latest("HbA1c")
        trig, tf = get_latest("Triglyceride")

        if bmi and bmi > 25:
            empfehlungen.append(f"BMI {bmi:.1f} liegt über dem Normalbereich (25). Gewichtsreduktion um {((bmi-23)*1.8):.0f} kg würde den BMI normalisieren.")
        elif bmi:
            empfehlungen.append(f"BMI {bmi:.1f} ist im Normalbereich – sehr gut.")

        if glucose and glucose > 100:
            empfehlungen.append(f"Nüchtern-Glucose {glucose:.0f} mg/dL ist grenzwertig erhöht. Weniger Zucker/Weißmehl, mehr Bewegung nach den Mahlzeiten.")
        if hba1c and hba1c > 5.7:
            empfehlungen.append(f"HbA1c {hba1c:.1f}% zeigt eine beginnende Störung des Zuckerstoffwechsels. Regelmäßige Kontrolle empfohlen.")
        if trig and trig > 200:
            empfehlungen.append(f"Triglyceride {trig:.0f} mg/dL sind deutlich erhöht. Weniger Alkohol, Zucker und gesättigte Fette. Omega-3-Fettsäuren können helfen.")

        if not empfehlungen:
            empfehlungen.append("Alle Werte im Zusammenspiel unauffällig – weiter so!")

    elif name == "Bauchfett & Entzündung":
        vf, _ = get_latest("Viszeralfett")
        crp, cf = get_latest("CRP")

        if vf and vf > 12:
            empfehlungen.append(f"Viszeralfett Level {vf:.0f} ist erhöht. Ausdauersport und Intervallfasten können gezielt Bauchfett reduzieren.")
        elif vf:
            empfehlungen.append(f"Viszeralfett Level {vf:.1f} ist im guten Bereich.")
        if crp and crp > 0.5:
            empfehlungen.append(f"CRP {crp:.2f} mg/dL deutet auf eine Entzündung hin. Bei dauerhaft erhöhtem CRP ohne Infekt: Zusammenhang mit Bauchfett prüfen.")

    elif name == "Muskeln & Nierenwerte":
        muskel, _ = get_latest("Muskelmasse")
        krea, _ = get_latest("Kreatinin")
        gfr, gf = get_latest("GFR")

        if gfr and gfr < 60:
            empfehlungen.append(f"GFR {gfr:.0f} mL/min ist eingeschränkt. Nephrologische Kontrolle empfohlen.")
        elif gfr and gfr < 90:
            empfehlungen.append(f"GFR {gfr:.0f} mL/min ist leicht reduziert – bei Alter 69 noch akzeptabel, aber regelmäßig kontrollieren.")
        if muskel and krea:
            empfehlungen.append(f"Bei {muskel:.0f}% Muskelmasse ist ein Kreatinin von {krea:.2f} mg/dL plausibel. Die GFR-Formel kann die Nierenfunktion leicht unterschätzen.")

    elif name == "Körperfett & Blutfette":
        fett, _ = get_latest("Fettgehalt")
        hdl, _ = get_latest("HDL")
        ldl, _ = get_latest("LDL")

        if fett and fett < 20:
            empfehlungen.append(f"Körperfett {fett:.1f}% ist gut für das Alter. Das unterstützt gute Blutfettwerte.")
        if hdl and hdl >= 60:
            empfehlungen.append(f"HDL {hdl:.0f} mg/dL (gutes Cholesterin) ist optimal – schützt die Gefäße.")
        elif hdl and hdl < 40:
            empfehlungen.append(f"HDL {hdl:.0f} mg/dL ist zu niedrig. Mehr Bewegung und ungesättigte Fette (Olivenöl, Nüsse, Fisch).")
        if ldl and ldl > 150:
            empfehlungen.append(f"LDL {ldl:.0f} mg/dL ist erhöht. Weniger gesättigte Fette, mehr Ballaststoffe.")

    elif name == "Nierenfunktion":
        gfr, _ = get_latest("GFR")
        krea, _ = get_latest("Kreatinin")
        hst, _ = get_latest("Harnstoff")

        if gfr and gfr < 60:
            empfehlungen.append(f"GFR {gfr:.0f}: Stadium 3 Niereninsuffizienz. Eiweißzufuhr begrenzen, viel trinken, regelmäßige Kontrolle.")
        elif gfr and gfr < 90:
            empfehlungen.append(f"GFR {gfr:.0f}: Leichte Einschränkung, alterstypisch. Ausreichend trinken (2L/Tag), Blutdruck kontrollieren.")
        if krea and krea > 1.2:
            empfehlungen.append(f"Kreatinin {krea:.2f} ist leicht erhöht – mit der GFR zusammen betrachten.")

    elif name == "Entzündungs-Kaskade":
        crp, _ = get_latest("CRP")
        leuko, _ = get_latest("Leukozyten")

        if crp and crp > 5:
            empfehlungen.append(f"CRP {crp:.1f} mg/dL ist stark erhöht – akuter Infekt oder Gewebeschaden wahrscheinlich.")
        elif crp and crp > 0.5:
            empfehlungen.append(f"CRP {crp:.2f} mg/dL ist leicht erhöht. Mögliche Ursachen: unterschwellige Entzündung, Übergewicht oder Stress.")
        if leuko and leuko > 11:
            empfehlungen.append(f"Leukozyten {leuko:.1f} sind erhöht – Immunsystem aktiv. Bei anhaltender Erhöhung ohne Infekt: abklären.")

    elif name == "Lipid-Profil":
        chol, _ = get_latest("Cholesterin")
        hdl, _ = get_latest("HDL")
        ldl, _ = get_latest("LDL")
        trig, _ = get_latest("Triglyceride")

        if chol and chol > 200:
            empfehlungen.append(f"Gesamt-Cholesterin {chol:.0f} mg/dL überschreitet den Zielwert. Entscheidend ist das Verhältnis LDL/HDL.")
        if ldl and hdl:
            ratio = ldl / hdl
            if ratio > 3:
                empfehlungen.append(f"LDL/HDL Verhältnis {ratio:.1f} ist ungünstig (Ziel <3). Mehr Bewegung und pflanzliche Ernährung können HDL heben.")
            else:
                empfehlungen.append(f"LDL/HDL Verhältnis {ratio:.1f} ist gut.")
        if trig and trig > 200:
            empfehlungen.append(f"Triglyceride {trig:.0f} mg/dL erhöht. Weniger Zucker, Alkohol und raffinierte Kohlenhydrate.")

    elif name == "Cholesterin-Aufschlüsselung":
        chol, _ = get_latest("Cholesterin")
        hdl, _ = get_latest("HDL")
        ldl, _ = get_latest("LDL")
        trig, _ = get_latest("Triglyceride")

        if chol and hdl and ldl and trig:
            berechnet = hdl + ldl + (trig / 5)
            empfehlungen.append(f"Formel: HDL ({hdl:.0f}) + LDL ({ldl:.0f}) + Triglyceride÷5 ({trig:.0f}÷5 = {trig/5:.0f}) = {berechnet:.0f} mg/dL (gemessen: {chol:.0f}).")

        if trig and trig > 200 and ldl and ldl < 150:
            empfehlungen.append(f"Triglyceride ({trig:.0f}) sind der Haupttreiber des hohen Gesamtcholesterins – NICHT das LDL ({ldl:.0f}, das ist OK).")
            empfehlungen.append("Maßnahmen gegen hohe Triglyceride: 1) Alkohol reduzieren/meiden, 2) Zucker und Weißmehl stark einschränken, 3) Omega-3 Fettsäuren (Fischöl 2g/Tag oder fetter Fisch 3×/Woche), 4) Regelmäßige Bewegung (senkt Triglyceride um 20-30%).")
        elif trig and trig > 200:
            empfehlungen.append(f"Triglyceride {trig:.0f} mg/dL deutlich erhöht. Weniger Zucker, Alkohol und schnelle Kohlenhydrate.")

        if hdl and hdl >= 55:
            empfehlungen.append(f"HDL {hdl:.0f} mg/dL ist gut (schützt die Gefäße). Weiter so mit Bewegung.")
        if ldl and ldl < 130:
            empfehlungen.append(f"LDL {ldl:.0f} mg/dL im Zielbereich für Alter 69 ohne Vorerkrankung. Statine aktuell nicht zwingend nötig.")

    if not empfehlungen:
        empfehlungen.append("Keine spezifischen Auffälligkeiten in dieser Kombination.")

    return " · ".join(empfehlungen)


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
            "empfehlung": _generate_empfehlung(vk["name"], result_tests),
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


@router.get("/bericht/charts", response_class=HTMLResponse)
async def bericht_charts(period: str = "1m", sort: str = "datum", dir: int = -1):
    """Arztbericht mit Verlaufs-Charts pro auffälligem Test."""
    from datetime import datetime

    conn = get_db()
    try:
        # Auffällige Tests im Zeitraum (eindeutig)
        query = """
            SELECT DISTINCT test_standard, gruppe FROM laborwerte WHERE flag IN ('H','L')
        """
        if period == "1m":
            query += " AND datum >= date('now', '-1 month')"
        elif period == "6m":
            query += " AND datum >= date('now', '-6 months')"
        elif period == "1y":
            query += " AND datum >= date('now', '-1 year')"

        test_names = [(r[0], r[1]) for r in conn.execute(query).fetchall()]

        # Pro Test: alle Werte + Normbereich
        tests_data = []
        for test, gruppe in sorted(test_names):
            rows = conn.execute(
                "SELECT datum, wert_norm, einheit_norm, normbereich, flag FROM laborwerte WHERE test_standard=? ORDER BY datum",
                (test,),
            ).fetchall()
            if not rows:
                continue

            norm = ""
            for r in rows:
                nb = (r["normbereich"] or "").strip()
                if nb and any(c.isdigit() for c in nb):
                    norm = nb
                    break

            # Bewertung
            recent = rows[-5:] if len(rows) >= 5 else rows
            recent_path = sum(1 for r in recent if r["flag"] in ("H", "L"))
            recent_ratio = recent_path / len(recent)
            last = rows[-1]

            if recent_ratio == 0:
                bew = f"✅ Aktuell im Normbereich ({last['wert_norm']} {last['einheit_norm'] or ''})"
                bew_cls = "gut"
            elif recent_ratio < 0.5:
                bew = f"⚠️ Teilweise auffällig – letzter Wert: {last['wert_norm']} {last['einheit_norm'] or ''}"
                bew_cls = "warn"
            else:
                bew = f"🚨 Kritisch – letzter Wert: {last['wert_norm']} {last['einheit_norm'] or ''} (Norm: {norm})"
                bew_cls = "crit"

            # Test-spezifische Empfehlung
            emp = _get_test_empfehlung(test, last["wert_norm"], last["flag"], norm, conn)

            tests_data.append({
                "name": test,
                "gruppe": gruppe,
                "beschreibung": TEST_DESCRIPTIONS.get(test, ""),
                "einheit": rows[0]["einheit_norm"] or "",
                "norm": norm,
                "bewertung": bew,
                "bewertung_cls": bew_cls,
                "empfehlung": emp,
                "labels": [r["datum"] for r in rows],
                "values": [r["wert_norm"] for r in rows],
                "flags": [r["flag"] for r in rows],
            })

    finally:
        conn.close()

    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    period_labels = {"1m": "Letzter Monat", "6m": "Letzte 6 Monate", "1y": "Letztes Jahr", "all": "Gesamter Zeitraum"}

    # Sortierung anwenden
    sort_keys = {
        "datum": lambda t: t["labels"][-1] if t["labels"] else "",
        "gruppe": lambda t: t.get("gruppe", ""),
        "test_standard": lambda t: t["name"],
        "wert_norm": lambda t: float(str(t["values"][-1]).replace(",", ".").replace("<", "").replace(">", "") or "0") if t["values"] else 0,
        "flag": lambda t: t["bewertung_cls"],
    }
    sort_fn = sort_keys.get(sort, sort_keys["datum"])
    tests_data.sort(key=sort_fn, reverse=(dir == -1))

    # Charts als JSON für client-seitiges Rendering
    import json
    charts_json = json.dumps(tests_data, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<title>Laborbericht mit Verlauf – {now}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
    body {{ font-family: -apple-system, "Segoe UI", sans-serif; font-size: 11px; color: #1a1a1a; margin: 1.5cm; line-height: 1.4; }}
    h1 {{ font-size: 18px; margin-bottom: 4px; }}
    .meta {{ color: #666; font-size: 10px; margin-bottom: 20px; }}
    .test-section {{ page-break-inside: avoid; margin-bottom: 24px; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; }}
    .test-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }}
    .test-name {{ font-size: 14px; font-weight: 700; }}
    .test-desc {{ font-size: 10px; color: #666; margin-bottom: 8px; }}
    .bewertung {{ font-size: 11px; font-weight: 500; padding: 4px 8px; border-radius: 4px; margin-bottom: 8px; display: inline-block; }}
    .bewertung.gut {{ background: #dcfce7; color: #166534; }}
    .bewertung.warn {{ background: #fef3c7; color: #92400e; }}
    .bewertung.crit {{ background: #fee2e2; color: #991b1b; }}
    .chart-container {{ height: 160px; margin: 8px 0 0 0; }}
    .stats {{ display: flex; gap: 16px; font-size: 10px; color: #666; margin-top: 28px; padding-top: 6px; border-top: 1px solid #eee; }}
    .print-btn {{ position: fixed; top: 16px; right: 16px; padding: 12px 24px; background: #2563eb; color: white; border: none; border-radius: 8px; font-size: 14px; cursor: pointer; z-index: 100; }}
    @media print {{
        body {{ margin: 0.5cm; font-size: 10px; }}
        .print-btn {{ display: none; }}
        .test-section {{ border: 1px solid #ddd; padding: 12px; margin-bottom: 16px; }}
        .chart-container {{ height: 150px; }}
    }}
</style>
</head>
<body>
<button class="print-btn" onclick="window.print()">🖨️ Als PDF drucken</button>

<h1>🩸 Laborbericht – Auffällige Werte mit Verlauf</h1>
<div class="meta">
    Patient: {PATIENT_CONFIG.get('vorname', '')} {PATIENT_CONFIG.get('nachname', '')} · geb. {PATIENT_CONFIG.get('geburtsdatum', '')} · männlich<br>
    Zeitraum: {period_labels.get(period, period)} · Erstellt: {now} · {len(tests_data)} auffällige Tests
</div>

<div id="report"></div>

<script>
const tests = {charts_json};

const container = document.getElementById('report');

tests.forEach((t, idx) => {{
    // Werte parsen
    const values = t.values.map(v => {{
        let raw = String(v).replace(',','.').replace(/^[<>]/,'');
        return parseFloat(raw) || null;
    }});

    const section = document.createElement('div');
    section.className = 'test-section';
    section.innerHTML = `
        <div class="test-header">
            <span class="test-name">${{t.name}} (${{t.einheit}})</span>
            <span>Norm: ${{t.norm || '–'}}</span>
        </div>
        <div class="test-desc">${{t.beschreibung}}</div>
        <div class="bewertung ${{t.bewertung_cls}}">${{t.bewertung}}</div>
        ${{t.empfehlung ? '<div style="font-size:10px;color:#166534;background:#dcfce7;padding:6px 10px;border-radius:4px;margin-bottom:8px;">💡 '+t.empfehlung+'</div>' : ''}}
        <div class="chart-container"><canvas id="chart${{idx}}"></canvas></div>
        <div class="stats" id="stats${{idx}}"></div>
    `;
    container.appendChild(section);

    // Statistik berechnen
    const numVals = values.filter(v => v !== null);
    if (numVals.length > 0) {{
        const mn = Math.min(...numVals);
        const mx = Math.max(...numVals);
        const avg = numVals.reduce((a,b) => a+b, 0) / numVals.length;
        const latest = numVals[numVals.length - 1];
        const first = numVals[0];
        const pct = first !== 0 ? ((latest - first) / first * 100).toFixed(0) : 0;
        let trend = Math.abs(pct) < 5 ? '→ Stabil' : (pct > 0 ? '↑ +'+pct+'%' : '↓ '+pct+'%');
        const trendColor = Math.abs(pct) < 5 ? '#059669' : (pct > 0 ? '#d97706' : '#2563eb');
        const fy = t.labels[0] ? t.labels[0].slice(0,4) : '';
        const ly = t.labels[t.labels.length-1] ? t.labels[t.labels.length-1].slice(0,4) : '';

        document.getElementById('stats'+idx).innerHTML =
            '<span><b>Min:</b> '+mn.toFixed(1)+' '+t.einheit+'</span>' +
            '<span><b>Max:</b> '+mx.toFixed(1)+' '+t.einheit+'</span>' +
            '<span><b>Ø:</b> '+avg.toFixed(1)+' '+t.einheit+'</span>' +
            '<span><b>Aktuell:</b> '+latest.toFixed(1)+' '+t.einheit+'</span>' +
            '<span style="color:'+trendColor+'"><b>Trend ('+fy+'→'+ly+'):</b> '+trend+'</span>';
    }}

    const pointColors = t.flags.map(f => f === 'H' ? '#dc2626' : f === 'L' ? '#2563eb' : '#059669');

    // Norm-Linien
    const datasets = [{{
        label: t.name,
        data: values,
        borderColor: '#059669',
        backgroundColor: 'rgba(5,150,105,0.05)',
        fill: true,
        tension: 0.25,
        pointBackgroundColor: pointColors,
        pointRadius: values.length > 30 ? 0 : 3,
        borderWidth: 1.5,
    }}];

    // Norm parsen
    let normMin = null, normMax = null;
    if (t.norm) {{
        const range = t.norm.match(/^([\\d.]+)\\s*-\\s*([\\d.]+)$/);
        if (range) {{ normMin = parseFloat(range[1]); normMax = parseFloat(range[2]); }}
        const lt = t.norm.match(/^[<]\\s*-?\\s*([\\d.]+)$/);
        if (lt) {{ normMax = parseFloat(lt[1]); }}
        const gt = t.norm.match(/^[>]\\s*-?\\s*([\\d.]+)$/);
        if (gt) {{ normMin = parseFloat(gt[1]); }}
        const dm = t.norm.match(/^-\\s*([\\d.]+)$/);
        if (dm && !range) {{ normMax = parseFloat(dm[1]); }}
    }}
    if (normMax) datasets.push({{ label:'Norm', data: Array(values.length).fill(normMax), borderColor:'rgba(220,38,38,0.3)', borderDash:[4,4], borderWidth:1, pointRadius:0 }});
    if (normMin) datasets.push({{ label:'Norm', data: Array(values.length).fill(normMin), borderColor:'rgba(220,38,38,0.3)', borderDash:[4,4], borderWidth:1, pointRadius:0 }});

    new Chart(document.getElementById('chart'+idx), {{
        type: 'line',
        data: {{ labels: t.labels, datasets }},
        options: {{
            responsive: true, maintainAspectRatio: false, animation: false,
            plugins: {{ legend: {{ display: false }}, title: {{ display: false }} }},
            scales: {{
                x: {{ ticks: {{ maxTicksLimit: 8, font: {{ size: 9 }} }}, grid: {{ display: false }} }},
                y: {{ ticks: {{ font: {{ size: 9 }} }}, grid: {{ color: 'rgba(0,0,0,0.05)' }} }}
            }}
        }}
    }});
}});
</script>
</body>
</html>"""

    return HTMLResponse(content=html)


@router.get("/bericht", response_class=HTMLResponse)
async def bericht(period: str = "1m"):
    """Arztbericht als druckfertiges HTML (im Browser als PDF speichern)."""
    from fastapi.responses import HTMLResponse
    from datetime import datetime

    conn = get_db()
    try:
        # Auffällige Werte im Zeitraum
        query = """
            SELECT datum, gruppe, test_standard, wert_norm, einheit_norm, normbereich, flag
            FROM laborwerte WHERE flag IN ('H', 'L')
        """
        if period == "1m":
            query += " AND datum >= date('now', '-1 month')"
        elif period == "6m":
            query += " AND datum >= date('now', '-6 months')"
        elif period == "1y":
            query += " AND datum >= date('now', '-1 year')"
        query += " ORDER BY gruppe, test_standard, datum DESC"
        path_rows = conn.execute(query).fetchall()

        # Letzte Werte pro Test
        alle_aktuell = conn.execute("""
            SELECT l.gruppe, l.test_standard, l.wert_norm, l.einheit_norm, l.normbereich, l.flag, l.datum
            FROM laborwerte l
            WHERE l.datum = (SELECT MAX(l2.datum) FROM laborwerte l2 WHERE l2.test_standard = l.test_standard)
            GROUP BY l.test_standard
            ORDER BY l.gruppe, l.test_standard
        """).fetchall()

        # KPIs
        total = conn.execute("SELECT COUNT(*) FROM laborwerte").fetchone()[0]
        path_total = conn.execute("SELECT COUNT(*) FROM laborwerte WHERE flag IN ('H','L')").fetchone()[0]
        zeitraum = conn.execute("SELECT MIN(datum), MAX(datum) FROM laborwerte").fetchone()

    finally:
        conn.close()

    # Zeitraum-Label
    period_labels = {"1m": "Letzter Monat", "6m": "Letzte 6 Monate", "1y": "Letztes Jahr", "all": "Gesamter Zeitraum"}
    period_label = period_labels.get(period, period)

    # Auffällige nach Gruppe gruppieren
    gruppen_path = {}
    for r in path_rows:
        g = r["gruppe"]
        if g not in gruppen_path:
            gruppen_path[g] = []
        gruppen_path[g].append(r)

    # HTML generieren
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    rows_html = ""
    for gruppe, items in sorted(gruppen_path.items()):
        rows_html += f'<tr class="group-row"><td colspan="6"><strong>{gruppe}</strong></td></tr>'
        for r in items:
            flag_cls = "high" if r["flag"] == "H" else "low"
            flag_txt = "↑ erhöht" if r["flag"] == "H" else "↓ erniedrigt"
            rows_html += f'''<tr>
                <td>{r["datum"]}</td>
                <td>{r["test_standard"]}</td>
                <td><strong>{r["wert_norm"]}</strong> {r["einheit_norm"] or ""}</td>
                <td>{r["normbereich"] or ""}</td>
                <td class="{flag_cls}">{flag_txt}</td>
                <td>{TEST_DESCRIPTIONS.get(r["test_standard"], "")[:80]}</td>
            </tr>'''

    # Aktuelle Werte Tabelle
    aktuell_html = ""
    current_gruppe = ""
    for r in alle_aktuell:
        if r["gruppe"] != current_gruppe:
            current_gruppe = r["gruppe"]
            aktuell_html += f'<tr class="group-row"><td colspan="5"><strong>{current_gruppe}</strong></td></tr>'
        flag_cls = "high" if r["flag"] == "H" else "low" if r["flag"] == "L" else ""
        aktuell_html += f'''<tr class="{flag_cls}">
            <td>{r["test_standard"]}</td>
            <td><strong>{r["wert_norm"]}</strong> {r["einheit_norm"] or ""}</td>
            <td>{r["normbereich"] or ""}</td>
            <td>{r["datum"]}</td>
            <td>{r["flag"] or "✓"}</td>
        </tr>'''

    html = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<title>Laborbericht – {now}</title>
<style>
    body {{ font-family: -apple-system, "Segoe UI", sans-serif; font-size: 11px; color: #1a1a1a; margin: 1cm; line-height: 1.4; }}
    h1 {{ font-size: 18px; margin-bottom: 4px; }}
    h2 {{ font-size: 14px; margin-top: 24px; margin-bottom: 8px; border-bottom: 1px solid #ddd; padding-bottom: 4px; }}
    .meta {{ color: #666; font-size: 10px; margin-bottom: 16px; }}
    .kpi-row {{ display: flex; gap: 24px; margin-bottom: 16px; }}
    .kpi {{ padding: 8px 12px; background: #f8f9fa; border-radius: 6px; }}
    .kpi-label {{ font-size: 9px; color: #666; text-transform: uppercase; }}
    .kpi-value {{ font-size: 16px; font-weight: 700; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 10px; margin-bottom: 16px; }}
    th {{ text-align: left; padding: 6px 8px; background: #f0f0f0; border-bottom: 2px solid #ddd; font-size: 9px; text-transform: uppercase; }}
    td {{ padding: 5px 8px; border-bottom: 1px solid #eee; }}
    .group-row td {{ background: #f8f9fa; padding-top: 10px; }}
    .high {{ color: #dc2626; }}
    .low {{ color: #2563eb; }}
    .footer {{ margin-top: 32px; padding-top: 12px; border-top: 1px solid #ddd; font-size: 9px; color: #999; }}
    @media print {{
        body {{ margin: 1.5cm; }}
        .no-print {{ display: none; }}
    }}
    .print-btn {{ position: fixed; top: 16px; right: 16px; padding: 10px 20px; background: #2563eb; color: white; border: none; border-radius: 8px; font-size: 13px; cursor: pointer; }}
</style>
</head>
<body>
<button class="print-btn no-print" onclick="window.print()">🖨️ Als PDF drucken</button>

<h1>Laborbericht</h1>
<div class="meta">
    Patient: {PATIENT_CONFIG.get('vorname', '')} {PATIENT_CONFIG.get('nachname', '')} · geb. {PATIENT_CONFIG.get('geburtsdatum', '')} · männlich<br>
    Erstellt: {now} · Zeitraum: {period_label} · Datenquelle: {total} Messwerte ({zeitraum[0]} bis {zeitraum[1]})
</div>

<div class="kpi-row">
    <div class="kpi"><div class="kpi-label">Messwerte gesamt</div><div class="kpi-value">{total}</div></div>
    <div class="kpi"><div class="kpi-label">Auffällige Werte</div><div class="kpi-value" style="color:#dc2626">{path_total}</div></div>
    <div class="kpi"><div class="kpi-label">Im Normbereich</div><div class="kpi-value" style="color:#059669">{total - path_total} ({round((total-path_total)/total*100)}%)</div></div>
</div>

<h2>⚠️ Auffällige Werte ({period_label})</h2>
<table>
    <thead><tr><th>Datum</th><th>Test</th><th>Wert</th><th>Norm</th><th>Status</th><th>Hinweis</th></tr></thead>
    <tbody>{rows_html}</tbody>
</table>

<h2>📋 Aktuelle Werte (alle Tests, letzter Messwert)</h2>
<table>
    <thead><tr><th>Test</th><th>Wert</th><th>Norm</th><th>Datum</th><th>Status</th></tr></thead>
    <tbody>{aktuell_html}</tbody>
</table>

<div class="footer">
    Dieser Bericht wurde automatisch erstellt und ersetzt keine ärztliche Diagnose.<br>
    Labor Dashboard · hc_med · Erstellt am {now}
</div>
</body>
</html>"""

    return HTMLResponse(content=html)


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
