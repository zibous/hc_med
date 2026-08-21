"""API: /vergleich – Mehrzeitraum-Vergleich als Pivot-Tabelle.

Zeigt pro Test den aktuellen Wert und die letzten 5 vorherigen Messungen
(analog zum Trend-Chart), statt fester Jahres-Zeitfenster.
"""

from datetime import date, timedelta

from fastapi import APIRouter

from app.config.settings import KURZNAMEN
from app.infrastructure.database import get_db

router = APIRouter(prefix="/api", tags=["labor"])

# Maximale Anzahl historischer Messungen pro Test
_MAX_HISTORY = 5


def _parse_float(val: str) -> float | None:
    """Parst einen Laborwert als Float."""
    try:
        return float(str(val).replace(",", ".").replace("<", "").replace(">", ""))
    except (ValueError, TypeError):
        return None


def _bewertung(aktuell_flag: str, vergleich_flag: str, aktuell_val: float, vergleich_val: float) -> str:
    """Bewertet die Veränderung zwischen zwei Zeitpunkten.

    Returns: 'verbessert', 'verschlechtert', 'stabil', 'neu_auffällig', 'normalisiert'
    """
    if vergleich_flag in ("H", "L") and not aktuell_flag:
        return "normalisiert"
    if not vergleich_flag and aktuell_flag in ("H", "L"):
        return "neu_auffällig"

    if vergleich_flag in ("H", "L") and aktuell_flag in ("H", "L"):
        if aktuell_flag == "H":
            if aktuell_val < vergleich_val:
                return "verbessert"
            elif aktuell_val > vergleich_val:
                return "verschlechtert"
        elif aktuell_flag == "L":
            if aktuell_val > vergleich_val:
                return "verbessert"
            elif aktuell_val < vergleich_val:
                return "verschlechtert"

    # Beide normal oder gleicher Flag – prozentuale Änderung bewerten
    if vergleich_val and vergleich_val != 0:
        pct = (aktuell_val - vergleich_val) / vergleich_val * 100
        if abs(pct) < 5:
            return "stabil"
        # Aktuell pathologisch → Richtung bestimmt Bewertung
        if aktuell_flag == "H":
            return "verschlechtert" if aktuell_val > vergleich_val else "verbessert"
        if aktuell_flag == "L":
            return "verschlechtert" if aktuell_val < vergleich_val else "verbessert"

    return "stabil"


def _datum_label(datum_str: str, heute: date) -> str:
    """Erstellt ein lesbares Label für das Datum relativ zu heute.

    Beispiele: 'vor 1 J.', 'vor 2 J.', 'vor 6 Mon.', '2019-04'
    """
    try:
        parts = datum_str.split("-")
        d = date(int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 1)
    except (ValueError, IndexError):
        return datum_str

    diff_days = (heute - d).days
    if diff_days < 45:
        return "vor 1 Mon."
    elif diff_days < 320:
        monate = round(diff_days / 30)
        return f"vor {monate} Mon."
    else:
        jahre = round(diff_days / 365, 1)
        if jahre == int(jahre):
            return f"vor {int(jahre)} J."
        return f"vor {jahre:.1f} J."


@router.get("/vergleich")
async def vergleich_pivot():
    """Pivot-Tabelle: Tests × letzte Messungen mit Bewertung.

    Zeigt pro Test die letzten 5 vorherigen Messungen (wie im Trend-Chart),
    statt fester Jahres-Zeitfenster. So fehlen keine historischen Daten.
    """
    conn = get_db()
    try:
        heute = date.today()
        vor_12m = (heute - timedelta(days=365)).isoformat()

        # Alle Tests mit aktuellem Wert (letzter Wert im letzten Jahr)
        aktuelle = conn.execute("""
            SELECT test_standard, gruppe, wert_norm, einheit_norm, normbereich, flag, datum
            FROM laborwerte l1
            WHERE datum = (SELECT MAX(datum) FROM laborwerte l2 WHERE l2.test_standard = l1.test_standard)
            AND datum >= ?
            GROUP BY test_standard
            ORDER BY gruppe, test_standard
        """, (vor_12m,)).fetchall()

        results = []
        for row in aktuelle:
            test = row["test_standard"]
            aktuell_val = _parse_float(row["wert_norm"])
            aktuell_datum = row["datum"]
            if aktuell_val is None:
                continue

            # Letzte N Messungen VOR dem aktuellen Wert
            history_rows = conn.execute("""
                SELECT wert_norm, flag, datum FROM laborwerte
                WHERE test_standard = ? AND datum < ?
                ORDER BY datum DESC LIMIT ?
            """, (test, aktuell_datum, _MAX_HISTORY)).fetchall()

            if not history_rows:
                continue  # Nur 1 Messung → kein Vergleich möglich

            entry = {
                "test": test,
                "kurzname": KURZNAMEN.get(test, ""),
                "gruppe": row["gruppe"],
                "aktuell": row["wert_norm"],
                "einheit": row["einheit_norm"] or "",
                "norm": row["normbereich"] or "",
                "flag": row["flag"] or "",
                "datum": aktuell_datum,
                "zeitraeume": [],
            }

            hat_aenderung = False

            for idx, hist in enumerate(history_rows):
                hist_val = _parse_float(hist["wert_norm"])
                hist_datum = hist["datum"]
                label = _datum_label(hist_datum, heute)

                if hist_val is None:
                    entry["zeitraeume"].append({
                        "label": label,
                        "wert": hist["wert_norm"],
                        "datum": hist_datum,
                        "bewertung": None,
                    })
                    continue

                bewertung = _bewertung(
                    row["flag"] or "", hist["flag"] or "", aktuell_val, hist_val
                )

                # Nur die ERSTE Messung (direkt vorherige) entscheidet ob der Test angezeigt wird
                if idx == 0 and bewertung != "stabil":
                    hat_aenderung = True

                pct = round((aktuell_val - hist_val) / hist_val * 100) if hist_val != 0 else 0

                entry["zeitraeume"].append({
                    "label": label,
                    "wert": hist["wert_norm"],
                    "flag": hist["flag"] or "",
                    "datum": hist_datum,
                    "pct": pct,
                    "bewertung": bewertung,
                })

            # NUR Tests mit aktuellem Flag (H/L) anzeigen
            aktuell_flag = row["flag"] or ""
            if aktuell_flag in ("H", "L"):
                results.append(entry)

        # Sortierung: verschlechtert/neu_auffällig zuerst
        def sort_key(item):
            worst = 0
            for zr in item["zeitraeume"]:
                b = zr.get("bewertung", "")
                if b == "neu_auffällig":
                    worst = max(worst, 4)
                elif b == "verschlechtert":
                    worst = max(worst, 3)
                elif b == "verbessert":
                    worst = max(worst, 2)
                elif b == "normalisiert":
                    worst = max(worst, 1)
            return -worst

        results.sort(key=sort_key)

        # Spalten-Labels: dynamisch aus den Daten (max Anzahl)
        max_cols = max((len(r["zeitraeume"]) for r in results), default=0)

        return {
            "tests": results,
            "anzahl": len(results),
            "max_cols": max_cols,
        }
    finally:
        conn.close()
