import logging

from config.app_config import config

log = logging.getLogger("labor_pipeline")


class LaborDatabaseAndStatsManager:
    """Kapselt den gesamten SQLite-Import sowie die terminale Statistik-Ausgabe am Ende der Pipeline."""

    def execute_import_and_report(self, file_results: list, all_results: list) -> None:
        """Führt den SQLite-Import durch und gibt die vollständige Statistik aus."""
        from writer.labor_db import LaborDB

        patient_data = getattr(config, "_patient", {})

        # ─── SQLite Import ──────────────────────────────────────────────────────────
        with LaborDB(db_path=config.DB_FILE) as db:
            patient_id = db.get_or_create_patient(
                vorname=patient_data.get("vorname", ""),
                nachname=patient_data.get("nachname", ""),
                geburtsdatum=config.PATIENT_GEBURTSDATUM,
                geschlecht=config.PATIENT_GESCHLECHT,
            )

            db_total = 0
            for filename, fmt, results, nuechtern_flag in file_results:
                if fmt == "tab":
                    labor = "Dr. Zünd, Lustenau"
                elif "laborbefund" in filename.lower():
                    labor = "Krankenhaus"
                else:
                    labor = ""

                count = db.import_results(
                    results,
                    quelldatei=filename,
                    patient_id=patient_id,
                    format=fmt,
                    labor=labor,
                    nuechtern=nuechtern_flag
                )
                db_total += count

            # Berechnete Werte (Non-HDL etc.) separat importieren
            berechnete = [r for r in all_results if "(berechnet)" in r.get("Test", "")]
            if berechnete:
                count = db.import_results(
                    berechnete,
                    quelldatei="berechnet",
                    patient_id=patient_id,
                    format="berechnet",
                    labor="berechnet"
                )
                db_total += count

            stats = db.stats()
            log.info(f"\n  SQLite: {stats['laborwerte']} Werte in {db.db_path.name}")
            log.info(f"    Zeitraum: {stats['zeitraum']['von']} bis {stats['zeitraum']['bis']}")
            log.info(f"    Befunde: {stats['befunde']}, Patienten: {stats['patienten']}")

        # ─── Statistik ──────────────────────────────────────────────────────────────
        groups = {}
        for row in all_results:
            groups[row["Gruppe"]] = groups.get(row["Gruppe"], 0) + 1
        log.info("\n  Gruppen-Verteilung:")
        for group, count in sorted(groups.items()):
            log.info(f"    {group}: {count}")

        # Warnung: Tests die in "Sonstige" gelandet sind
        sonstige_tests = sorted(set(
            r["Test_Standard"] for r in all_results if r["Gruppe"] == "Sonstige"
        ))
        if sonstige_tests:
            log.warning(f"\n  ⚠️  Ohne Gruppen-Zuordnung → 'Sonstige' ({len(sonstige_tests)} Tests):")
            for t in sonstige_tests:
                log.warning(f"    - {t}")
            log.info("    → GROUPS_YAML_PATH (groups.yaml) ergänzen um zuzuordnen")

        normalized = sum(1 for r in all_results if r["Test_Standard"] != r["Test"])
        converted = sum(1 for r in all_results if r["Wert_Norm"] != r["Wert"])
        log.info(f"\n  Normalisiert: {normalized} Testnamen, {converted} Einheiten-Konversionen")
        log.info(f"\n✓ {len(all_results)} Laborwerte in {config.OUTPUT_FILE.name} geschrieben")
        log.info(f"✓ SQLite-Datenbank: {config.DB_FILE.name}")
