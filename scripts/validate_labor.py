"""Validierung der Laborwerte in der Datenbank.

Prüft ob Werte plausibel sind:
- Innerhalb einer medizinisch sinnvollen Range
- Keine Ausreißer durch Parser-Fehler
- Einheiten-Konsistenz pro Test
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "labor.db"

# Plausibilitäts-Ranges pro Test (min, max in der normalisierten Einheit)
# Werte weit außerhalb sind Parser-Fehler oder Einheiten-Probleme
PLAUSIBLE_RANGES: dict[str, tuple[float, float]] = {
    # Blutbild
    "Leukozyten": (1.0, 50.0),          # 10^9/L
    "Erythrozyten": (2.0, 8.0),          # 10^12/L oder 10^6/µl
    "Hämoglobin": (5.0, 20.0),           # g/dL
    "Hämatokrit": (20.0, 60.0),          # %
    "MCV": (60.0, 110.0),                # fL
    "MCH": (20.0, 40.0),                 # pg
    "MCHC": (28.0, 40.0),               # g/dL
    "RDW": (10.0, 20.0),                 # %
    "Thrombozyten": (20.0, 600.0),       # 10^9/L
    "MPV": (6.0, 15.0),                  # fL
    # Entzündung
    "CRP": (0.0, 50.0),                  # mg/dL
    "Interleukin-6": (0.0, 500.0),       # pg/mL
    "Procalcitonin": (0.0, 10.0),        # ng/mL
    "BSG 1h": (0.0, 120.0),             # mm
    # Leber
    "GOT": (0.0, 500.0),                 # U/L
    "GPT": (0.0, 500.0),                 # U/L
    "GGT": (0.0, 500.0),                 # U/L
    "Alk. Phosphatase": (20.0, 500.0),   # U/L
    "Bilirubin": (0.0, 20.0),            # mg/dL
    "LDH": (50.0, 500.0),               # U/L
    "Cholinesterase": (3000.0, 15000.0), # U/L
    # Niere
    "Kreatinin": (0.3, 5.0),             # mg/dL
    "GFR": (10.0, 150.0),               # mL/min
    "Harnstoff": (5.0, 150.0),           # mg/dL
    "Harnsäure": (1.0, 15.0),            # mg/dL
    # Elektrolyte
    "Natrium": (120.0, 160.0),           # mmol/L
    "Kalium": (2.5, 7.0),               # mmol/L
    "Chlorid": (80.0, 120.0),            # mmol/L
    "Calcium": (1.5, 3.5),              # mmol/L
    "Magnesium": (0.3, 2.0),            # mmol/L
    "Phosphat": (0.5, 3.0),             # mmol/L
    # Stoffwechsel
    "Glucose": (30.0, 400.0),            # mg/dL
    "HbA1c": (3.0, 15.0),               # %
    "HbA1c (IFCC)": (15.0, 120.0),      # mmol/mol
    "Totalprotein": (3.0, 10.0),         # g/dL
    # Lipide
    "Cholesterin": (80.0, 400.0),        # mg/dL
    "HDL": (20.0, 120.0),               # mg/dL
    "LDL": (30.0, 300.0),               # mg/dL
    "Triglyceride": (30.0, 600.0),       # mg/dL
    "Quotient Chol/HDL": (1.0, 10.0),
    "Quotient LDL/HDL": (0.5, 8.0),
    # Pankreas
    "Amylase": (5.0, 300.0),             # U/L
    "Pankreas-Amylase": (5.0, 200.0),   # U/L
    "Lipase": (5.0, 300.0),             # U/L
    # Gerinnung
    "Quick": (20.0, 150.0),              # %
    "INR": (0.5, 5.0),
    "aPTT": (15.0, 80.0),               # Sek
    # Schilddrüse
    "TSH": (0.01, 20.0),                # mIU/L
    # Tumor-Marker
    "PSA": (0.0, 50.0),                 # ng/mL
    # Körperdaten
    "Gewicht": (40.0, 150.0),            # kg
    "BMI": (15.0, 45.0),
    "Fettgehalt": (3.0, 40.0),           # %
    "Muskelmasse": (20.0, 60.0),         # kg oder %
}


def validate():
    """Prüft alle Werte in der DB auf Plausibilität."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    # Alle Werte holen
    rows = conn.execute("""
        SELECT id, datum, test_standard, wert_norm, einheit_norm, wert_original, einheit_original
        FROM laborwerte
        ORDER BY test_standard, datum
    """).fetchall()

    issues = []
    stats = {"total": len(rows), "ok": 0, "outside_range": 0, "not_numeric": 0, "no_range_defined": 0}

    for r in rows:
        test = r["test_standard"]
        wert_str = str(r["wert_norm"]).replace("<", "").replace(">", "").strip()

        # Nicht-numerisch?
        try:
            val = float(wert_str)
        except (ValueError, TypeError):
            stats["not_numeric"] += 1
            issues.append({
                "typ": "NICHT_NUMERISCH",
                "id": r["id"],
                "datum": r["datum"],
                "test": test,
                "wert": r["wert_norm"],
                "einheit": r["einheit_norm"],
                "original": f"{r['wert_original']} {r['einheit_original']}",
            })
            continue

        # Range definiert?
        if test not in PLAUSIBLE_RANGES:
            stats["no_range_defined"] += 1
            stats["ok"] += 1
            continue

        min_val, max_val = PLAUSIBLE_RANGES[test]

        if val < min_val or val > max_val:
            stats["outside_range"] += 1
            # Wie weit außerhalb?
            if val < min_val:
                deviation = f"{((min_val - val) / min_val * 100):.0f}% unter Minimum"
            else:
                deviation = f"{((val - max_val) / max_val * 100):.0f}% über Maximum"

            issues.append({
                "typ": "AUSSERHALB_RANGE",
                "id": r["id"],
                "datum": r["datum"],
                "test": test,
                "wert": val,
                "einheit": r["einheit_norm"],
                "range": f"{min_val}–{max_val}",
                "abweichung": deviation,
                "original": f"{r['wert_original']} {r['einheit_original']}",
            })
        else:
            stats["ok"] += 1

    conn.close()
    return stats, issues


def print_report(stats, issues):
    """Gibt den Validierungsbericht aus."""
    print("\n📊 Validierungsbericht")
    print("=" * 70)
    print(f"  Gesamt:              {stats['total']}")
    print(f"  ✅ Plausibel:         {stats['ok']}")
    print(f"  ❌ Außerhalb Range:   {stats['outside_range']}")
    print(f"  ⚠️  Nicht numerisch:  {stats['not_numeric']}")
    print(f"  ℹ️  Ohne Range-Def.:  {stats['no_range_defined']}")
    print()

    if not issues:
        print("  🎉 Keine Probleme gefunden!")
        return

    # Nach Typ gruppieren
    range_issues = [i for i in issues if i["typ"] == "AUSSERHALB_RANGE"]
    non_numeric = [i for i in issues if i["typ"] == "NICHT_NUMERISCH"]

    if range_issues:
        print(f"  ❌ Werte außerhalb plausible Range ({len(range_issues)}):")
        print(f"  {'Datum':<12} {'Test':<22} {'Wert':>8} {'Einheit':<8} {'Range':<14} {'Abweichung':<25} {'Original'}")
        print("  " + "-" * 110)
        for i in range_issues:
            print(f"  {i['datum']:<12} {i['test']:<22} {i['wert']:>8.2f} {i['einheit'] or '':<8} {i['range']:<14} {i['abweichung']:<25} {i['original']}")

    if non_numeric:
        print(f"\n  ⚠️  Nicht-numerische Werte ({len(non_numeric)}):")
        print(f"  {'Datum':<12} {'Test':<22} {'Wert':<15} {'Original'}")
        print("  " + "-" * 70)
        for i in non_numeric:
            print(f"  {i['datum']:<12} {i['test']:<22} {i['wert']:<15} {i['original']}")


if __name__ == "__main__":
    stats, issues = validate()
    print_report(stats, issues)
