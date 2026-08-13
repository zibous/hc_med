import csv
from pathlib import Path
from config.app_config import config

class LaborCSVExporter:
    """Verantwortlich für das Sortieren und Exportieren von Laborergebnissen."""

    def __init__(self):
        self.fieldnames = [
            "Datum", "Alter", "Gruppe", "Test_Standard", "Test",
            "Wert_Norm", "Einheit_Norm", "Wert", "Einheit", "Normbereich", "Flag",
        ]

    def export(self, all_results: list[dict]) -> None:
        if not all_results:
            print("  ⚠️ Keine Ergebnisse zum Exportieren vorhanden.")
            return

        # KORREKTUR: Sortierung auf die chronologische Reihenfolge des Monolithen umgestellt!
        all_results.sort(key=lambda x: (x.get("Datum", ""), x.get("Gruppe", ""), x.get("Test_Standard", "")))

        try:
            with open(config.OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.fieldnames, delimiter=";", extrasaction="ignore")
                writer.writeheader()
                writer.writerows(all_results)
                
            print(f"  💾 {len(all_results)} Werte erfolgreich nach '{config.OUTPUT_FILE.name}' exportiert.")
            
        except (IOError, OSError) as e:
            print(f"  ❌ Fehler beim Schreiben der CSV-Datei: {e}")
