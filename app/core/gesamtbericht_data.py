"""Gesamtbericht – Daten-Assembly-Modul.

Stellt Hilfsfunktionen bereit, die vom Gesamtbericht-Endpoint genutzt werden,
um alle relevanten Labor-Daten zusammenzuführen.
"""

import sqlite3

from app.config.settings import EMPFEHLUNGEN_TESTS, GROUP_CONFIG, GROUP_DESCRIPTIONS, KURZNAMEN
from app.core.empfehlungen import get_test_empfehlung


# ---------------------------------------------------------------------------
# Traffic-Light Classification
# ---------------------------------------------------------------------------

def classify_traffic_light(pathologisch: int, total: int) -> str:
    """Klassifiziert eine Gruppe anhand des Anteils pathologischer Werte.

    Args:
        pathologisch: Anzahl pathologischer Messwerte in der Gruppe.
        total: Gesamtzahl der Messwerte in der Gruppe (muss > 0 sein).

    Returns:
        "gut"       – kein pathologischer Wert (ratio == 0)
        "ok"        – ratio > 0 und < 0.15
        "auffällig" – ratio >= 0.15 und < 0.35
        "kritisch"  – ratio >= 0.35
    """
    if total <= 0:
        return "gut"
    if pathologisch == 0:
        return "gut"
    ratio = pathologisch / total
    if ratio < 0.15:
        return "ok"
    if ratio < 0.35:
        return "auffällig"
    return "kritisch"


# ---------------------------------------------------------------------------
# Gefäß-Score
# ---------------------------------------------------------------------------

_GEFAESS_FAKTOREN = [
    # (test_name, threshold, operator, points)
    ("Triglyceride", 200, "gt", 2),
    ("CRP", 0.5, "gt", 2),
    ("HbA1c", 5.7, "gt", 1),
    ("LDL", 130, "gt", 1),
    ("Harnsäure", 7.0, "gt", 1),
    ("HDL", 40, "lt", 1),
]


def _get_last_value(conn: sqlite3.Connection, test_name: str):
    """Holt den letzten numerischen Wert eines Tests aus der DB."""
    row = conn.execute(
        "SELECT wert_norm FROM laborwerte WHERE test_standard=? ORDER BY datum DESC LIMIT 1",
        (test_name,),
    ).fetchone()
    if not row:
        return None
    try:
        return float(str(row[0]).replace(",", ".").replace("<", "").replace(">", ""))
    except (ValueError, TypeError):
        return None


def berechne_gefaess_score(conn: sqlite3.Connection) -> dict:
    """Berechnet den Gefäßgesundheit-Score mit Einzelfaktoren.

    Nutzt dieselben Schwellenwerte wie `_berechne_gefaess_details` in
    `verknuepfung.py`: Triglyceride >200, CRP >0.5, HbA1c >5.7,
    LDL >130, Harnsäure >7.0, HDL <40.

    Returns:
        dict mit keys: score, max, status, faktoren
    """
    score = 0
    max_score = 8
    faktoren = []

    for test_name, threshold, operator, points in _GEFAESS_FAKTOREN:
        wert = _get_last_value(conn, test_name)
        if wert is None:
            continue

        if operator == "gt":
            aktiv = wert > threshold
        else:  # "lt"
            aktiv = wert < threshold

        if aktiv:
            score += points

        # Formatierung analog verknuepfung.py
        if test_name == "CRP":
            wert_str = f"{wert:.2f}"
        elif test_name == "HbA1c":
            wert_str = f"{wert:.1f}%"
        elif test_name in ("Harnsäure",):
            wert_str = f"{wert:.1f}"
        else:
            wert_str = f"{wert:.0f}"

        faktoren.append({
            "name": test_name,
            "wert": wert_str,
            "punkte": points if aktiv else 0,
            "max": points,
            "aktiv": aktiv,
        })

    # Status-Ableitung (identisch zu overview.py)
    if score >= 5:
        status = "kritisch"
    elif score >= 3:
        status = "auffällig"
    else:
        status = "gut"

    return {
        "score": score,
        "max": max_score,
        "status": status,
        "faktoren": faktoren,
    }


# ---------------------------------------------------------------------------
# Gruppen-Summary mit Traffic-Light
# ---------------------------------------------------------------------------

def build_gruppen_summary(conn: sqlite3.Connection) -> list[dict]:
    """Erstellt eine Traffic-Light-Zusammenfassung aller Gruppen.

    Fragt die Datenbank nach Gruppenstatistiken und wendet
    `classify_traffic_light` an.

    Returns:
        Liste von dicts mit: name, icon, status, anzahl, pathologisch, path_ratio
    """
    rows = conn.execute("""
        SELECT gruppe,
               COUNT(*) as anzahl,
               SUM(CASE WHEN flag IN ('H','L') THEN 1 ELSE 0 END) as path_count
        FROM laborwerte
        GROUP BY gruppe
        ORDER BY gruppe
    """).fetchall()

    gruppen = []
    for row in rows:
        name = row["gruppe"]
        anzahl = row["anzahl"]
        path_count = row["path_count"]
        path_ratio = path_count / anzahl if anzahl > 0 else 0.0

        gc = GROUP_CONFIG.get(name, {})
        gruppen.append({
            "name": name,
            "icon": gc.get("icon", "📋"),
            "status": classify_traffic_light(path_count, anzahl),
            "anzahl": anzahl,
            "pathologisch": path_count,
            "path_ratio": round(path_ratio, 4),
        })

    return gruppen


# ---------------------------------------------------------------------------
# Trend Indicator Computation
# ---------------------------------------------------------------------------

def compute_trend(current: float, previous: float, flag: str) -> tuple[str, str]:
    """Berechnet den Trend-Indikator für einen auffälligen Test.

    Vergleicht aktuellen Wert mit dem vorherigen Wert und bestimmt
    anhand der Flag-Richtung, ob sich der Wert verschlechtert oder verbessert hat.

    Args:
        current: Aktueller Messwert.
        previous: Vorheriger Messwert (muss > 0 sein für sinnvolle Berechnung).
        flag: Flag-Richtung ("H" für zu hoch, "L" für zu niedrig).

    Returns:
        Tuple (trend_symbol, trend_label):
        - ("→", "stabil") wenn Änderung < 5%
        - ("↑", "verschlechtert") wenn Wert sich in pathologische Richtung bewegt
        - ("↓", "verbessert") wenn Wert sich Richtung Normalbereich bewegt
    """
    if previous == 0:
        return ("→", "stabil")

    change_pct = abs(current - previous) / abs(previous)

    if change_pct < 0.05:
        return ("→", "stabil")

    if flag == "H":
        if current > previous:
            return ("↑", "verschlechtert")
        else:
            return ("↓", "verbessert")
    else:  # flag == "L"
        if current < previous:
            return ("↑", "verschlechtert")
        else:
            return ("↓", "verbessert")


# ---------------------------------------------------------------------------
# Abnormal Tests Collection
# ---------------------------------------------------------------------------

def build_abnormal_tests(conn: sqlite3.Connection, period: str = "all") -> list[dict]:
    """Sammelt alle Tests mit pathologischem Flag auf der letzten Messung.

    Args:
        conn: SQLite-Datenbankverbindung.
        period: Zeitfilter – "all", "1y", "6m", "1m".

    Returns:
        Liste von Dicts mit: name, gruppe, wert, einheit, norm, flag,
        trend, trend_label, empfehlung, bewertung_cls
    """
    # Zeitfilter
    period_filter = ""
    if period == "1m":
        period_filter = " AND l.datum >= date('now', '-1 month')"
    elif period == "6m":
        period_filter = " AND l.datum >= date('now', '-6 months')"
    elif period == "1y":
        period_filter = " AND l.datum >= date('now', '-1 year')"

    # Letzter Wert pro Test, nur mit H/L-Flag
    rows = conn.execute(f"""
        SELECT l.datum, l.gruppe, l.test_standard, l.wert_norm, l.einheit_norm,
               l.normbereich, l.flag
        FROM laborwerte l
        WHERE l.flag IN ('H', 'L')
        {period_filter}
        AND l.datum = (
            SELECT MAX(l2.datum) FROM laborwerte l2
            WHERE l2.test_standard = l.test_standard AND l2.flag IN ('H','L')
            {period_filter}
        )
        GROUP BY l.test_standard
        ORDER BY l.datum DESC
    """).fetchall()

    results = []
    for row in rows:
        test_name = row["test_standard"]
        current_wert = row["wert_norm"]
        flag = row["flag"]
        datum = row["datum"]

        # Aktuellen Wert als float parsen
        try:
            current_val = float(
                str(current_wert).replace(",", ".").replace("<", "").replace(">", "")
            )
        except (ValueError, TypeError):
            current_val = None

        # Vorherigen Wert für Trend-Berechnung holen
        prev_row = conn.execute(
            """SELECT wert_norm FROM laborwerte
               WHERE test_standard = ? AND datum < ?
               ORDER BY datum DESC LIMIT 1""",
            (test_name, datum),
        ).fetchone()

        trend = "→"
        trend_label = "stabil"
        if current_val is not None and prev_row:
            try:
                prev_val = float(
                    str(prev_row["wert_norm"]).replace(",", ".").replace("<", "").replace(">", "")
                )
                trend, trend_label = compute_trend(current_val, prev_val, flag)
            except (ValueError, TypeError):
                pass

        # Empfehlung aus empfehlungen.py
        empfehlung = get_test_empfehlung(
            test_name, current_wert, flag, row["normbereich"], conn
        )

        # Schweregrad berechnen: Anteil pathologischer Werte in den letzten 5 Messungen
        severity_rows = conn.execute(
            """SELECT flag FROM laborwerte
               WHERE test_standard = ?
               ORDER BY datum DESC LIMIT 5""",
            (test_name,),
        ).fetchall()
        path_count = sum(1 for r in severity_rows if r["flag"] in ("H", "L"))
        path_ratio = path_count / len(severity_rows) if severity_rows else 0

        bewertung_cls = "crit" if path_ratio >= 0.6 else "warn"

        results.append({
            "name": KURZNAMEN.get(test_name, test_name),
            "gruppe": row["gruppe"],
            "wert": current_wert,
            "einheit": row["einheit_norm"] or "",
            "norm": row["normbereich"] or "",
            "flag": flag,
            "trend": trend,
            "trend_label": trend_label,
            "empfehlung": empfehlung,
            "bewertung_cls": bewertung_cls,
            "datum": datum,
            "_path_ratio": path_ratio,
        })

    # Sortierung: erst H (hoch), dann L (tief), innerhalb nach Datum absteigend
    h_items = [r for r in results if r["flag"] == "H"]
    l_items = [r for r in results if r["flag"] == "L"]
    h_items.sort(key=lambda x: x.get("datum", "") or "", reverse=True)
    l_items.sort(key=lambda x: x.get("datum", "") or "", reverse=True)
    results = h_items + l_items

    # Hilfsfelder entfernen
    for r in results:
        r.pop("_path_ratio", None)
        r.pop("datum", None)

    return results


# ---------------------------------------------------------------------------
# Verknüpfungs-Charts für Problem-Gruppen
# ---------------------------------------------------------------------------

def build_verknuepfung_charts(conn: sqlite3.Connection) -> list[dict]:
    """Filtert Verknüpfungen auf solche mit mindestens einem pathologischen Test.

    Für jede relevante Verknüpfung werden die Chart-Daten (JSON für Chart.js)
    und die Empfehlung zusammengestellt.

    Returns:
        Liste von dicts mit: name, beschreibung, tests_json, empfehlung
    """
    import json
    from app.config.settings import VERKNUEPFUNGEN
    from app.core.empfehlungen import generate_verknuepfung_empfehlung

    # Bestimmen welche Tests aktuell pathologisch sind
    path_tests = set()
    rows = conn.execute("""
        SELECT test_standard FROM laborwerte l
        WHERE flag IN ('H','L')
        AND datum = (SELECT MAX(l2.datum) FROM laborwerte l2 WHERE l2.test_standard = l.test_standard)
        GROUP BY test_standard
    """).fetchall()
    for r in rows:
        path_tests.add(r["test_standard"])

    charts = []
    for vk in VERKNUEPFUNGEN:
        # Nur Verknüpfungen wo mindestens ein Test pathologisch ist
        if not any(t in path_tests for t in vk.get("tests", [])):
            continue

        # Chart-Daten sammeln
        result_tests = {}
        for test in vk["tests"]:
            test_rows = conn.execute(
                """SELECT datum, wert_norm, einheit_norm, normbereich, flag
                   FROM laborwerte WHERE test_standard=? ORDER BY datum""",
                (test,),
            ).fetchall()
            if test_rows:
                norm = ""
                for r in test_rows:
                    if r["normbereich"] and r["normbereich"].strip():
                        norm = r["normbereich"]
                        break
                result_tests[test] = {
                    "einheit": test_rows[0]["einheit_norm"] or "",
                    "normbereich": norm,
                    "werte": [{"datum": r["datum"], "wert": r["wert_norm"], "flag": r["flag"]} for r in test_rows],
                }

        if not result_tests:
            continue

        empfehlung = generate_verknuepfung_empfehlung(vk["name"], result_tests)

        charts.append({
            "name": vk["name"],
            "beschreibung": vk.get("beschreibung", ""),
            "tests_json": json.dumps(result_tests, ensure_ascii=False),
            "empfehlung": empfehlung,
            "path_count": sum(1 for t in vk["tests"] if t in path_tests),
        })

    # Sortierung: meiste auffällige Tests zuerst
    charts.sort(key=lambda c: c["path_count"], reverse=True)

    # Hilfsfeld entfernen
    for c in charts:
        c.pop("path_count", None)

    return charts


# ---------------------------------------------------------------------------
# Haupt-Orchestrator
# ---------------------------------------------------------------------------

def build_report_data(conn: sqlite3.Connection, period: str = "1y") -> dict:
    """Orchestriert alle Datensammlung für den Gesamtbericht.

    Args:
        conn: DB-Verbindung.
        period: Zeitfilter – "all", "1y", "6m", "1m".

    Returns:
        Dict mit allen Report-Sektionen.
    """
    from datetime import datetime
    from app.config.settings import PATIENT_CONFIG
    from app.core.vergleich import berechne_vorjahresvergleich

    PERIOD_LABELS = {"all": "Gesamter Zeitraum", "1y": "Letztes Jahr", "6m": "Letzte 6 Monate", "1m": "Letzter Monat"}

    return {
        "patient": PATIENT_CONFIG,
        "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "period_label": PERIOD_LABELS.get(period, period),
        "gruppen": build_gruppen_summary(conn),
        "gefaess_score": berechne_gefaess_score(conn),
        "abnormal_tests": build_abnormal_tests(conn, period=period),
        "verknuepfung_charts": build_verknuepfung_charts(conn),
        "vergleich": berechne_vorjahresvergleich(conn),
    }
