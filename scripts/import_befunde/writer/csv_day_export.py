import csv
import logging
from collections import defaultdict
from pathlib import Path
from config.app_config import config

log = logging.getLogger("labor_pipeline")

def export_values_per_day(all_results: list):
    """Gruppiert alle extrahierten Laborergebnisse nach Datum und schreibt pro Tag eine separate CSV."""
    
    # 1. Zielverzeichnis dynamisch aus der Patienten-Config berechnen
    export_dir = config.USER_DIR / "export"
    export_dir.mkdir(parents=True, exist_ok=True)
    
    # 2. Daten im Speicher nach Datum bündeln
    data_by_day = defaultdict(list)
    for row in all_results:
        # Robustheits-Check für den Testnamen
        test_name = row.get("Test_Standard") or row.get("Test")
        if not test_name:
            continue
        
        datum = row.get("Datum", "UNBEKANNT")
        data_by_day[datum].append(row)
        
    log.info(f"\n📂 Generiere Tages-Exporte unter: '{export_dir.name}/'")
    
    # 3. Pro Tag eine strukturierte CSV schreiben
    for datum, rows in sorted(data_by_day.items()):
        file_path = export_dir / f"laborwerte_{datum}.csv"
        
        headers = ["Blutwert", "Normwert", "Messwert", "Einheit", "Bewertung"]
        
        with open(file_path, mode="w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(headers)
            
            for r in rows:
                # 💡 TOLE-FALLBACKS: Holt die Daten felsenfest aus den richtigen Spalten
                blutwert = r.get("Test_Standard") or r.get("Test", "")
                normwert = r.get("Normbereich") or r.get("Norm", "")
                messwert = r.get("Wert_Norm") or r.get("Wert", "")
                einheit = r.get("Einheit_Norm") or r.get("Einheit", "")
                bewertung = r.get("Flag", "-")
                
                writer.writerow([
                    str(blutwert).strip(),
                    str(normwert).strip(),
                    str(messwert).strip(),
                    str(einheit).strip(),
                    str(bewertung).strip()
                ])
                
    log.info(f"  ✓ {len(data_by_day)} separate Tages-CSV-Dateien erfolgreich exportiert.")
