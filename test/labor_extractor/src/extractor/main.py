import logging
from pathlib import Path
from extractor.parsers.detector import detect_format
from extractor.parsers.freetext import parse_freetext_file
from extractor.parsers.table import parse_table_format, parse_pivot_format
from extractor.parsers.csv_tab import parse_csv_format, parse_tab_format, parse_simple_csv
from extractor.parsers.kuerzel import parse_kuerzel_space_format
from extractor.parsers.pdf import parse_pdf_text_format

# Mapping von ercanntem Format zur alten Parser-Funktion
PARSER_REGISTRY = {
    "freetext": parse_freetext_file,
    "table": parse_table_format,
    "pivot": parse_pivot_format,
    "csv": parse_csv_format,
    "tab": parse_tab_format,
    "simple_csv": parse_simple_csv,
    "kuerzel_space": parse_kuerzel_space_format,
    "pdf_text": parse_pdf_text_format,
}

def extract_labor_data(filepath: Path) -> list[dict]:
    """Zentrale Orchestrierung für die Erkennung und das Parsing."""
    if not filepath.exists():
        raise FileNotFoundError(f"Datei existiert nicht: {filepath}")

    # 1. Format erkennen (Code wurde von Rope nach detector.py geschoben)
    file_format = detect_format(filepath)
    logging.info(f"Erkanntes Format: '{file_format}' für {filepath.name}")

    # 2. Passende Funktion holen
    parse_func = PARSER_REGISTRY.get(file_format)
    if not parse_func:
        raise ValueError(f"Kein Parser für Format '{file_format}' gefunden.")

    # 3. Ausführen
    return parse_func(filepath)

def main():
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    
    if len(sys.argv) < 2:
        print("Syntax: python -m extractor.main <dateipfad>")
        sys.exit(1)
        
    target_file = Path(sys.argv[1])
    try:
        results = extract_labor_data(target_file)
        print(f"Erfolgreich extrahiert: {len(results)} Datensätze.")
    except Exception as e:
        logging.error(f"Fehler: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
