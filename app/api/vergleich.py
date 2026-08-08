"""API: /vergleich – Mehrzeitraum-Vergleich als Pivot-Tabelle."""

from datetime import date, timedelta

from fastapi import APIRouter

from app.config.settings import KURZNAMEN
from app.infrastructure.database import get_db

router = APIRouter(prefix="/api", tags=["labor"])


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
    # Flag-basierte Bewertung
    if vergleich_flag in ("H", "L") and not aktuell_flag:
        return "normalisiert"
    if not vergleich_flag and aktuell_flag in ("H", "L"):
        return "neu_auffällig"

    # Beide auffällig → Richtung prüfen
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

    # Beide normal → Veränderung >10% beachten
    if not aktuell_flag and not vergleich_flag:
        if vergleich_val and vergleich_val != 0:
            pct = abs((aktuell_val - vergleich_val) / vergleich_val * 100)
            if pct < 5:
                return "stabil"
        return "stabil"

    return "stabil"


@router.get("/vergleich")
async def vergleich_pivot():
    """Pivot-Tabelle: Tests × Zeiträume (1–5 Jahre) mit Bewertung."""
    conn = get_db()
    try:
        heute = date.today()

        # Zeiträume definieren: 1, 2, 3, 4, 5 Jahre zurück
        # Pro Zeitraum: Fenster ±6 Monate um den Stichtag
        zeitraeume = []
        for jahre in range(1, 6):
            mitte = heute - timedelta(days=365 * jahre)
            von = (mitte - timedelta(days=182)).isoformat()
            bis = (mitte + timedelta(days=182)).isoformat()
            zeitraeume.append({"jahre": jahre, "von": von, "bis": bis})

        # Alle Tests mit aktuellem Wert (letzter Wert im letzten Jahr)
        vor_12m = (heute - timedelta(days=365)).isoformat()
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
            if aktuell_val is None:
                continue

            entry = {
                "test": test,
                "kurzname": KURZNAMEN.get(test, ""),
                "gruppe": row["gruppe"],
                "aktuell": row["wert_norm"],
                "einheit": row["einheit_norm"] or "",
                "flag": row["flag"] or "",
                "datum": row["datum"],
                "zeitraeume": [],
            }

            hat_aenderung = False
            gesehene_werte = set()  # Duplikate vermeiden

            for zr in zeitraeume:
                # Wert im Zeitfenster (±6 Monate um Stichtag), nächster zur Mitte
                vgl_row = conn.execute("""
                    SELECT wert_norm, flag, datum FROM laborwerte
                    WHERE test_standard = ? AND datum >= ? AND datum <= ?
                    ORDER BY datum DESC LIMIT 1
                """, (test, zr["von"], zr["bis"])).fetchone()

                if not vgl_row:
                    entry["zeitraeume"].append({
                        "jahre": zr["jahre"],
                        "wert": None,
                        "bewertung": None,
                    })
                    continue

                # Duplikat-Check: gleicher Wert+Datum wie schon gezeigt?
                wert_key = f"{vgl_row['wert_norm']}_{vgl_row['datum']}"
                if wert_key in gesehene_werte:
                    entry["zeitraeume"].append({
                        "jahre": zr["jahre"],
                        "wert": None,
                        "bewertung": None,
                    })
                    continue
                gesehene_werte.add(wert_key)

                vgl_val = _parse_float(vgl_row["wert_norm"])
                if vgl_val is None:
                    entry["zeitraeume"].append({
                        "jahre": zr["jahre"],
                        "wert": vgl_row["wert_norm"],
                        "bewertung": None,
                    })
                    continue

                bewertung = _bewertung(
                    row["flag"] or "", vgl_row["flag"] or "", aktuell_val, vgl_val
                )

                if bewertung != "stabil":
                    hat_aenderung = True

                # Prozentuale Veränderung
                pct = round((aktuell_val - vgl_val) / vgl_val * 100) if vgl_val != 0 else 0

                entry["zeitraeume"].append({
                    "jahre": zr["jahre"],
                    "wert": vgl_row["wert_norm"],
                    "flag": vgl_row["flag"] or "",
                    "datum": vgl_row["datum"],
                    "pct": pct,
                    "bewertung": bewertung,
                })

            # Nur Tests mit mindestens einer Veränderung aufnehmen
            if hat_aenderung:
                results.append(entry)

        # Sortierung: verschlechtert zuerst
        def sort_key(item):
            worst = 0
            for zr in item["zeitraeume"]:
                b = zr.get("bewertung", "")
                if b == "neu_auffällig":
                    worst = max(worst, 4)
                elif b == "verschlechtert":
                    worst = max(worst, 3)
                elif b == "normalisiert":
                    worst = max(worst, 1)
                elif b == "verbessert":
                    worst = max(worst, 2)
            return -worst

        results.sort(key=sort_key)

        return {
            "tests": results,
            "anzahl": len(results),
            "zeitraeume_label": [f"vor {z['jahre']} J." for z in zeitraeume],
        }
    finally:
        conn.close()
