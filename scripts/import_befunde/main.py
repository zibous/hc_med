import sys
from pathlib import Path

# Korrekte Imports aus deinen Unterordnern
from config.app_config import config
from service.pipeline import LaborDataPipeline
from writer.import_labor_db import LaborDatabaseAndStatsManager


def main():
    
    export_mode = "--export" in sys.argv
    test_mode = "--test" in sys.argv

    # 💡 KORREKTUR: Konsolen-Text an den gewählten Modus anpassen
    if export_mode:
        print(f"📂 REINER EXPORT-MODUS AKTIV für Patient: '{config.user_id}'")
        print(f"   (Überspringe SQLite-DB, Validierung und Text-Vergleich)\n")
    else:
        print(f"🚀 Starte Labor-Pipeline für Patient: '{config.user_id}'")
        print(f"  📂 Ausgabe-CSV: {config.OUTPUT_FILE.name}")
        print(f"  💾 Ziel-DB:    {config.DB_FILE.name}\n")
    
    if not config.BEFUNDE_DIR.exists():
        print(f"  ⚠️ Import-Verzeichnis existiert nicht: {config.BEFUNDE_DIR}")
        return
        
    txt_files = []
    for ext in ("*.txt", "*.csv", "*.TXT", "*.CSV"):
        txt_files.extend(config.BEFUNDE_DIR.glob(ext))
        
    if not txt_files:
        print(f"  ⚠️ Keine .txt oder .csv Dateien in {config.BEFUNDE_DIR} gefunden.")
        return

    # Stichproben-Warnung, falls kritische Dictionaries leer sind (nur im Normalmodus)
    if not export_mode:
        if not config.INVALID_NORMS:
            print("  ❌ FEHLER: 'INVALID_NORMS' ist leer! filters.yaml wurde nicht eingelesen.")
        if not config.PLAUSIBLE_RANGES:
            print("  ❌ FEHLER: 'PLAUSIBLE_RANGES' ist leer! ranges.yaml wurde nicht eingelesen.")
        if config.INVALID_NORMS and config.PLAUSIBLE_RANGES:
            print("  🎉 Exzellent! Alle Konfigurationsdateien wurden erfolgreich entpackt.")
        print("---------------------------------------\n")

    # 1. Pipeline ausführen (schreibt via app_config automatisch in die produktive laborwerte_gesamt.csv oder laborwerte_gesamt_test.csv)
    pipeline = LaborDataPipeline()
    file_results, all_results = pipeline.process_all_files(txt_files)

    # ─── 💡 DIE FIXE EXPORT-WEICHE (KURZSCHLUSS) ─────────────────────────────
    if export_mode:
        from writer.csv_day_export import export_values_per_day
        export_values_per_day(all_results)
        print(f"\n✨ Export erfolgreich beendet. Schönen Tag noch!")
        return  # Hier bricht das Skript ab! Keine DB, kein Validator, kein Compare.
    # ──────────────────────────────────────────────────────────────────────────

    # 2. Echten SQLite-Import ausführen (schreibt via app_config in labor.db oder labor_test.db)
    db_manager = LaborDatabaseAndStatsManager()
    db_manager.execute_import_and_report(file_results, all_results)
    
    # 3. Körperdaten holen
    if getattr(config, "HAS_SCALE_DB", False):
        print(f"\n⚖️  Starte Waage-Daten-Import aus hc_scale...")
        from writer.import_scale_db import import_scale_data
        import_scale_data(config.user_id)
    else:
        print(f"\n⚖️  Waage-Import übersprungen (HAS_SCALE_DB ist in der Config deaktiviert).")

    # 4. Automatische Datenbank-Validierung am Ende della Pipeline zuschalten!
    from service.validate_labor import validate_database, print_validation_report
    stats, issues = validate_database()
    print_validation_report(stats, issues)
    

    # 5. Der Text-Vergleich wird NUR im Test-Modus ausgeführt!
    if test_mode:
        old_csv_path = config.USER_DIR / "laborwerte_gesamt.csv"
        new_csv_path = config.OUTPUT_FILE

        print("\n  🔍 Text-Vergleich (Präziser Inhalts-Abgleich):")
        if not old_csv_path.exists():
            print(f"    ⚠️ Keine alte Original-Datei zum Vergleichen unter '{old_csv_path.name}' gefunden.")
            return

        old_data = {}
        for line in old_csv_path.read_text(encoding="utf-8").splitlines()[1:]:
            if not line.strip(): continue
            p = line.split(";")
            if len(p) < 11: continue
            key = (p[0].strip(), p[3].strip(), p[4].strip())  # Datum, Test_Standard, Test
            old_data[key] = p

        new_data = {}
        for line in new_csv_path.read_text(encoding="utf-8").splitlines()[1:]:
            if not line.strip(): continue
            p = line.split(";")
            if len(p) < 11: continue
            key = (p[0].strip(), p[3].strip(), p[4].strip())
            new_data[key] = p

        print(f"    Alt: {len(old_data)} Datensätze | Neu: {len(new_data)} Datensätze")
        
        def is_cell_equal(f_old, f_new, col_idx, test_name):
            o_str = f_old.strip()
            n_str = f_new.strip()
            if o_str == n_str: return True
            
            try:
                o_clean = o_str.replace("<", "").replace(">", "").strip()
                n_clean = n_str.replace("<", "").replace(">", "").strip()
                if float(o_clean) == float(n_clean):                        
                    return ("<" in o_str) == ("<" in n_str) and (">" in o_str) == (">" in n_str)
            except ValueError: pass
                        
            if "-" in o_str and "-" in n_str:
                try:
                    o_parts = o_str.split("-")
                    n_parts = n_str.split("-")
                    if len(o_parts) == 2 and len(n_parts) == 2:
                        return float(o_parts[0].strip()) == float(n_parts[0].strip()) and float(o_parts[1].strip()) == float(n_parts[1].strip())
                except ValueError: pass
            
            if col_idx == 2:  # Spalte Gruppe Richtigstellung
                if "GGT" in str(test_name) and o_str == "Sonstige" and n_str == "Leber": return True

            if col_idx == 9:  # Spalte Normbereich Leitlinien-Anpassung
                if "LDL" in str(test_name) and o_str.replace(" ", "") == "<150" and n_str.replace(" ", "") == "<130": return True                    
                if "Non-HDL" in str(test_name) and o_str.replace(" ", "") == "<160" and n_str == "": return True
            return False

        diff_count = 0
        field_names = ["Datum", "Alter", "Gruppe", "Test_Standard", "Test", "Wert_Norm", "Einheit_Norm", "Wert", "Einheit", "Normbereich", "Flag"]
        
        for key, p_old in old_data.items():
            if key in new_data:
                p_new = new_data[key]
                for i in range(11):                        
                    if not is_cell_equal(p_old[i], p_new[i], i, key[1]):
                        diff_count += 1
                        if diff_count <= 10:
                            print(f"\n    ❌ Inhaltliche Abweichung in Spalte '{field_names[i]}' bei Test '{key}' am {key[0]}:")
                            print(f"      [ALT] ➔ {';'.join(p_old)}")
                            print(f"      [NEU] ➔ {';'.join(p_new)}")
                        break

        missing_in_new = [";".join(old) for key, old in old_data.items() if key not in new_data]
        if missing_in_new:
            print(f"\n    ⚠️  {len(missing_in_new)} Zeilen aus der alten CSV fehlen im neuen System komplett:")
            for m in missing_in_new[:5]: print(f"      - {m}")

        added_in_new = [";".join(new) for key, new in new_data.items() if key not in old_data]
        if added_in_new:
            print(f"\n    ✨ {len(added_in_new)} Zeilen sind im neuen System komplett NEU dazugekommen:")
            for a in added_in_new[:5]: print(f"      + {a}")

        if diff_count == 0 and not missing_in_new and not added_in_new:
            print("    ✅ Perfekt! Alle Datenstrukturen und Inhalte sind zu 100% deckungsgleich.")
        else:
            print(f"\n    ➔ Analyse beendet: {diff_count} Abweichungen im Text-Inhalt gefunden.")

    print(f"\n✅ Pipeline-Lauf erfolgreich beendet. (Ergebnis gespeichert)")

if __name__ == "__main__":
    main()
