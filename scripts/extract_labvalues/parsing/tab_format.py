import re
from pathlib import Path


def parse_tab_format(filepath: Path) -> list[dict]:
    """Parse das Tab-getrennte Format (Arztpraxis Zünd).

    Header: Kürzel    Bezeichnung    Path    Wert    Einh.    Referenz
    Beispiel:
        KREA    Kreatinin    *    1,01    mg/dl    0,70 - 1,20 mg/dl
        WBC     Leukozyten   H    13,4    G/L      4,0 - 11,0 G/L
    """

    text = filepath.read_text(encoding="utf-8", errors="replace")
    results = []

    # Datum aus Dateinamen extrahieren: YYYY-MM-DD
    dm = re.search(r"(\d{4})-(\d{2})-(\d{2})", filepath.name)
    if not dm:
        return results

    file_date = f"{dm.group(1)}-{dm.group(2)}-{dm.group(3)}"

    lines = text.splitlines()
    in_data = False

    for raw_line in lines:
        # Unicode-Bereinigung
        line = raw_line.replace("\u200b", "").replace("\ufeff", "").strip()
        if not line:
            continue

        # Header erkennen
        if ("Kürzel" in line and "Bezeichnung" in line and "Wert" in line):
            in_data = True
            continue

        if not in_data:
            continue

        parts = line.split("\t")
        if len(parts) < 4:
            continue

        kuerzel = parts[0].strip()
        bezeichnung = parts[1].strip()
        flag = parts[2].strip()
        wert = parts[3].strip()
        einheit = parts[4].strip() if len(parts) > 4 else ""
        referenz = parts[5].strip() if len(parts) > 5 else ""

        # Abschnittsüberschriften überspringen
        if kuerzel.isupper() and not any(c.isdigit() for c in wert):
            continue

        # Qualitative Werte erlauben (negativ, positiv, normal)
        qualitative = wert.lower() in ("negativ", "positiv", "pos", "neg", "normal")

        # Numerische Werte erkennen
        numeric = re.match(r"[<>]?\s*\d+[.,]?\d*", wert)

        if not qualitative and not numeric:
            continue

        # Wert normalisieren
        wert_norm = wert.replace(",", ".")

        # Einheit normalisieren
        einheit = einheit.replace("d1", "dL").replace("Т/L", "T/L").replace("응", "%")

        # Referenzbereich extrahieren
        norm = ""
        if referenz:
            # Beispiel: "0,70 - 1,20 mg/dl"
            # Einheit entfernen
            ref = referenz.replace(",", ".")
            if einheit and ref.lower().endswith(einheit.lower()):
                ref = ref[:-len(einheit)].strip()

            # Bereich extrahieren
            m = re.search(r"([\d.<>\- ]+)", ref)
            if m:
                norm = m.group(1).strip().replace(" ", "").replace("--", "-")

        results.append({
            "Datum": file_date,
            "Test": bezeichnung,
            "Wert": wert_norm,
            "Einheit": einheit,
            "Normbereich": norm,
            "Flag": flag,
        })

    return results
