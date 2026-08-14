"""
Labor-Pipeline – Haupteinstiegspunkt.

Nutzung:
    python main.py <user>              → Vollständiger Produktiv-Lauf
    python main.py <user> --test       → Schreibt in _test-Dateien, vergleicht mit Referenz
    python main.py <user> --quiet      → Nur Warnungen/Fehler
    python main.py <user> --debug      → Ausführliches Logging

Flow:
    1. Befunde parsen (data/{user}/import/)
    2. laborwerte_gesamt.csv schreiben
    3. Tages-CSVs exportieren (data/{user}/export/)
    4. Plausibilitäts-Validierung
    5. Nur wenn Validierung OK → SQLite-DB schreiben
    6. Körperdaten aus hc_scale importieren (falls konfiguriert)
    7. [--test] Vergleich mit Referenz-CSV
"""

import logging
import sys

from config.app_config import config
from service.pipeline import LaborDataPipeline

log = logging.getLogger("labor_pipeline")


def main():
    test_mode = config.test_mode

    log.info(f"🚀 Starte Labor-Pipeline für Patient: '{config.user_id}'")
    log.info(f"  📂 Ausgabe-CSV: {config.OUTPUT_FILE.name}")
    log.info(f"  💾 Ziel-DB:    {config.DB_FILE.name}\n")

    # ─── Voraussetzungen prüfen ───────────────────────────────────────────────
    if not config.BEFUNDE_DIR.exists():
        log.error(f"  Import-Verzeichnis existiert nicht: {config.BEFUNDE_DIR}")
        sys.exit(1)

    txt_files = []
    for ext in ("*.txt", "*.csv", "*.TXT", "*.CSV"):
        txt_files.extend(config.BEFUNDE_DIR.glob(ext))

    if not txt_files:
        log.error(f"  Keine .txt oder .csv Dateien in {config.BEFUNDE_DIR} gefunden.")
        sys.exit(1)

    if not config.INVALID_NORMS:
        log.error("  'INVALID_NORMS' ist leer! filters.yaml wurde nicht eingelesen.")
        sys.exit(1)
    if not config.PLAUSIBLE_RANGES:
        log.error("  'PLAUSIBLE_RANGES' ist leer! ranges.yaml wurde nicht eingelesen.")
        sys.exit(1)

    log.info("  ✓ Alle Konfigurationsdateien geladen.")
    log.info("---------------------------------------\n")

    # ─── 1. Pipeline: Parsen + Normalisieren + CSV schreiben ──────────────────
    pipeline = LaborDataPipeline()
    file_results, all_results = pipeline.process_all_files(txt_files)

    # ─── 2. Tages-Export (immer) ──────────────────────────────────────────────
    from writer.csv_day_export import export_values_per_day
    export_values_per_day(all_results)

    # ─── 3. Plausibilitäts-Validierung ────────────────────────────────────────
    #    Hier validieren wir die CSV-Daten im Speicher (vor DB-Import).
    #    Die DB-Validierung kommt nach dem Import.
    validation_ok = _validate_results(all_results)

    # ─── 4. SQLite-DB nur wenn Validierung OK ─────────────────────────────────
    if not validation_ok:
        log.error("\n  ❌ Validierung fehlgeschlagen – SQLite-Import übersprungen!")
        log.error("     CSV wurde geschrieben, DB bleibt unverändert.")
    else:
        from writer.import_labor_db import LaborDatabaseAndStatsManager
        db_manager = LaborDatabaseAndStatsManager()
        db_manager.execute_import_and_report(file_results, all_results)

        # ─── 5. Körperdaten aus hc_scale ──────────────────────────────────────
        if getattr(config, "HAS_SCALE_DB", False):
            log.info(f"\n⚖️  Starte Waage-Daten-Import aus hc_scale...")
            from writer.import_scale_db import import_scale_data
            import_scale_data(config.user_id)
        else:
            log.debug("  Waage-Import übersprungen (kein scaledb konfiguriert).")

        # ─── 6. DB-Validierung (nach Import) ──────────────────────────────────
        from service.validate_labor import validate_database, print_validation_report
        stats, issues = validate_database()
        print_validation_report(stats, issues)

    # ─── 7. Text-Vergleich (nur --test) ───────────────────────────────────────
    if test_mode:
        _run_text_comparison()

    log.info(f"\n✅ Pipeline-Lauf erfolgreich beendet.")


def _validate_results(all_results: list[dict]) -> bool:
    """Prüft die Ergebnisse auf Plausibilität (vor DB-Import)."""
    plausible_ranges = config.PLAUSIBLE_RANGES
    issues = 0

    for row in all_results:
        test = row.get("Test_Standard", "")
        if test not in plausible_ranges:
            continue

        range_v = plausible_ranges[test]
        if not isinstance(range_v, (list, tuple)) or len(range_v) != 2:
            continue

        wert_str = str(row.get("Wert_Norm", "")).replace("<", "").replace(">", "").strip()
        try:
            val = float(wert_str)
        except (ValueError, TypeError):
            continue

        min_val, max_val = float(range_v[0]), float(range_v[1])
        if val < min_val or val > max_val:
            issues += 1
            if issues <= 5:
                log.warning(f"  ⚠️  Plausibilität: {test} = {val} (Range: {min_val}–{max_val}) am {row.get('Datum', '?')}")

    if issues > 0:
        log.error(f"\n  ❌ {issues} Werte außerhalb der Plausibilitätsgrenzen!")
        return False

    log.info("  ✓ Plausibilitäts-Check bestanden (0 Fehler).")
    return True


def _run_text_comparison():
    """Vergleicht alte und neue CSV im Test-Modus."""
    old_csv_path = config.USER_DIR / "laborwerte_gesamt.csv"
    new_csv_path = config.OUTPUT_FILE

    log.info("\n  🔍 Text-Vergleich (Präziser Inhalts-Abgleich):")
    if not old_csv_path.exists():
        log.warning(f"    ⚠️ Keine Referenz-Datei zum Vergleichen unter '{old_csv_path.name}' gefunden.")
        return

    old_data = {}
    for line in old_csv_path.read_text(encoding="utf-8").splitlines()[1:]:
        if not line.strip():
            continue
        p = line.split(";")
        if len(p) < 11:
            continue
        key = (p[0].strip(), p[3].strip(), p[4].strip())
        old_data[key] = p

    new_data = {}
    for line in new_csv_path.read_text(encoding="utf-8").splitlines()[1:]:
        if not line.strip():
            continue
        p = line.split(";")
        if len(p) < 11:
            continue
        key = (p[0].strip(), p[3].strip(), p[4].strip())
        new_data[key] = p

    log.info(f"    Alt: {len(old_data)} Datensätze | Neu: {len(new_data)} Datensätze")

    diff_count = 0
    field_names = ["Datum", "Alter", "Gruppe", "Test_Standard", "Test",
                   "Wert_Norm", "Einheit_Norm", "Wert", "Einheit", "Normbereich", "Flag"]

    for key, p_old in old_data.items():
        if key in new_data:
            p_new = new_data[key]
            for i in range(11):
                if not _is_cell_equal(p_old[i], p_new[i], i, key[1]):
                    diff_count += 1
                    if diff_count <= 10:
                        log.info(f"\n    ❌ Abweichung '{field_names[i]}' bei '{key[1]}' am {key[0]}:")
                        log.info(f"      [ALT] ➔ {';'.join(p_old)}")
                        log.info(f"      [NEU] ➔ {';'.join(p_new)}")
                    break

    missing_in_new = [k for k in old_data if k not in new_data]
    if missing_in_new:
        log.warning(f"\n    ⚠️  {len(missing_in_new)} Zeilen fehlen im neuen Ergebnis.")

    added_in_new = [k for k in new_data if k not in old_data]
    if added_in_new:
        log.info(f"\n    ✨ {len(added_in_new)} neue Zeilen hinzugekommen.")

    if diff_count == 0 and not missing_in_new and not added_in_new:
        log.info("    ✅ 100% deckungsgleich mit Referenz.")
    else:
        log.info(f"\n    ➔ {diff_count} Abweichungen gefunden.")


def _is_cell_equal(f_old: str, f_new: str, col_idx: int, test_name: str) -> bool:
    """Vergleicht zwei Zellen mit Toleranz für numerische Gleichheit."""
    o_str = f_old.strip()
    n_str = f_new.strip()
    if o_str == n_str:
        return True

    # Numerischer Vergleich (Dezimalstellen-Toleranz)
    try:
        o_clean = o_str.replace("<", "").replace(">", "").strip()
        n_clean = n_str.replace("<", "").replace(">", "").strip()
        if float(o_clean) == float(n_clean):
            return ("<" in o_str) == ("<" in n_str) and (">" in o_str) == (">" in n_str)
    except ValueError:
        pass

    # Range-Vergleich (z.B. "4.0-6.0" vs "4.0 - 6.0")
    if "-" in o_str and "-" in n_str:
        try:
            o_parts = o_str.split("-")
            n_parts = n_str.split("-")
            if len(o_parts) == 2 and len(n_parts) == 2:
                return (float(o_parts[0].strip()) == float(n_parts[0].strip())
                        and float(o_parts[1].strip()) == float(n_parts[1].strip()))
        except ValueError:
            pass

    return False


if __name__ == "__main__":
    main()
