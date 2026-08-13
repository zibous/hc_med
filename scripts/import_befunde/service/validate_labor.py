import sqlite3
from pathlib import Path

# Zentrale Konfiguration laden
from config.app_config import config

def validate_database() -> tuple[dict, list]:
    """Prüft alle Werte in der aktiven DB auf Plausibilität anhand der Config-Ranges."""
    db_path = config.DB_FILE
    
    if not db_path.exists():
        print(f"  ⚠️  [Validator] labor.db nicht vorhanden unter: {db_path}")
        return {"total": 0, "ok": 0, "outside_range": 0, "not_numeric": 0, "no_range_defined": 0}, []

    # 💡 FIX: Nutzt die zentral in app_config geladenen Ranges (aus der YAML)
    plausible_ranges = getattr(config, "PLAUSIBLE_RANGES", {})

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

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

        # Nicht-numerische Werte abfangen
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

        # Range-Definition in der YAML vorhanden?
        if test not in plausible_ranges:
            stats["no_range_defined"] += 1
            stats["ok"] += 1
            continue

        # Range auswerten (erwartet ein zweielementiges Array/Tuple [min, max] aus der YAML)
        range_v = plausible_ranges[test]
        if not isinstance(range_v, (list, tuple)) or len(range_v) != 2:
            stats["no_range_defined"] += 1
            stats["ok"] += 1
            continue

        min_val, max_val = float(range_v[0]), float(range_v[1])

        if val < min_val or val > max_val:
            stats["outside_range"] += 1
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

def print_validation_report(stats: dict, issues: list) -> None:
    """Gibt den strukturierten Validierungsbericht auf dem Terminal aus."""
    print("\n📊 Validierungsbericht (Plausibilitäts-Check)")
    print("=" * 110)
    print(f"  Gesamt-Werte:        {stats['total']}")
    print(f"  ✅ Plausibel:         {stats['ok']}")
    print(f"  ❌ Außerhalb Range:   {stats['outside_range']}")
    print(f"  ⚠️  Nicht numerisch:  {stats['not_numeric']}")
    print(f"  ℹ️  Ohne Range-Def.:  {stats['no_range_defined']}")
    print()

    if not issues:
        print("  🎉 Keine Plausibilitätsfehler in der Datenbank gefunden!")
        return

    range_issues = [i for i in issues if i["typ"] == "AUSSERHALB_RANGE"]
    non_numeric = [i for i in issues if i["typ"] == "NICHT_NUMERISCH"]

    if range_issues:
        print(f"  ❌ Werte außerhalb plausible Range ({len(range_issues)}):")
        print(f"  {'Datum':<12} {'Test':<22} {'Wert':>8} {'Einheit':<8} {'Range':<14} {'Abweichung':<25} {'Original'}")
        print("  " + "-" * 118)
        for i in range_issues:
            print(f"  {i['datum']:<12} {i['test']:<22} {i['wert']:>8.2f} {i['einheit'] or '':<8} {i['range']:<14} {i['abweichung']:<25} {i['original']}")

    if non_numeric:
        print(f"\n  ⚠️  Nicht-numerische Werte ({len(non_numeric)}):")
        print(f"  {'Datum':<12} {'Test':<22} {'Wert':<15} {'Original'}")
        print("  " + "-" * 70)
        for i in non_numeric:
            print(f"  {i['datum']:<12} {i['test']:<22} {i['wert']:<15} {i['original']}")
