from pathlib import Path


def detect_format(filepath: Path) -> str:
    """Erkennt das Format einer Befund-Datei."""
    text = filepath.read_text(encoding="utf-8", errors="replace")
    first_lines = text[:500]

    # Einfaches CSV-Format (Vorlage): "Gruppe;Test;Wert;Einheit;Normbereich;Flag"
    if first_lines.startswith("Gruppe;Test;Wert"):
        return "simple_csv"

    # Pivot-Format: Header beginnt mit "Parameter;Einheit;Referenz;" gefolgt von Datumsspalten
    if first_lines.startswith("Parameter;") and "Referenz" in first_lines:
        return "pivot"
    if ";" in first_lines and ("Tag;" in first_lines or first_lines.count(";") > 5):
        # Unterscheidung: pivot hat viele Semikolons in Zeile 1 (>5 Datumsspalten)
        first_line = first_lines.split("\n")[0]
        if first_line.count(";") > 8 and not first_line.startswith("Tag;"):
            return "pivot"
        return "csv"
    if "\t" in first_lines and ("Kürzel" in first_lines or "Bezeichnung" in first_lines):
        return "tab"
    # Kürzel-Format mit Leerzeichen (OCR-gescannte Arztbefunde)
    if "Kürzel" in first_lines and "Bezeichnung" in first_lines and "\t" not in first_lines:
        return "kuerzel_space"
    if "Analyse" in first_lines and "Ergebnis" in first_lines and "Referenz" in first_lines:
        return "pdf_text"
    if "Laborbefund vom" in first_lines:
        return "freetext"
    if "Test" in first_lines and "Norm" in first_lines and "Einheit" in first_lines:
        return "table"

    # Fallback: prüfe ob viele Semikolons
    if text.count(";") > 20:
        return "csv"
    # Fallback: viele Tabs deuten auf Tab-Format
    if text.count("\t") > 10:
        return "tab"

    return "freetext"
