"""API: /bericht und /bericht/charts – Arztberichte als druckfertiges HTML."""

import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config.settings import TEST_DESCRIPTIONS, KURZNAMEN, get_patient_config
from app.core.empfehlungen import get_test_empfehlung
from app.core.norm_bar import norm_bar_html
from app.core.vergleich import berechne_vorjahresvergleich
from app.infrastructure.database import get_db

router = APIRouter(prefix="/api", tags=["labor"])

TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
templates.env.globals["norm_bar_html"] = norm_bar_html

PERIOD_LABELS = {"1m": "Letzter Monat", "6m": "Letzte 6 Monate", "1y": "Letztes Jahr", "all": "Gesamter Zeitraum"}


def _build_zusammenfassung(tests_data: list) -> dict:
    """Erstellt eine Zusammenfassung für den Berichtskopf."""
    kritisch = [t for t in tests_data if t["bewertung_cls"] == "crit"]
    auffaellig = [t for t in tests_data if t["bewertung_cls"] == "warn"]
    gut = [t for t in tests_data if t["bewertung_cls"] == "gut"]

    # Gesamtbewertung
    if kritisch:
        status = "kritisch"
        status_text = "Laborwerte"
        status_icon = "🚨"
    elif auffaellig:
        status = "auffällig"
        status_text = "Einige Werte beobachten"
        status_icon = "⚠️"
    else:
        status = "gut"
        status_text = "Alle Werte unauffällig"
        status_icon = "✅"

    # Wichtigste Punkte (max 5)
    punkte = []
    for t in kritisch[:3]:
        kurzname = KURZNAMEN.get(t["name"], "")
        prefix = f"{kurzname} " if kurzname else ""
        punkte.append(f"🚨 {prefix}{t['name']}: {t['bewertung']}")
        if t.get("empfehlung"):
            punkte.append(f"   💡 {t['empfehlung'][:150]}")
    for t in auffaellig[:3]:
        if len(punkte) < 8:
            kurzname = KURZNAMEN.get(t["name"], "")
            prefix = f"{kurzname} " if kurzname else ""
            punkte.append(f"⚠️ {prefix}{t['name']}: letzter Wert {t['values'][-1]} {t['einheit']} (Norm: {t['norm']})")

    return {
        "status": status,
        "status_text": status_text,
        "status_icon": status_icon,
        "kritisch_count": len(kritisch),
        "auffaellig_count": len(auffaellig),
        "gut_count": len(gut),
        "total": len(tests_data),
        "punkte": punkte,
    }


def _period_filter(query: str, period: str) -> str:
    """Fügt eine Datums-Filterbedingung zur Query hinzu."""
    if period == "1m":
        return query + " AND datum >= date('now', '-1 month')"
    elif period == "6m":
        return query + " AND datum >= date('now', '-6 months')"
    elif period == "1y":
        return query + " AND datum >= date('now', '-1 year')"
    return query


@router.get("/bericht/charts", response_class=HTMLResponse)
async def bericht_charts(request: Request, befunde: int = 0, period: str = "", sort: str = "datum", dir: int = -1, von: str = "", bis: str = ""):
    """Arztbericht mit Verlaufs-Charts pro auffälligem Test."""
    # Fallback: alte period-Parameter auf befunde mappen
    if not befunde and period and period not in ("all", ""):
        try:
            befunde = int(period)
        except ValueError:
            befunde = 0
    conn = get_db()
    try:
        # Jahres-Filter oder Befunde-Filter
        datum_filter = ""
        period_label = "Gesamter Zeitraum"

        if von or bis:
            parts = []
            if von:
                parts.append(f"datum >= '{von}-01-01'")
            if bis:
                parts.append(f"datum <= '{bis}-12-31'")
            datum_filter = " AND " + " AND ".join(parts)
            period_label = f"{von or 'Anfang'} – {bis or 'Heute'}"
        elif befunde > 0:
            befund_rows = conn.execute(
                "SELECT DISTINCT datum FROM befunde ORDER BY datum DESC LIMIT ?",
                (befunde,)
            ).fetchall()
            if befund_rows:
                aeltestes_datum = befund_rows[-1]["datum"]
                datum_filter = f" AND datum >= '{aeltestes_datum}'"
                period_label = f"Letzte {befunde} Befunde (ab {aeltestes_datum})"

        path_query = f"""
            SELECT l.test_standard, l.gruppe, l.flag, l.datum
            FROM laborwerte l
            WHERE l.flag IN ('H', 'L')
            {datum_filter}
            AND l.datum = (
                SELECT MAX(l3.datum) FROM laborwerte l3
                WHERE l3.test_standard = l.test_standard AND l3.flag IN ('H','L')
                {datum_filter}
            )
            GROUP BY l.test_standard
            ORDER BY l.datum DESC, l.gruppe
        """
        path_rows = conn.execute(path_query).fetchall()
        test_order = [(r["test_standard"], r["gruppe"], r["flag"], r["datum"]) for r in path_rows]

        tests_data = []
        for test, gruppe, last_flag, last_datum in test_order:
            rows = conn.execute(
                "SELECT datum, wert_norm, einheit_norm, normbereich, flag FROM laborwerte WHERE test_standard=? ORDER BY datum",
                (test,),
            ).fetchall()
            if not rows:
                continue

            norm = next((r["normbereich"] for r in rows if r["normbereich"] and any(c.isdigit() for c in r["normbereich"])), "")

            recent = rows[-5:] if len(rows) >= 5 else rows
            recent_ratio = sum(1 for r in recent if r["flag"] in ("H", "L")) / len(recent)
            last = rows[-1]

            if recent_ratio == 0:
                bew, bew_cls = f"✅ Im Normbereich ({last['wert_norm']} {last['einheit_norm'] or ''})", "gut"
            elif recent_ratio < 0.5:
                bew, bew_cls = f"⚠️ Teilweise auffällig – letzter Wert: {last['wert_norm']} {last['einheit_norm'] or ''}", "warn"
            else:
                bew, bew_cls = f"🚨 Kritisch – letzter Wert: {last['wert_norm']} {last['einheit_norm'] or ''} (Norm: {norm})", "crit"

            tests_data.append({
                "name": test, "gruppe": gruppe,
                "beschreibung": TEST_DESCRIPTIONS.get(test, ""),
                "einheit": rows[0]["einheit_norm"] or "", "norm": norm,
                "bewertung": bew, "bewertung_cls": bew_cls,
                "flag": last_flag or "",
                "datum": last_datum or "",
                "empfehlung": get_test_empfehlung(test, last["wert_norm"], last["flag"], norm, conn),
                "labels": [r["datum"] for r in rows],
                "values": [r["wert_norm"] for r in rows],
                "flags": [r["flag"] for r in rows],
            })
    finally:
        conn.close()

    # Keine serverseitige Sortierung – wird im Bericht-JS clientseitig gemacht
    # (gleiche Logik wie in cards.js, vermeidet Inkonsistenzen)

    return templates.TemplateResponse("bericht_charts.html", {
        "request": request,
        "now": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "period_label": period_label,
        "patient": get_patient_config(),
        "tests_data": tests_data,
        "charts_json": json.dumps(tests_data, ensure_ascii=False),
        "zusammenfassung": _build_zusammenfassung(tests_data),
        "vergleich": berechne_vorjahresvergleich(get_db()),
    })


@router.get("/bericht", response_class=HTMLResponse)
async def bericht(request: Request, period: str = "1m"):
    """Arztbericht als druckfertiges HTML (Tabellen-Format)."""
    conn = get_db()
    try:
        query = "SELECT datum, gruppe, test_standard, wert_norm, einheit_norm, normbereich, flag FROM laborwerte WHERE flag IN ('H', 'L')"
        query = _period_filter(query, period)
        query += " ORDER BY gruppe, test_standard, datum DESC"
        path_rows = conn.execute(query).fetchall()

        alle_aktuell = conn.execute("""
            SELECT l.gruppe, l.test_standard, l.wert_norm, l.einheit_norm, l.normbereich, l.flag, l.datum
            FROM laborwerte l
            WHERE l.datum = (SELECT MAX(l2.datum) FROM laborwerte l2 WHERE l2.test_standard = l.test_standard)
            GROUP BY l.test_standard ORDER BY l.gruppe, l.test_standard
        """).fetchall()

        total = conn.execute("SELECT COUNT(*) FROM laborwerte").fetchone()[0]
        path_total = conn.execute("SELECT COUNT(*) FROM laborwerte WHERE flag IN ('H','L')").fetchone()[0]
        zeitraum = conn.execute("SELECT MIN(datum), MAX(datum) FROM laborwerte").fetchone()
    finally:
        conn.close()

    # Gruppieren
    gruppen_path = {}
    for r in path_rows:
        gruppen_path.setdefault(r["gruppe"], []).append(dict(r))

    return templates.TemplateResponse("bericht_tabelle.html", {
        "request": request,
        "now": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "period_label": PERIOD_LABELS.get(period, period),
        "patient": get_patient_config(),
        "total": total, "path_total": path_total,
        "norm_pct": round((total - path_total) / total * 100) if total > 0 else 100,
        "zeitraum_von": zeitraum[0], "zeitraum_bis": zeitraum[1],
        "gruppen_path": gruppen_path,
        "alle_aktuell": [dict(r) for r in alle_aktuell],
        "beschreibungen": TEST_DESCRIPTIONS,
    })
