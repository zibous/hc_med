#!/usr/bin/env python3
import sys
import json
from pathlib import Path

# Fügt das 'src'-Verzeichnis dynamisch zum Python-Suchpfad hinzu
SRC_PATH = Path(__file__).parent / "labor_extractor" / "src"
sys.path.insert(0, str(SRC_PATH))

# Importiert die zentrale Orchestrierungs-Funktion aus der neuen Struktur
from extractor.main import extract_labor_data

def main():
    # Prüfen, ob eine Datei übergeben wurde
    if len(sys.argv) < 2:
        print("Nutzung: python extract_labvalues.py <pfad_zur_labordatei>", file=sys.stderr)
        sys.exit(1)

    filepath = Path(sys.argv[1])
    
    try:
        # Ausführung des neuen modularen Extraktors
        data = extract_labor_data(filepath)
        
        # Ausgabe der extrahierten Daten als formatiertes JSON
        print(json.dumps(data, indent=2, ensure_ascii=False))
        
    except FileNotFoundError as e:
        print(f"Fehler: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Formatfehler: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unerwarteter Fehler bei der Verarbeitung: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
