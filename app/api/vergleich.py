"""API: /vergleich – Vorjahresvergleich der Laborwerte."""

from fastapi import APIRouter

from app.infrastructure.database import get_db

router = APIRouter(prefix="/api", tags=["labor"])


@router.get("/vergleich")
async def vergleich():
    """Vergleicht aktuelle Werte mit Vorjahr – zeigt Verbesserungen/Verschlechterungen."""
    conn = get_db()
    try:
        # Alle Tests mit mindestens 2 Messungen in verschiedenen Jahren
        rows = conn.execute("""
            SELECT test_standard, datum, wert_norm, einheit_norm, normbereich, flag, gruppe
            FROM laborwerte
            WHERE test_standard IN (
                SELECT test_standard FROM laborwerte
                GROUP BY test_standard
                HAVING COUNT(DISTINCT substr(datum,1,4)) >= 2
            )
            ORDER BY test_standard, datum
        """).fetchall()

        if not rows:
            return {"verbessert": [], "verschlechtert": [], "stabil": []}

        # Pro Test: letzter Wert vs. vorheriger Wert (mind. 6 Monate Abstand)
        tests = {}
        for r in rows:
            t = r["test_standard"]
            if t not in tests:
                tests[t] = []
            tests[t].append(r)

        verbessert = []
        verschlechtert = []
        stabil = []

        for test, messungen in tests.items():
            if len(messungen) < 2:
                continue

            aktuell = messungen[-1]
            # Vorherigen Wert finden (mind. 180 Tage Abstand)
            vorher = None
            for m in reversed(messungen[:-1]):
                if aktuell["datum"] > m["datum"]:
                    # Mindestens 6 Monate Abstand
                    from datetime import datetime
                    d_akt = datetime.strptime(aktuell["datum"], "%Y-%m-%d")
                    d_vor = datetime.strptime(m["datum"], "%Y-%m-%d")
                    if (d_akt - d_vor).days >= 180:
                        vorher = m
                        break

            if not vorher:
                continue

            # Werte parsen
            try:
                val_akt = float(str(aktuell["wert_norm"]).replace(",", ".").replace("<", "").replace(">", ""))
                val_vor = float(str(vorher["wert_norm"]).replace(",", ".").replace("<", "").replace(">", ""))
            except (ValueError, TypeError):
                continue

            if val_vor == 0:
                continue

            pct = ((val_akt - val_vor) / val_vor) * 100
            einheit = aktuell["einheit_norm"] or ""
            norm = aktuell["normbereich"] or ""

            # Bestimmen ob Veränderung gut oder schlecht ist
            flag_akt = aktuell["flag"]
            flag_vor = vorher["flag"]

            entry = {
                "test": test,
                "gruppe": aktuell["gruppe"],
                "aktuell": f"{val_akt:.1f}",
                "vorher": f"{val_vor:.1f}",
                "einheit": einheit,
                "datum_aktuell": aktuell["datum"],
                "datum_vorher": vorher["datum"],
                "veraenderung_pct": round(pct, 1),
                "norm": norm,
            }

            # War vorher auffällig und jetzt nicht mehr → verbessert
            if flag_vor in ("H", "L") and not flag_akt:
                entry["bewertung"] = "Normalisiert ✅"
                verbessert.append(entry)
            # War normal und jetzt auffällig → verschlechtert
            elif not flag_vor and flag_akt in ("H", "L"):
                entry["bewertung"] = "Neu auffällig ⚠️"
                verschlechtert.append(entry)
            # War auffällig und bleibt auffällig, aber Wert nähert sich Norm
            elif flag_vor and flag_akt:
                # Prüfe ob Richtung stimmt (näher an Norm = besser)
                if flag_akt == "H" and val_akt < val_vor:
                    entry["bewertung"] = "Besser (noch erhöht)"
                    verbessert.append(entry)
                elif flag_akt == "L" and val_akt > val_vor:
                    entry["bewertung"] = "Besser (noch erniedrigt)"
                    verbessert.append(entry)
                elif flag_akt == "H" and val_akt > val_vor:
                    entry["bewertung"] = "Weiter verschlechtert ↑"
                    verschlechtert.append(entry)
                elif flag_akt == "L" and val_akt < val_vor:
                    entry["bewertung"] = "Weiter verschlechtert ↓"
                    verschlechtert.append(entry)
                else:
                    entry["bewertung"] = "Unverändert auffällig"
                    stabil.append(entry)
            else:
                # Beide normal, >5% Veränderung trotzdem melden
                if abs(pct) > 10:
                    entry["bewertung"] = f"{'↑' if pct > 0 else '↓'} {abs(pct):.0f}% (im Normbereich)"
                    stabil.append(entry)

        # Sortieren: größte Veränderung zuerst
        verbessert.sort(key=lambda x: abs(x["veraenderung_pct"]), reverse=True)
        verschlechtert.sort(key=lambda x: abs(x["veraenderung_pct"]), reverse=True)

        return {
            "verbessert": verbessert,
            "verschlechtert": verschlechtert,
            "stabil": stabil[:5],  # Nur die top 5 mit großer Veränderung
        }
    finally:
        conn.close()
