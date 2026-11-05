from pathlib import Path

def detect_format(filepath: Path) -> str:
    """Erkennt das Format einer Befund-Datei basierend auf den ersten Zeilen."""
    try:
        text = filepath.read_text(encoding="utf-8", errors="replace")
    except (IOError, OSError):
        return "freetext"

    if not text.strip():
        return "freetext"

    # Die ersten 10 Zeilen sauber trennen und leere Zeilen ignorieren
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return "freetext"

    # Für Header-Checks nutzen wir die allererste echte Zeile
    first_line = lines[0]
    # Für kombinierte Checks nehmen wir die ersten paar Zeilen als Block
    sample_block = "\n".join(lines[:10])

    # 1. Einfaches CSV-Format (Vorlage)
    if first_line.startswith("Gruppe;Test;Wert"):
        fmt = "simple_csv"
        # print(f"  🔍 [Autodetect] {filepath.name} -> MATCH: Gruppe;Test;Wert ({fmt})")
        return fmt

    # 1b. KH-Feldkirch CSV-Format: Test;Wert;Flag;Einheit;Normbereich
    if first_line.startswith("Test;Wert;") or first_line.startswith("Test;Wert;Flag"):
        fmt = "simple_csv"
        # print(f"  🔍 [Autodetect] {filepath.name} -> MATCH: Test;Wert;Flag ({fmt})")
        return fmt

    # 2. Pivot-Format: Header beginnt mit "Parameter;Einheit;Referenz;"
    if first_line.startswith("Parameter;") and "Referenz" in first_line:
        fmt = "pivot"
        # print(f"  🔍 [Autodetect] {filepath.name} -> MATCH: Parameter;Einheit;Referenz ({fmt})")
        return fmt

    # 3. Strukturierte Semikolon-Formate (CSV oder Pivot-Varianten)
    if ";" in sample_block:
        if first_line.count(";") > 8 and not first_line.startswith("Tag;"):
            fmt = "pivot"
            # print(f"  🔍 [Autodetect] {filepath.name} -> MATCH: Semikolon-Zähler > 8 ({fmt})")
            return fmt
        if "Tag;" in sample_block or first_line.count(";") > 5:
            fmt = "csv"
            # print(f"  🔍 [Autodetect] {filepath.name} -> MATCH: Standard-Semikolon-CSV ({fmt})")
            return fmt

    # 4. Tab-getrenntes Format (Arztpraxis Zünd)
    if "\t" in sample_block and ("Kürzel" in sample_block or "Bezeichnung" in sample_block):
        fmt = "tab"
        # print(f"  🔍 [Autodetect] {filepath.name} -> MATCH: Tab-Format Kürzel/Bezeichnung ({fmt})")
        return fmt

    # 5. Kürzel-Format mit Leerzeichen (OCR-gescannte Arztbefunde)
    if "Kürzel" in sample_block and "Bezeichnung" in sample_block and "\t" not in sample_block:
        fmt = "kuerzel_space"
        # print(f"  🔍 [Autodetect] {filepath.name} -> MATCH: Kürzel-Space ({fmt})")
        return fmt

    # 6. Aus PDF extrahiertes Textformat
    if "Analyse" in sample_block and "Ergebnis" in sample_block and "Referenz" in sample_block:
        fmt = "pdf_text"
        # print(f"  🔍 [Autodetect] {filepath.name} -> MATCH: PDF-Text Analyse ({fmt})")
        return fmt

    # 7. Standard-Tabellenformat
    if "Test" in sample_block and "Norm" in sample_block and "Einheit" in sample_block:
        fmt = "table"
        # print(f"  🔍 [Autodetect] {filepath.name} -> MATCH: Standard-Tabelle ({fmt})")
        return fmt

    # 8. Klassisches Freitext-Format
    if "Laborbefund vom" in sample_block:
        fmt = "freetext"
        # print(f"  🔍 [Autodetect] {filepath.name} -> MATCH: Freitext Laborbefund ({fmt})")
        return fmt

    # ─── Fallbacks über die gesamte Datei ─────────────────────────────────────
    if text.count(";") > 20:
        fmt = "csv"
        # print(f"  🔍 [Autodetect] {filepath.name} -> FALLBACK: Semikolons > 20 ({fmt})")
        return fmt
    if text.count("\t") > 10:
        fmt = "tab"
        # print(f"  🔍 [Autodetect] {filepath.name} -> FALLBACK: Tabs > 10 ({fmt})")
        return fmt

    # print(f"  🔍 [Autodetect] {filepath.name} -> NO MATCH: Fallback auf freetext")
    return "freetext"
