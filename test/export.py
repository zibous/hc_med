import pdfplumber
import csv

pdf_path = "../data/user/peter/docs/Laborbericht-13.06.2018.pdf"
csv_path = "laborbericht_text.csv"

print("Starte Textextraktion...")

with pdfplumber.open(pdf_path) as pdf:
    with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        
        for seiten_nummer, seite in enumerate(pdf.pages, start=1):
            text = seite.extract_text()
            
            if text:
                print(f"Text auf Seite {seiten_nummer} gefunden. Schreibe in CSV...")
                # Teilt den Text in einzelne Zeilen auf
                for zeile in text.split("\n"):
                    # Option A: Zeile so wie sie ist als einzelne Spalte schreiben
                    writer.writerow([zeile])
            else:
                print(f"Warnung: Seite {seiten_nummer} enthält keinen Text (Evtl. ein Bild/Scan).")

print(f"Fertig! Datei wurde gespeichert unter: {csv_path}")
