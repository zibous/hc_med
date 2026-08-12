import csv
import re
from pdf2image import convert_from_path
import pytesseract

pdf_path = "../data/user/peter/docs/Laborbericht-13.06.2018.pdf"
csv_path = "laborbericht_sauber.csv"

print("="*60)
print(f"STARTE LABORBERICHT-EXTRAKTION")
print(f"Datei: {pdf_path}")
print("="*60)

# 1. PDF-Seiten in Bilder umwandeln
print("-> Wandle PDF-Seiten in Bilder um... (Bitte warten)")
seiten = convert_from_path(pdf_path)
gesamt_seiten = len(seiten)
print(f"-> {gesamt_seiten} Seiten erfolgreich geladen.\n")

# Erweiterte Regex, um noch mehr Einheiten-Variationen abzufangen
labor_regex = re.compile(
    r'^([A-Za-zÄÖÜäöüß\s,\.\/\-]+?)\s+'     # 1. Name der Untersuchung
    r'(\d+[\.,]\d+|\d+)\s+'                # 2. Messwert
    r'(\S+)\s+'                            # 3. Einheit
    r'(\d+[\.,]\d+-\d+[\.,]\d+|\d+-\d+)'   # 4. Referenzbereich
)

print("-> Starte Texterkennung (OCR) und CSV-Erstellung...\n")
print("Untersuchung,Messwert,Einheit,Referenzbereich") # Header in der Konsole anzeigen

with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["Untersuchung", "Messwert", "Einheit", "Referenzbereich"])
    
    # Schleife über alle Seiten
    for seiten_index, seite in enumerate(seiten, start=1):
        # Visuelle Trennung in der Konsole für den Fortschritt
        print(f"\n--- VERARBEITE SEITE {seiten_index} VON {gesamt_seiten} ---")
        
        # OCR ausführen
        text = pytesseract.image_to_string(seite, lang="deu", config='--psm 6')
        
        # Zeilenweise Auswertung
        for zeile in text.split("\n"):
            zeile = zeile.strip()
            
            match = labor_regex.search(zeile)
            if match:
                untersuchung = match.group(1).strip()
                messwert = match.group(2).strip()
                einheit = match.group(3).strip()
                bereich = match.group(4).strip()
                
                # Bekannte Tesseract-Lesefehler bei Einheiten korrigieren
                if einheit.lower() in ["inl", "1nl"]: einheit = "/nl"
                if einheit.lower() in ["ipl", "1pl"]: einheit = "/pl"
                if einheit.lower() in ["in", "1n", "nl"]: einheit = "/nl" # Fix für Lymphozyten abs.
                if "mmol" in einheit.lower(): einheit = "mmol/l"
                if "mg/d" in einheit.lower() or "mgldi" in zeile.lower(): einheit = "mg/dl"
                
                # MCV "v" oder ähnliche Artefakte am Namensende entfernen
                untersuchung = re.sub(r'\s+[a-zA-Z]$', '', untersuchung)
                
                # In Datei schreiben
                writer.writerow([untersuchung, messwert, einheit, bereich])
                
                # Live-Ausgabe im Terminal
                print(f"{untersuchung},{messwert},{einheit},{bereich}")
                
            elif re.search(r'\d+[\.,]\d+', zeile):
                # Fallback für Zeilen ohne starres Muster
                teile = [t.strip() for t in re.split(r'\s{2,}', zeile) if t.strip()]
                if len(teile) >= 3:
                    writer.writerow(teile[:4])
                    print(f"[Fallback] {','.join(teile[:4])}")

print("\n" + "="*60)
print(f"FERTIG! Alle {gesamt_seiten} Seiten wurden verarbeitet.")
print(f"Ergebnisse gespeichert in: {csv_path}")
print("="*60)
