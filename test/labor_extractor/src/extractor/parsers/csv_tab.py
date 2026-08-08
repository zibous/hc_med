import re
from pathlib import Path


def parse_simple_csv(filepath: Path) -> list[dict]:
    """Parse das einfache CSV-Format (Vorlage für Numbers/Excel).

    Header: Gruppe;Test;Wert;Einheit;Normbereich;Flag
    Datum wird aus dem Dateinamen extrahiert (YYYY-MM-DD_...).
    Leere Wert-Felder werden übersprungen.
    """
    results = []
    text = filepath.read_text(encoding="utf-8", errors="replace")

    # Datum aus Dateinamen
    date_match = re.search(r"(\d{4})-(\d{2})-(\d{2})", filepath.name)
    if not date_match:
        return results
    file_date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"

    lines = text.splitlines()
    for line in lines:
        line = line.strip()
        # Header und leere Zeilen überspringen
        if not line or line.startswith("Gruppe;Test") or line.startswith("#"):
            continue

        parts = line.split(";")
        if len(parts) < 3:
            continue

        test = parts[1].strip() if len(parts) > 1 else ""
        wert = parts[2].strip() if len(parts) > 2 else ""
        einheit = parts[3].strip() if len(parts) > 3 else ""
        norm = parts[4].strip() if len(parts) > 4 else ""
        flag = parts[5].strip() if len(parts) > 5 else ""

        # Leere Werte überspringen
        if not wert or not test:
            continue

        results.append({
            "Datum": file_date,
            "Test": test,
            "Wert": wert.replace(",", "."),
            "Einheit": einheit,
            "Normbereich": norm,
            "Flag": flag,
        })

    return results


def parse_tab_format(filepath: Path) -> list[dict]:
    """Parse das Tab-getrennte Format (Arztpraxis Zünd).

    Header: Kürzel  Bezeichnung  Path  Wert  Einh.  Referenz
    """
    results = []
    text = filepath.read_text(encoding="utf-8", errors="replace")

    # Datum aus Dateinamen extrahieren
    date_match = re.search(r"(\d{4})-(\d{2})-(\d{2})", filepath.name)
    if not date_match:
        return results
    file_date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"

    lines = text.splitlines()
    in_data = False

    for line in lines:
        # Zero-width spaces und andere Unicode-Zeichen bereinigen
        line = line.replace("\u200b", "").replace("\ufeff", "").strip()

        # Header-Zeile erkennen
        if "Kürzel" in line and "Bezeichnung" in line and "Wert" in line:
            in_data = True
            continue

        if not in_data or not line:
            continue

        # Tab-getrennte Felder
        parts = line.split("\t")
        # Mindestens Kürzel, Bezeichnung, ?, Wert brauchen wir
        if len(parts) < 4:
            continue

        kuerzel = parts[0].strip()
        bezeichnung = parts[1].strip()
        flag = parts[2].strip() if len(parts) > 2 else ""  # Path/*-Flag
        wert = parts[3].strip() if len(parts) > 3 else ""
        einheit = parts[4].strip() if len(parts) > 4 else ""
        referenz = parts[5].strip() if len(parts) > 5 else ""

        # Abschnitts-Header überspringen (z.B. "CHEMIE  KLINISCHE CHEMIE")
        if not wert or wert.upper() == wert and not any(c.isdigit() for c in wert):
            continue

        # Qualitative Werte wie "negativ", "normal" auch aufnehmen
        # aber nur wenn es ein gültiger Laborwert ist
        if wert.lower() in ("negativ", "normal", "positiv", "pos", "neg"):
            # Qualitative Werte übernehmen
            pass
        else:
            # Prüfen ob numerischer Wert (evtl. mit < oder >)
            numeric_check = re.match(r"[<>]?\s*\d", wert)
            if not numeric_check:
                continue

        # Einheit aus Referenz-Feld bereinigen (z.B. "0.70 - 1.20 mg/dL" -> Norm: "0.70-1.20")
        norm_clean = referenz
        # Einheit am Ende der Referenz entfernen
        if einheit and norm_clean.endswith(einheit):
            norm_clean = norm_clean[: -len(einheit)].strip()
        # Leerzeichen um Bindestrich entfernen
        norm_clean = re.sub(r"\s*-\s*", "-", norm_clean)

        # Flag aus Path-Spalte (* = pathologisch)
        flag_str = "H" if flag == "*" else ""

        # Testname: Bezeichnung bevorzugen, Kürzel als Fallback
        test_name = bezeichnung if bezeichnung else kuerzel

        results.append({
            "Datum": file_date,
            "Test": test_name,
            "Wert": wert.replace(",", "."),
            "Einheit": einheit,
            "Normbereich": norm_clean,
            "Flag": flag_str,
        })

    return results


def parse_csv_format(filepath: Path) -> list[dict]:
    """Parse das semikolon-getrennte Format (2025-01-06).

    Format: Tag;Test;Norm;Erst-Wert;Min-Wert;Max-Wert;Letzt-Wert;Einheit
    """
    results = []
    text = filepath.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    for line in lines:
        if line.startswith("Tag;") or not line.strip():
            continue

        parts = line.split(";")
        if len(parts) < 5:
            continue

        # Datum umformatieren: DD.MM.YYYY -> YYYY-MM-DD
        raw_date = parts[0].strip()
        date_match = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", raw_date)
        if date_match:
            date_str = f"{date_match.group(3)}-{date_match.group(2)}-{date_match.group(1)}"
        else:
            date_str = raw_date

        test_name = parts[1].strip()
        norm = parts[2].strip() if len(parts) > 2 else ""

        # Letzt-Wert oder Erst-Wert nehmen
        erst_wert = parts[3].strip() if len(parts) > 3 else ""
        letzt_wert = parts[6].strip() if len(parts) > 6 else ""

        value = letzt_wert if letzt_wert else erst_wert
        unit = parts[-1].strip() if parts[-1].strip() else (parts[7].strip() if len(parts) > 7 else "")

        if value:
            results.append({
                "Datum": date_str,
                "Test": test_name,
                "Wert": value.replace(",", "."),
                "Einheit": unit,
                "Normbereich": norm,
                "Flag": "",
            })

    return results
