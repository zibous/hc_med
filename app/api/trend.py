"""API: /trend/{test} – Zeitreihe für einen einzelnen Test."""

from fastapi import APIRouter, HTTPException

from app.config.settings import TEST_DESCRIPTIONS, EREIGNISSE, VERKNUEPFUNGEN, KURZNAMEN, NUECHTERN_SENSITIV
from app.core.empfehlungen import get_test_empfehlung
from app.core.bewertung import bewerte_trend
from app.infrastructure.database import get_db

router = APIRouter(prefix="/api", tags=["labor"])


@router.get("/trend/{test:path}")
async def trend(test: str):
    """Zeitreihe für einen einzelnen Test."""
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT l.datum, l.wert_norm, l.einheit_norm, l.normbereich, l.flag, l.alter_bei_messung,
                      b.nuechtern
               FROM laborwerte l
               JOIN befunde b ON b.id = l.befund_id
               WHERE l.test_standard=? ORDER BY l.datum""",
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
        bewertung, bewertung_status = bewerte_trend(
            [{"wert_norm": r["wert_norm"], "flag": r["flag"], "einheit_norm": r["einheit_norm"], "normbereich": r["normbereich"]} for r in rows]
        )

        last_val = rows[-1]["wert_norm"] if rows else ""
        last_flag = rows[-1]["flag"] if rows else ""

        # Test-spezifische Empfehlung
        trend_empfehlung = get_test_empfehlung(test, last_val, last_flag, normbereich, conn)

        # Nüchtern-Hinweis: Prüfen ob nicht-nüchtern-Befunde vorhanden sind
        nuechtern_hinweis = ""
        if test in NUECHTERN_SENSITIV:
            nicht_nuechtern = conn.execute("""
                SELECT COUNT(*) FROM laborwerte l
                JOIN befunde b ON b.id = l.befund_id
                WHERE l.test_standard = ? AND b.nuechtern = 0
            """, (test,)).fetchone()[0]
            if nicht_nuechtern:
                nuechtern_hinweis = f"⚠️ Dieser Test ist nüchtern-sensitiv. {nicht_nuechtern} von {len(rows)} Messungen wurden NICHT nüchtern durchgeführt – diese Werte können deutlich verfälscht sein."

        return {
            "test": test,
            "kurzname": KURZNAMEN.get(test, ""),
            "beschreibung": TEST_DESCRIPTIONS.get(test, ""),
            "einheit": rows[0]["einheit_norm"],
            "normbereich": normbereich,
            "bewertung": bewertung,
            "bewertung_empfehlung": trend_empfehlung,
            "bewertung_status": bewertung_status,
            "nuechtern_hinweis": nuechtern_hinweis,
            "werte": [
                {**dict(r), "nicht_nuechtern": (test in NUECHTERN_SENSITIV and r["nuechtern"] == 0)}
                for r in rows
            ],
            "ereignisse": relevante_ereignisse,
            "verknuepfungen": verwandte,
        }
    finally:
        conn.close()
