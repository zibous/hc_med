"""API: /overview – Übersicht mit KPIs und Gruppen."""

from fastapi import APIRouter

from app.config.settings import GROUP_CONFIG, GROUP_DESCRIPTIONS
from app.core.gesamtbericht_data import berechne_gefaess_score, berechne_stoffwechsel_score
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
            # Nur Tests berücksichtigen deren letzte Messung max. 3 Jahre alt ist
            aktuell_path = conn.execute("""
                SELECT COUNT(DISTINCT l.test_standard) FROM laborwerte l
                WHERE l.gruppe=? AND l.flag IN ('H','L')
                AND l.datum = (
                    SELECT MAX(l2.datum) FROM laborwerte l2
                    WHERE l2.test_standard = l.test_standard
                )
                AND l.datum >= date('now', '-3 years')
            """, (name,)).fetchone()[0]

            aktuell_total = conn.execute("""
                SELECT COUNT(DISTINCT l.test_standard) FROM laborwerte l
                WHERE l.gruppe=?
                AND l.datum = (
                    SELECT MAX(l2.datum) FROM laborwerte l2
                    WHERE l2.test_standard = l.test_standard
                )
                AND l.datum >= date('now', '-3 years')
            """, (name,)).fetchone()[0]

            # Basis-Bewertung: Anteil der Tests deren LETZTER Wert auffällig ist
            path_ratio = aktuell_path / aktuell_total if aktuell_total > 0 else 0
            if path_ratio == 0:
                status = "gut"
            elif path_ratio < 0.20:
                status = "ok"
            elif path_ratio < 0.40:
                status = "auffällig"
            else:
                status = "kritisch"

            # Hochstufung: Ein Test mit ≥5 Messungen UND die letzten 3 alle auffällig
            # macht die Gruppe "kritisch" – zeigt dauerhaftes Problem an
            if status == "auffällig" and aktuell_path > 0:
                auff_tests = conn.execute("""
                    SELECT DISTINCT l.test_standard FROM laborwerte l
                    WHERE l.gruppe=? AND l.flag IN ('H','L')
                    AND l.datum = (SELECT MAX(l2.datum) FROM laborwerte l2
                                   WHERE l2.test_standard = l.test_standard)
                """, (name,)).fetchall()

                for t in auff_tests:
                    total_count = conn.execute(
                        "SELECT COUNT(*) FROM laborwerte WHERE test_standard=?", (t[0],)
                    ).fetchone()[0]
                    if total_count < 5:
                        continue

                    letzte3 = conn.execute("""
                        SELECT flag FROM laborwerte
                        WHERE test_standard=?
                        ORDER BY datum DESC LIMIT 3
                    """, (t[0],)).fetchall()
                    path_count = sum(1 for r in letzte3 if r["flag"] in ("H", "L"))
                    if path_count >= 3:
                        status = "kritisch"
                        break

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
        gefaess = berechne_gefaess_score(conn)

        # Stoffwechsel-Risikoprofil
        stoffwechsel = berechne_stoffwechsel_score(conn)

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
            "stoffwechsel": stoffwechsel,
        }
    finally:
        conn.close()
