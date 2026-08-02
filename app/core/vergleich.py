"""Vorjahresvergleich – welche Tests haben sich verbessert/verschlechtert."""

import sqlite3
from datetime import date, timedelta


def berechne_vorjahresvergleich(conn: sqlite3.Connection) -> dict:
    """Vergleicht die letzten Werte mit denen vor ~12 Monaten.

    Returns: {
        "verbessert": [{"test": ..., "aktuell": ..., "vorjahr": ..., "einheit": ..., "richtung": "besser"}],
        "verschlechtert": [...],
        "stabil": [...],
    }
    """
    # Tests mit mindestens 2 Messungen im letzten Jahr + davor
    heute = date.today()
    vor_12m = (heute - timedelta(days=365)).isoformat()

    # Letzter Wert pro Test (aktuell)
    aktuelle = conn.execute("""
        SELECT test_standard, wert_norm, einheit_norm, normbereich, flag, datum
        FROM laborwerte l1
        WHERE datum = (SELECT MAX(datum) FROM laborwerte l2 WHERE l2.test_standard = l1.test_standard)
        AND datum >= ?
        GROUP BY test_standard
    """, (vor_12m,)).fetchall()

    verbessert = []
    verschlechtert = []
    stabil = []

    for row in aktuelle:
        test = row["test_standard"]
        aktuell_str = row["wert_norm"]
        einheit = row["einheit_norm"] or ""
        flag_aktuell = row["flag"]
        norm = row["normbereich"] or ""

        # Wert vor 12+ Monaten
        vorjahr_row = conn.execute("""
            SELECT wert_norm, flag, datum FROM laborwerte
            WHERE test_standard = ? AND datum < ?
            ORDER BY datum DESC LIMIT 1
        """, (test, vor_12m)).fetchone()

        if not vorjahr_row:
            continue  # Kein Vorjahreswert vorhanden

        # Numerische Werte parsen
        try:
            aktuell_val = float(str(aktuell_str).replace(",", ".").replace("<", "").replace(">", ""))
            vorjahr_val = float(str(vorjahr_row["wert_norm"]).replace(",", ".").replace("<", "").replace(">", ""))
        except (ValueError, TypeError):
            continue

        if aktuell_val == vorjahr_val:
            continue

        # Richtung bestimmen: hängt vom Normbereich ab
        # Bei den meisten Tests: näher an Norm = besser
        pct_change = ((aktuell_val - vorjahr_val) / vorjahr_val * 100) if vorjahr_val != 0 else 0

        # Nur signifikante Änderungen (>5%)
        if abs(pct_change) < 5:
            stabil.append(test)
            continue

        # Bewertung: Hat sich der Flag-Status verbessert?
        flag_vorjahr = vorjahr_row["flag"]
        if flag_vorjahr in ("H", "L") and not flag_aktuell:
            # War auffällig, jetzt normal → verbessert
            verbessert.append({
                "test": test, "aktuell": aktuell_str, "vorjahr": vorjahr_row["wert_norm"],
                "einheit": einheit, "pct": round(pct_change), "flag_vorjahr": flag_vorjahr,
            })
        elif not flag_vorjahr and flag_aktuell in ("H", "L"):
            # War normal, jetzt auffällig → verschlechtert
            verschlechtert.append({
                "test": test, "aktuell": aktuell_str, "vorjahr": vorjahr_row["wert_norm"],
                "einheit": einheit, "pct": round(pct_change), "flag_aktuell": flag_aktuell,
            })
        elif flag_vorjahr in ("H", "L") and flag_aktuell in ("H", "L"):
            # Beide auffällig – Richtung prüfen
            # Wenn Flag "H": niedriger = besser, wenn "L": höher = besser
            if flag_aktuell == "H":
                if aktuell_val < vorjahr_val:
                    verbessert.append({
                        "test": test, "aktuell": aktuell_str, "vorjahr": vorjahr_row["wert_norm"],
                        "einheit": einheit, "pct": round(pct_change),
                    })
                else:
                    verschlechtert.append({
                        "test": test, "aktuell": aktuell_str, "vorjahr": vorjahr_row["wert_norm"],
                        "einheit": einheit, "pct": round(pct_change),
                    })
            elif flag_aktuell == "L":
                if aktuell_val > vorjahr_val:
                    verbessert.append({
                        "test": test, "aktuell": aktuell_str, "vorjahr": vorjahr_row["wert_norm"],
                        "einheit": einheit, "pct": round(pct_change),
                    })
                else:
                    verschlechtert.append({
                        "test": test, "aktuell": aktuell_str, "vorjahr": vorjahr_row["wert_norm"],
                        "einheit": einheit, "pct": round(pct_change),
                    })

    return {
        "verbessert": sorted(verbessert, key=lambda x: abs(x["pct"]), reverse=True),
        "verschlechtert": sorted(verschlechtert, key=lambda x: abs(x["pct"]), reverse=True),
        "stabil_count": len(stabil),
    }
