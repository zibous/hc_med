"""API: /overview – Übersicht mit KPIs und Gruppen."""

from fastapi import APIRouter

from app.config.settings import GROUP_CONFIG, GROUP_DESCRIPTIONS
from app.core.vergleich import berechne_vorjahresvergleich
from app.infrastructure.database import get_db

router = APIRouter(prefix="/api", tags=["labor"])


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

            # Letzte 3 auffällige Tests dieser Gruppe (nur wenn AKTUELLER Wert auffällig)
            letzte_path = conn.execute("""
                SELECT l.test_standard, l.wert_norm, l.einheit_norm, l.flag, l.datum
                FROM laborwerte l
                WHERE l.gruppe=? AND l.flag IN ('H','L')
                AND l.datum = (
                    SELECT MAX(l2.datum) FROM laborwerte l2
                    WHERE l2.test_standard = l.test_standard
                )
                ORDER BY l.datum DESC LIMIT 3
            """, (name,)).fetchall()

            # Trend: Anzahl Messungen pro Jahr für Sparkline
            jahres_trend = conn.execute("""
                SELECT substr(datum,1,4) as jahr, COUNT(*) as n
                FROM laborwerte WHERE gruppe=?
                GROUP BY jahr ORDER BY jahr
            """, (name,)).fetchall()

            # Bewertung: Anteil aktuell auffälliger Tests (nicht historisch)
            aktuell_path = conn.execute("""
                SELECT COUNT(DISTINCT l.test_standard) FROM laborwerte l
                WHERE l.gruppe=? AND l.flag IN ('H','L')
                AND l.datum = (
                    SELECT MAX(l2.datum) FROM laborwerte l2
                    WHERE l2.test_standard = l.test_standard
                )
            """, (name,)).fetchone()[0]
            
            aktuell_total = conn.execute("""
                SELECT COUNT(DISTINCT test_standard) FROM laborwerte WHERE gruppe=?
            """, (name,)).fetchone()[0]
            
            path_ratio = aktuell_path / aktuell_total if aktuell_total > 0 else 0
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

        # Vorjahresvergleich
        vergleich = berechne_vorjahresvergleich(conn)

        # Gefäßgesundheit Score
        gefaess = _berechne_gefaess_score(conn)

        return {
            "kpis": {
                "messwerte": total,
                "befunde": befunde,
                "pathologisch": pathologisch,
                "zeitraum_von": zeitraum[0],
                "zeitraum_bis": zeitraum[1],
            },
            "gruppen": gruppen,
            "vergleich": vergleich,
            "gefaess": gefaess,
        }
    finally:
        conn.close()


def _berechne_gefaess_score(conn) -> dict:
    """Berechnet einen Gefäßgesundheit-Score aus den aktuellen Werten."""
    def get_last(test):
        row = conn.execute(
            "SELECT wert_norm FROM laborwerte WHERE test_standard=? ORDER BY datum DESC LIMIT 1", (test,)
        ).fetchone()
        if not row: return None
        try: return float(str(row[0]).replace(",", ".").replace("<", "").replace(">", ""))
        except: return None

    ldl = get_last("LDL")
    hdl = get_last("HDL")
    trig = get_last("Triglyceride")
    crp = get_last("CRP")
    hba1c = get_last("HbA1c")
    hs = get_last("Harnsäure")

    score = 0
    max_score = 8
    details = []
    if trig and trig > 200: score += 2; details.append(f"Triglyceride {trig:.0f} ↑")
    if crp and crp > 0.5: score += 2; details.append(f"CRP {crp:.1f} ↑")
    if hba1c and hba1c > 5.7: score += 1; details.append(f"HbA1c {hba1c:.1f}% ↑")
    if ldl and ldl > 130: score += 1; details.append(f"LDL {ldl:.0f} ↑")
    if hs and hs > 7.0: score += 1; details.append(f"Harnsäure {hs:.1f} ↑")
    if hdl and hdl < 40: score += 1; details.append(f"HDL {hdl:.0f} ↓")

    if score >= 5: status = "kritisch"
    elif score >= 3: status = "auffällig"
    else: status = "gut"

    return {"score": score, "max": max_score, "status": status, "details": details}
