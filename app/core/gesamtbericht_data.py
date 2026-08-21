"""Gesamtbericht – Daten-Assembly-Modul.

Stellt Hilfsfunktionen bereit, die vom Gesamtbericht-Endpoint genutzt werden,
um alle relevanten Labor-Daten zusammenzuführen.
"""

import sqlite3

from app.config.settings import GROUP_CONFIG, KURZNAMEN
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
        "zusammenfassung": _build_gefaess_zusammenfassung(faktoren),
    }


def _build_gefaess_zusammenfassung(faktoren: list[dict]) -> str:
    """Generiert einen medizinischen Zusammenfassungssatz basierend auf den aktiven Risikofaktoren."""
    aktive = [f for f in faktoren if f["aktiv"]]
    if not aktive:
        return "Kein erhöhtes Gefäßrisiko – alle Risikofaktoren im Normbereich."

    teile = []

    # Fettstoffwechsel (Triglyceride + LDL)
    trig_aktiv = any(f["name"] == "Triglyceride" for f in aktive)
    ldl_aktiv = any(f["name"] == "LDL" for f in aktive)
    hdl_ok = not any(f["name"] == "HDL" and f["aktiv"] for f in faktoren)

    if trig_aktiv and ldl_aktiv:
        teil = "eine kombinierte Fettstoffwechselstörung (erhöhte Triglyceride und erhöhtes LDL-Cholesterin"
        if hdl_ok:
            teil += " bei gutem HDL"
        teil += ")"
        teile.append(teil)
    elif trig_aktiv:
        teil = "eine Hypertriglyceridämie (stark erhöhte Triglyceride"
        if hdl_ok:
            teil += " bei gutem HDL"
        teil += ")"
        teile.append(teil)
    elif ldl_aktiv:
        teile.append("ein erhöhtes LDL-Cholesterin")

    # HDL niedrig (nur wenn nicht schon im Fett-Teil erwähnt)
    if any(f["name"] == "HDL" and f["aktiv"] for f in faktoren):
        teile.append("ein erniedrigtes HDL-Cholesterin (fehlender Gefäßschutz)")

    # HbA1c
    if any(f["name"] == "HbA1c" for f in aktive):
        teile.append("einen Prädiabetes (erhöhter Langzeitblutzucker)")

    # Harnsäure
    if any(f["name"] == "Harnsäure" for f in aktive):
        teile.append("eine leichte Hyperurikämie (erhöhte Harnsäure)")

    # CRP
    if any(f["name"] == "CRP" for f in aktive):
        teile.append("Hinweise auf ein akutes oder chronisch-subklinisches Entzündungsgeschehen (erhöhtes CRP)")

    if not teile:
        return ""

    # Satz zusammenbauen
    if len(teile) == 1:
        aufzaehlung = teile[0]
    else:
        aufzaehlung = ", ".join(teile[:-1]) + " sowie " + teile[-1]

    return f"Es liegt ein metabolisches Risikoprofil mit {aufzaehlung} vor."


# ---------------------------------------------------------------------------
# Stoffwechsel-Risiko Score
# ---------------------------------------------------------------------------


def berechne_stoffwechsel_score(conn: sqlite3.Connection) -> dict:
    """Berechnet das Stoffwechsel-Risikoprofil (metabolisches Syndrom).

    Abgestufte Bewertung: schwerere Abweichungen geben mehr Punkte.
    Faktoren: Blutzucker, HbA1c, Triglyceride, HDL, Leberwerte,
    Harnsäure und BMI.

    Returns:
        dict mit keys: score, max, status, faktoren, zusammenfassung
    """
    score = 0
    max_score = 12
    faktoren = []

    # HbA1c (2 Punkte max): >6.5 = 2P (Diabetes), >5.7 = 1P (Prädiabetes)
    hba1c_val = _get_last_value(conn, "HbA1c")
    hba1c_ifcc_val = _get_last_value(conn, "HbA1c (IFCC)")

    if hba1c_val is not None:
        if hba1c_val > 6.5:
            punkte = 2
        elif hba1c_val > 5.7:
            punkte = 1
        else:
            punkte = 0
        score += punkte
        faktoren.append({"name": "HbA1c", "wert": f"{hba1c_val:.1f}%", "punkte": punkte, "max": 2, "aktiv": punkte > 0})
    elif hba1c_ifcc_val is not None:
        if hba1c_ifcc_val > 48:
            punkte = 2
        elif hba1c_ifcc_val > 39:
            punkte = 1
        else:
            punkte = 0
        score += punkte
        faktoren.append({"name": "HbA1c (IFCC)", "wert": f"{hba1c_ifcc_val:.0f}", "punkte": punkte, "max": 2, "aktiv": punkte > 0})

    # Glucose (1 Punkt): >100 nüchtern
    glucose = _get_last_value(conn, "Glucose")
    if glucose is not None:
        aktiv = glucose > 100
        if aktiv:
            score += 1
        faktoren.append({"name": "Glucose nüchtern", "wert": f"{glucose:.0f}", "punkte": 1 if aktiv else 0, "max": 1, "aktiv": aktiv})

    # Triglyceride (2 Punkte max): >200 = 2P, >150 = 1P
    trig = _get_last_value(conn, "Triglyceride")
    if trig is not None:
        if trig > 200:
            punkte = 2
        elif trig > 150:
            punkte = 1
        else:
            punkte = 0
        score += punkte
        faktoren.append({"name": "Triglyceride", "wert": f"{trig:.0f}", "punkte": punkte, "max": 2, "aktiv": punkte > 0})

    # HDL (1 Punkt): <40 = fehlender Gefäßschutz
    hdl = _get_last_value(conn, "HDL")
    if hdl is not None:
        aktiv = hdl < 40
        if aktiv:
            score += 1
        faktoren.append({"name": "HDL", "wert": f"{hdl:.0f}", "punkte": 1 if aktiv else 0, "max": 1, "aktiv": aktiv})

    # GPT (1 Punkt): >50
    gpt = _get_last_value(conn, "GPT")
    if gpt is not None:
        aktiv = gpt > 50
        if aktiv:
            score += 1
        faktoren.append({"name": "GPT", "wert": f"{gpt:.0f}", "punkte": 1 if aktiv else 0, "max": 1, "aktiv": aktiv})

    # GGT (1 Punkt): >60
    ggt = _get_last_value(conn, "GGT")
    if ggt is not None:
        aktiv = ggt > 60
        if aktiv:
            score += 1
        faktoren.append({"name": "GGT", "wert": f"{ggt:.0f}", "punkte": 1 if aktiv else 0, "max": 1, "aktiv": aktiv})

    # Harnsäure (1 Punkt): >7.0
    hs = _get_last_value(conn, "Harnsäure")
    if hs is not None:
        aktiv = hs > 7.0
        if aktiv:
            score += 1
        faktoren.append({"name": "Harnsäure", "wert": f"{hs:.1f}", "punkte": 1 if aktiv else 0, "max": 1, "aktiv": aktiv})

    # BMI (1 Punkt): >30
    bmi = _get_last_value(conn, "BMI")
    if bmi is not None:
        aktiv = bmi > 30
        if aktiv:
            score += 1
        faktoren.append({"name": "BMI", "wert": f"{bmi:.1f}", "punkte": 1 if aktiv else 0, "max": 1, "aktiv": aktiv})

    if score >= 6:
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
        "zusammenfassung": _build_stoffwechsel_zusammenfassung(faktoren),
    }


def _build_stoffwechsel_zusammenfassung(faktoren: list[dict]) -> str:
    """Generiert einen Zusammenfassungssatz für das Stoffwechsel-Risikoprofil."""
    aktive = [f for f in faktoren if f["aktiv"]]
    if not aktive:
        return "Kein erhöhtes Stoffwechsel-Risiko – alle metabolischen Parameter im Normbereich."

    teile = []

    # Blutzucker
    zucker_aktiv = [f for f in aktive if f["name"] in ("Glucose nüchtern", "HbA1c", "HbA1c (IFCC)")]
    if len(zucker_aktiv) >= 2:
        teile.append("eine Insulinresistenz bzw. Prädiabetes (Nüchternglucose und Langzeitblutzucker erhöht)")
    elif any(f["name"] == "HbA1c" or f["name"] == "HbA1c (IFCC)" for f in zucker_aktiv):
        teile.append("einen erhöhten Langzeitblutzucker (Prädiabetes)")
    elif any(f["name"] == "Glucose nüchtern" for f in zucker_aktiv):
        teile.append("eine erhöhte Nüchternglucose")

    # Lipide
    if any(f["name"] == "Triglyceride" for f in aktive):
        teile.append("erhöhte Triglyceride")
    if any(f["name"] == "HDL" for f in aktive):
        teile.append("ein erniedrigtes HDL")

    # Leber
    leber_aktiv = [f for f in aktive if f["name"] in ("GPT", "GGT")]
    if len(leber_aktiv) >= 2:
        teile.append("erhöhte Leberwerte (GPT und GGT – Hinweis auf Fettleber)")
    elif leber_aktiv:
        teile.append(f"einen erhöhten {leber_aktiv[0]['name']}-Wert")

    # Harnsäure
    if any(f["name"] == "Harnsäure" for f in aktive):
        teile.append("eine Hyperurikämie (erhöhte Harnsäure)")

    # BMI
    if any(f["name"] == "BMI" for f in aktive):
        teile.append("Adipositas (BMI > 30)")

    if not teile:
        return ""

    if len(teile) == 1:
        aufzaehlung = teile[0]
    else:
        aufzaehlung = ", ".join(teile[:-1]) + " sowie " + teile[-1]

    return f"Das Stoffwechsel-Profil zeigt {aufzaehlung}. Eine ärztliche Beratung zur Lebensstiloptimierung ist empfohlen."


# ---------------------------------------------------------------------------
# Gruppen-Summary mit Traffic-Light
# ---------------------------------------------------------------------------

def build_gruppen_summary(conn: sqlite3.Connection, datum_filter: str = "") -> list[dict]:
    """Erstellt eine Traffic-Light-Zusammenfassung aller Gruppen mit Flag-Details und Trend."""
    rows = conn.execute(f"""
        SELECT gruppe,
               COUNT(*) as anzahl,
               SUM(CASE WHEN flag = 'H' THEN 1 ELSE 0 END) as hoch_count,
               SUM(CASE WHEN flag = 'L' THEN 1 ELSE 0 END) as tief_count
        FROM laborwerte
        WHERE 1=1 {datum_filter}
        GROUP BY gruppe
        ORDER BY gruppe
    """).fetchall()

    # Vorjahresvergleich pro Gruppe (vereinfacht: Anzahl pathologischer im letzten Jahr vs. davor)
    from datetime import date, timedelta
    vor_12m = (date.today() - timedelta(days=365)).isoformat()

    gruppen = []
    for row in rows:
        name = row["gruppe"]
        anzahl = row["anzahl"]
        hoch = row["hoch_count"]
        tief = row["tief_count"]
        path_count = hoch + tief
        path_ratio = path_count / anzahl if anzahl > 0 else 0.0

        # Trend: Vergleiche aktuelle pathologische Anzahl (letztes Jahr) mit davor
        recent_path = conn.execute(
            "SELECT COUNT(*) FROM laborwerte WHERE gruppe=? AND flag IN ('H','L') AND datum >= ?",
            (name, vor_12m)
        ).fetchone()[0]
        older_path = conn.execute(
            "SELECT COUNT(*) FROM laborwerte WHERE gruppe=? AND flag IN ('H','L') AND datum < ?",
            (name, vor_12m)
        ).fetchone()[0]
        recent_total = conn.execute(
            "SELECT COUNT(*) FROM laborwerte WHERE gruppe=? AND datum >= ?",
            (name, vor_12m)
        ).fetchone()[0]
        older_total = conn.execute(
            "SELECT COUNT(*) FROM laborwerte WHERE gruppe=? AND datum < ?",
            (name, vor_12m)
        ).fetchone()[0]

        # Trend berechnen (Ratio-Vergleich)
        recent_ratio = recent_path / recent_total if recent_total > 0 else 0
        older_ratio = older_path / older_total if older_total > 0 else 0
        if older_total == 0 or recent_total == 0:
            trend = "→"
        elif recent_ratio > older_ratio + 0.05:
            trend = "↑"  # verschlechtert
        elif recent_ratio < older_ratio - 0.05:
            trend = "↓"  # verbessert
        else:
            trend = "→"  # stabil

        gc = GROUP_CONFIG.get(name, {})
        gruppen.append({
            "name": name,
            "icon": gc.get("icon", "📋"),
            "status": classify_traffic_light(path_count, anzahl),
            "anzahl": anzahl,
            "pathologisch": path_count,
            "hoch": hoch,
            "tief": tief,
            "trend": trend,
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
        - ("→", "unverändert") wenn Änderung < 5%
        - ("↑", "verschlechtert") wenn Wert sich in pathologische Richtung bewegt
        - ("↓", "verbessert") wenn Wert sich Richtung Normalbereich bewegt
    """
    if previous == 0:
        return ("→", "unverändert")

    change_pct = abs(current - previous) / abs(previous)

    if change_pct < 0.05:
        return ("→", "unverändert")

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

def build_abnormal_tests(conn: sqlite3.Connection, datum_filter: str = "") -> list[dict]:
    """Sammelt alle Tests mit pathologischem Flag auf der letzten Messung.

    Args:
        conn: SQLite-Datenbankverbindung.
        datum_filter: SQL-Fragment für Datumsfilter (z.B. " AND datum >= '2025-07-07'").

    Returns:
        Liste von Dicts.
    """
    # Letzter Wert pro Test, nur mit H/L-Flag
    rows = conn.execute(f"""
        SELECT l.datum, l.gruppe, l.test_standard, l.wert_norm, l.einheit_norm,
               l.normbereich, l.flag
        FROM laborwerte l
        WHERE l.flag IN ('H', 'L')
        {datum_filter}
        AND l.datum = (
            SELECT MAX(l2.datum) FROM laborwerte l2
            WHERE l2.test_standard = l.test_standard AND l2.flag IN ('H','L')
            {datum_filter}
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
        trend_label = "unverändert"
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
            "name": test_name,
            "kurzname": KURZNAMEN.get(test_name, ""),
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


def _get_abnormal_test_names(conn: sqlite3.Connection, datum_filter: str = "") -> set[str]:
    """Gibt die Testnamen zurück die im Zeitraum einen auffälligen Wert haben."""
    rows = conn.execute(f"""
        SELECT DISTINCT test_standard FROM laborwerte
        WHERE flag IN ('H','L') {datum_filter}
    """).fetchall()
    return {r["test_standard"] for r in rows}


def _build_normal_tests(conn: sqlite3.Connection, datum_filter: str = "", exclude_tests: set = None) -> list[dict]:
    """Sammelt alle Tests deren letzter Wert im gewählten Zeitraum im Normbereich liegt."""
    rows = conn.execute(f"""
        SELECT l.test_standard, l.gruppe, l.wert_norm, l.einheit_norm
        FROM laborwerte l
        WHERE l.datum = (SELECT MAX(l2.datum) FROM laborwerte l2 WHERE l2.test_standard = l.test_standard)
        AND (l.flag IS NULL OR l.flag = '')
        {datum_filter}
        GROUP BY l.test_standard
        ORDER BY l.gruppe, l.test_standard
    """).fetchall()

    results = []
    if exclude_tests is None:
        exclude_tests = set()
    for row in rows:
        if row["test_standard"] in exclude_tests:
            continue
        results.append({
            "name": row["test_standard"],
            "kurzname": KURZNAMEN.get(row["test_standard"], ""),
            "gruppe": row["gruppe"],
            "wert": row["wert_norm"],
            "einheit": row["einheit_norm"] or "",
        })
    return results


# ---------------------------------------------------------------------------
# Haupt-Orchestrator
# ---------------------------------------------------------------------------

def build_report_data(conn: sqlite3.Connection, befunde_count: int = 0, von: str = "", bis: str = "") -> dict:
    """Orchestriert alle Datensammlung für den Gesamtbericht.

    Args:
        conn: DB-Verbindung.
        befunde_count: Anzahl der letzten Befunde (0=alle, legacy).
        von: Start-Jahr (YYYY), leer = ab Anfang.
        bis: End-Jahr (YYYY), leer = bis heute.

    Returns:
        Dict mit allen Report-Sektionen.
    """
    from datetime import datetime
    from app.config.settings import get_patient_config, get_gesamtbericht_bemerkung
    from app.core.vergleich import berechne_vorjahresvergleich

    bemerkung = get_gesamtbericht_bemerkung()

    # Zeitraum-Filter: Von/Bis hat Vorrang vor befunde_count
    datum_filter = ""
    period_display = "Gesamter Zeitraum"

    if von or bis:
        parts = []
        if von:
            parts.append(f"datum >= '{von}-01-01'")
        if bis:
            parts.append(f"datum <= '{bis}-12-31'")
        datum_filter = " AND " + " AND ".join(parts)
        period_display = f"{von or 'Anfang'} – {bis or 'Heute'}"
    elif befunde_count > 0:
        befund_rows = conn.execute(
            "SELECT DISTINCT datum FROM befunde ORDER BY datum DESC LIMIT ?",
            (befunde_count,)
        ).fetchall()
        if befund_rows:
            aeltestes_datum = befund_rows[-1]["datum"]
            neuestes_datum = befund_rows[0]["datum"]
            period_display = f"Letzte{'r' if befunde_count == 1 else ''} {befunde_count} Befund{'e' if befunde_count > 1 else ''} ({aeltestes_datum} – {neuestes_datum})"
            datum_filter = f" AND datum >= '{aeltestes_datum}'"

    return {
        "patient": get_patient_config(),
        "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "period_label": period_display,
        "bemerkung": bemerkung,
        "gruppen": build_gruppen_summary(conn, datum_filter=datum_filter),
        "gefaess_score": berechne_gefaess_score(conn),
        "stoffwechsel_score": berechne_stoffwechsel_score(conn),
        "abnormal_tests": build_abnormal_tests(conn, datum_filter=datum_filter),
        "normal_tests": _build_normal_tests(conn, datum_filter=datum_filter, exclude_tests=_get_abnormal_test_names(conn, datum_filter)),
        "verknuepfung_charts": build_verknuepfung_charts(conn),
        "vergleich": berechne_vorjahresvergleich(conn),
        "vergleich_zusammenfassung": _build_vergleich_zusammenfassung(berechne_vorjahresvergleich(conn)),
    }


# ---------------------------------------------------------------------------
# Vorjahresvergleich Zusammenfassung
# ---------------------------------------------------------------------------

def _build_vergleich_zusammenfassung(vergleich: dict) -> dict:
    """Generiert eine dynamische Zusammenfassung des Vorjahresvergleichs.

    Returns:
        dict mit: text (Fließtext), details (Liste mit Einzelbeschreibungen)
    """
    verschlechtert = vergleich.get("verschlechtert", [])
    verbessert = vergleich.get("verbessert", [])

    if not verschlechtert and not verbessert:
        return {"text": "Im Vergleich zum Vorjahr keine signifikanten Veränderungen.", "details": []}

    # Kategorisierung der Verschlechterungen
    fett_tests = {"Triglyceride", "Cholesterin", "Non-HDL-Cholesterin", "LDL", "HDL", "Quotient Chol/HDL", "Quotient LDL/HDL"}
    zucker_tests = {"HbA1c", "HbA1c (IFCC)", "Glucose"}
    niere_tests = {"GFR", "Kreatinin", "Harnstoff"}
    entzuendung_tests = {"CRP", "Leukozyten", "Interleukin-6"}
    gerinnung_tests = {"Quick", "INR", "aPTT"}

    v_names = {v["test"] for v in verschlechtert}

    teile = []

    # Fettstoffwechsel
    fett_treffer = v_names & fett_tests
    if fett_treffer:
        if len(fett_treffer) >= 3:
            teile.append("einer massiven Progression der Fettstoffwechselstörung")
        elif len(fett_treffer) >= 2:
            teile.append("einer deutlichen Verschlechterung der Blutfettwerte")
        else:
            teile.append(f"einer Verschlechterung bei {', '.join(fett_treffer)}")

    # Zucker
    zucker_treffer = v_names & zucker_tests
    if zucker_treffer:
        teile.append("einer metabolischen Verschlechterung in Richtung Diabetes (Anstieg des Langzeitblutzuckers)")

    # Niere
    niere_treffer = v_names & niere_tests
    if niere_treffer:
        teile.append("einer beginnenden Einschränkung der Nierenfunktion")

    # Entzündung
    entz_treffer = v_names & entzuendung_tests
    if entz_treffer:
        if len(entz_treffer) >= 2:
            teile.append("Zeichen einer akuten Immunreaktion mit Entzündungsgeschehen")
        else:
            teile.append(f"Hinweisen auf Entzündung ({', '.join(entz_treffer)} erhöht)")

    # Gerinnung
    ger_treffer = v_names & gerinnung_tests
    if ger_treffer:
        teile.append("Veränderungen der Blutgerinnung")

    # Sonstige
    sonstige = v_names - fett_tests - zucker_tests - niere_tests - entzuendung_tests - gerinnung_tests
    if sonstige and not teile:
        teile.append(f"Verschlechterung bei {', '.join(sorted(sonstige))}")

    # Verbesserungen erwähnen
    verb_teil = ""
    if verbessert:
        verb_namen = [v["test"] for v in verbessert[:3]]
        verb_teil = f", während sich {', '.join(verb_namen)} verbessert zeig{'en' if len(verb_namen) > 1 else 't'}"

    # Zusammenfassung bauen
    if teile:
        if len(teile) == 1:
            aufzaehlung = teile[0]
        else:
            aufzaehlung = ", ".join(teile[:-1]) + " sowie " + teile[-1]
        text = f"Im Vergleich zum Vorjahr zeigt sich eine Befundverschlechterung mit {aufzaehlung}{verb_teil}."
    elif verbessert:
        text = f"Im Vergleich zum Vorjahr zeigen sich Verbesserungen bei {', '.join(v['test'] for v in verbessert[:4])}."
    else:
        text = ""

    # Details: Wichtigste Veränderungen
    details = []
    # Verschlechtert (nach abs(pct) sortiert, Top 8)
    for v in sorted(verschlechtert, key=lambda x: abs(x.get("pct", 0)), reverse=True)[:8]:
        pct = v.get("pct", 0)
        pct_str = f"+{pct}%" if pct > 0 else f"{pct}%"

        # Dynamische Beschreibung pro Test
        beschreibung = _detail_beschreibung(v["test"], pct)
        details.append({
            "test": v["test"],
            "wert": v.get("aktuell", ""),
            "pct": pct_str,
            "richtung": "verschlechtert",
            "beschreibung": beschreibung,
        })

    return {"text": text, "details": details}


def _detail_beschreibung(test: str, pct: int) -> str:
    """Generiert eine kurze medizinische Beschreibung der Veränderung."""
    abs_pct = abs(pct)

    # Intensitäts-Prefix
    if abs_pct > 200:
        intensitaet = "Massiver"
    elif abs_pct > 100:
        intensitaet = "Drastischer"
    elif abs_pct > 50:
        intensitaet = "Starker"
    elif abs_pct > 20:
        intensitaet = "Deutlicher"
    else:
        intensitaet = "Leichter"

    beschreibungen = {
        "CRP": f"{intensitaet} Anstieg – akutes Entzündungsgeschehen",
        "Triglyceride": f"{intensitaet} Anstieg der Blutfette",
        "Cholesterin": f"Gesamtcholesterin {intensitaet.lower()} erhöht",
        "Non-HDL-Cholesterin": f"{intensitaet} Anstieg der gefäßschädigenden Cholesterinanteile",
        "LDL": f"LDL-Cholesterin {intensitaet.lower()} verschlechtert",
        "Quotient Chol/HDL": f"Cholesterin-Verhältnis {intensitaet.lower()} verschlechtert",
        "Quick": f"{intensitaet} beschleunigte Blutgerinnung",
        "Leukozyten": "Veränderung der weißen Blutkörperchen",
        "GFR": "Rückgang der Nierenfiltrationsleistung – Nierenwerte kontrollieren",
        "HbA1c": "Anstieg des Langzeitblutzuckers – Trend zum Diabetes",
        "HbA1c (IFCC)": "Anstieg des Langzeitblutzuckers (IFCC)",
        "Harnsäure": "Anstieg der Harnsäure – Gichtrisiko",
        "Hämatokrit": "Veränderung der Blutdicke",
        "Hämoglobin": "Veränderung des roten Blutfarbstoffs",
    }

    return beschreibungen.get(test, f"{intensitaet} Veränderung")
