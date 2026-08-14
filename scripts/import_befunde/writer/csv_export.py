import csv
import logging
from pathlib import Path
from config.app_config import config

log = logging.getLogger("labor_pipeline")


class LaborCSVExporter:
    """Verantwortlich für das Sortieren und Exportieren von Laborergebnissen."""

    def __init__(self):
        self.fieldnames = [
            "Datum", "Alter", "Gruppe", "Test_Standard", "Test",
            "Wert_Norm", "Einheit_Norm", "Wert", "Einheit", "Normbereich", "Flag",
        ]

    def export(self, all_results: list[dict]) -> None:
        if not all_results:
            log.warning("Keine Ergebnisse zum Exportieren vorhanden.")
            return

        # Sortierung auf die chronologische Reihenfolge
        all_results.sort(key=lambda x: (x.get("Datum", ""), x.get("Gruppe", ""), x.get("Test_Standard", "")))

        try:
            with open(config.OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.fieldnames, delimiter=";", extrasaction="ignore")
                writer.writeheader()
                writer.writerows(all_results)

            log.info(f"  💾 {len(all_results)} Werte erfolgreich nach '{config.OUTPUT_FILE.name}' exportiert.")

        except (IOError, OSError) as e:
            log.error(f"  Fehler beim Schreiben der CSV-Datei: {e}")
