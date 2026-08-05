"""Extraktion von Laborwerten aus den Befund-Textdateien in eine CSV-Datei.

Unterstützte Formate:
- Freitext-Format (2018er Befunde, 2024-02-08): "Testname  Wert  Einheit  Norm"
- Tabellenformat (2024-12-06): "Test  Norm  Erst-Wert  Min  Max  Letzt  Einheit"
- CSV-Format (2025-01-06): Semikolon-getrennt mit Header
- Tab-Format (Arztpraxis Zünd): Tab-getrennt mit Kürzel/Bezeichnung
- PDF-Text-Format (2024-12-01, 2024-12-11): Aus PDF extrahiert

Ausgabe: CSV mit Spalten: Datum, Alter, Gruppe, Test, Test_Standard, Wert, Wert_Norm, Einheit, Einheit_Norm, Normbereich, Flag
"""

import csv
import re
from datetime import date, datetime
from pathlib import Path

BEFUNDE_DIR = Path(__file__).parent.parent / "data" / "befunde"
OUTPUT_FILE = BEFUNDE_DIR / "laborwerte_gesamt.csv"
CONFIG_PATH = Path(__file__).parent.parent / "data" / "labor_config.yaml"

import yaml
_config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
_patient = _config.get("patient", {})

# Patient-Daten aus Config
PATIENT_GEBURTSDATUM = date(*[int(x) for x in _patient.get("geburtsdatum", "1955-12-16").split("-")])
PATIENT_GESCHLECHT = _patient.get("geschlecht", "m")


# ─── Testnamen-Normalisierung ──────────────────────────────────────────────────
# Mapping: (lowercase-Pattern im Original) -> Standard-Name
TEST_ALIASES: dict[str, str] = {
    # Blutbild
    "leukocyten": "Leukozyten",
    "leuko": "Leukozyten",
    "leukozyten": "Leukozyten",
    "leukozyten abs.": "Lymphozyten abs.",
    "erythrocyten": "Erythrozyten",
    "erythrozyten": "Erythrozyten",
    "erythrozyten rdw": "RDW",
    "ery": "Erythrozyten",
    "hämoglobin": "Hämoglobin",
    "hgb": "Hämoglobin",
    "hbe (mca)": "MCH",
    "hb": "Hämoglobin",
    "hämatokrit": "Hämatokrit",
    "hk": "Hämatokrit",
    "mcv": "MCV",
    "mch": "MCH",
    "mchc": "MCHC",
    "rdw": "RDW",
    "rdw-cv": "RDW",
    "thrombocyten": "Thrombozyten",
    "thrombozyten": "Thrombozyten",
    "thrombo": "Thrombozyten",
    "mpv": "MPV",
    "mpv (mittleres thrombozytenvolumen)": "MPV",
    # Differentialblutbild
    "neutrophile %": "Neutrophile rel.",
    "neutrophile absolut": "Neutrophile abs.",
    "neutroph. gran. abs.": "Neutrophile abs.",
    "neutroph. gran. rel.": "Neutrophile rel.",
    "neutrophile abs": "Neutrophile abs.",
    "neutrophile abs.": "Neutrophile abs.",
    "neutrophile": "Neutrophile rel.",
    "granulocytes": "Granulozyten rel.",
    "granulozyten": "Granulozyten rel.",
    "index ldl/hdl": "Quotient LDL/HDL",
    "gran.aut.": "Granulozyten rel.",
    "granul.abs": "Granulozyten abs.",
    "lymphocyten %": "Lymphozyten rel.",
    "lymphocyten absolut": "Lymphozyten abs.",
    "lymphozyten abs.": "Lymphozyten abs.",
    "lymphozyten rel.": "Lymphozyten rel.",
    "lymphozyten": "Lymphozyten rel.",
    "lymph.abs.": "Lymphozyten abs.",
    "lymph.aut.": "Lymphozyten rel.",
    "monocyten %": "Monozyten rel.",
    "mono absolut": "Monozyten abs.",
    "monozyten abs.": "Monozyten abs.",
    "monozyten rel.": "Monozyten rel.",
    "mono.aut.": "Monozyten rel.",
    "mono": "Monozyten abs.",
    "monozyten": "Monozyten rel.",
    "eosinophile %": "Eosinophile rel.",
    "eosinophile gr. abs.": "Eosinophile abs.",
    "eosinophile gr. rel.": "Eosinophile rel.",
    "eosinophile": "Eosinophile rel.",
    "eos.aut.": "Eosinophile rel.",
    "eos": "Eosinophile abs.",
    "basophile %": "Basophile rel.",
    "basophile gr.abs.": "Basophile abs.",
    "basophile gr.rel.": "Basophile rel.",
    "baso.aut.": "Basophile rel.",
    "baso": "Basophile abs.",
    # Unreife Granulozyten / Normoblasten (KH-spezifisch)
    "ig-absolut": "IG-Absolut",
    "ig-wert": "IG-Wert",
    "nrbc": "NRBC",
    "nrbc-a": "NRBC-A",
    "normoblast.(nrbc)rt.": "NRBC",
    "normoblasten (nrbc) abs.": "NRBC-A",
    "unreife neutrophile granulozyten abs.": "IG-Absolut",
    "gran., unreife rel.": "IG-Wert",
    # Entzündung
    "crp": "CRP",
    "crp hs": "CRP",
    "interleukin 6": "Interleukin-6",
    "procalcitonin": "Procalcitonin",
    "bsg nach 1 h": "BSG 1h",
    "bsg nach 2 h": "BSG 2h",
    "rheumafaktor": "Rheumafaktor",
    # Leber
    "got (asat)": "GOT",
    "asat (got)": "GOT",
    "ast(got)": "GOT",
    "gpt (alat)": "GPT",
    "alat (gpt)": "GPT",
    "alt(gpt)": "GPT",
    "ggt": "GGT",
    "gamma-gt": "GGT",
    "gamma-glutaminyltransferase": "GGT",
    "ggt-37": "GGT",
    "alk.phos.": "Alk. Phosphatase",
    "alk.phosphatase (ap)": "Alk. Phosphatase",
    "bilirubin gesamt": "Bilirubin",
    "bilirubin": "Bilirubin",
    "ldh": "LDH",
    "che": "Cholinesterase",
    "cholinesterase": "Cholinesterase",
    # Niere
    "kreatinin": "Kreatinin",
    "gfr-ckd/1.73m2": "GFR",
    "gfr-ckd": "GFR",
    "gfr-ckd krea": "GFR",
    "gfr (ckd-epi)": "GFR",
    "harnstoff": "Harnstoff",
    "harnsäure": "Harnsäure",
    # Elektrolyte
    "natrium": "Natrium",
    "kalium": "Kalium",
    "chlorid": "Chlorid",
    "calcium": "Calcium",
    "magnesium": "Magnesium",
    "phosphat": "Phosphat",
    # Stoffwechsel
    "glucose": "Glucose",
    "glucose nüchtern": "Glucose",
    "glukose": "Glucose",
    "hba1c (ngsp)": "HbA1c",
    "hba1c (ifcc)": "HbA1c (IFCC)",
    "hbalc (ngsp)": "HbA1c",
    "hbalc (ifcc)": "HbA1c (IFCC)",
    "hba1c": "HbA1c",
    "totalprotein": "Totalprotein",
    "g.eiweiss": "Totalprotein",
    # Lipide
    "cholesterin": "Cholesterin",
    "hdl-cholesterin": "HDL",
    "hdl cholesterin": "HDL",
    "ldl-cholesterin": "LDL",
    "ldl cholesterin": "LDL",
    "non-hdl-chol.": "Non-HDL-Cholesterin",
    "non-hdl-cholesterin": "Non-HDL-Cholesterin",
    "triglyceride": "Triglyceride",
    "quotient cholesterin/hdl": "Quotient Chol/HDL",
    "quotient hdl/cholesterin": "Quotient Chol/HDL",
    "quot. chol./hdl": "Quotient Chol/HDL",
    "index cholesterin/hdl": "Quotient Chol/HDL",
    "ldl/hdl quotient": "Quotient LDL/HDL",
    "ld/hdl": "Quotient LDL/HDL",
    "q-ldl": "Quotient LDL/HDL",
    # Pankreas
    "amylase": "Amylase",
    "p-amylase": "Pankreas-Amylase",
    "pankreas-amylase": "Pankreas-Amylase",
    "lipase": "Lipase",
    # Gerinnung
    "quick": "Quick",
    "quick (prothrombinzeit)": "Quick",
    "ptz (prothrombinz.)": "Quick",
    "inr (quick)": "INR",
    "inr": "INR",
    "ptt actin fs": "aPTT",
    "aptt": "aPTT",
    # Schilddrüse
    "tsh": "TSH",
    # Tumor-Marker
    "psa": "PSA",
    # Autoimmun
    "anti-ccp": "Anti-CCP",
    "anti-cardiolipin ak (aca)": "Anti-Cardiolipin",
    "anti-ß2-glycoprotein ak": "Anti-β2-Glycoprotein",
    "la-screen": "La-Screen",
    "la-confirm": "La-Confirm",
}


# ─── Einheiten-Normalisierung ──────────────────────────────────────────────────
# (Original-Einheit lowercase, Standard-Testname) -> (Ziel-Einheit, Umrechnungsfaktor)
UNIT_CONVERSIONS: dict[tuple[str, str], tuple[str, float]] = {
    # Hämoglobin: g/L_ -> g/dL (÷10)
    ("g/l_", "Hämoglobin"): ("g/dL", 0.1),
    ("g/l", "Hämoglobin"): ("g/dL", 0.1),
    # MCHC: g/L_ -> g/dL (÷10)
    ("g/l_", "MCHC"): ("g/dL", 0.1),
    ("g/l", "MCHC"): ("g/dL", 0.1),
    # Hämatokrit: L/L -> % (×100) – nur wenn Wert < 1
    ("l/l", "Hämatokrit"): ("%", 100.0),
    ("/l", "Hämatokrit"): ("%", 100.0),
    # Cholinesterase: KU/l -> U/L (×1000)
    ("ku/l", "Cholinesterase"): ("U/L", 1000.0),
    # Leukozyten: G/L = 10^9/l (gleich, nur Schreibweise)
    ("g/l", "Leukozyten"): ("10^9/L", 1.0),
    # Erythrozyten: T/L = 10^12/l
    ("t/l", "Erythrozyten"): ("10^12/L", 1.0),
    # Thrombozyten: G/L = 10^9/l
    ("g/l", "Thrombozyten"): ("10^9/L", 1.0),
    # MPV: g/dl ist falsch geparst aus Pivot -> fL
    ("g/dl", "MPV"): ("fL", 1.0),
}

# Standard-Einheiten pro Test (Ziel-Einheit wenn keine Konversion nötig)
STANDARD_UNITS: dict[str, str] = {
    "Hämoglobin": "g/dL",
    "MCHC": "g/dL",
    "Hämatokrit": "%",
    "Leukozyten": "10^9/L",
    "Erythrozyten": "10^12/L",
    "Thrombozyten": "10^9/L",
    "CRP": "mg/dL",
    "Kreatinin": "mg/dL",
    "GFR": "mL/min",
    "Glucose": "mg/dL",
    "Natrium": "mmol/L",
    "Kalium": "mmol/L",
    "GOT": "U/L",
    "GPT": "U/L",
    "GGT": "U/L",
}


def parse_freetext_file(filepath: Path) -> list[dict]:
    """Parse das Freitext-Format (2018, 2024-02-08).

    Erkennt Zeilen wie:
      Natrium          140     mmol/L   136-145
      CRP              4.69 H  mg/dL    < 0.50
      Leukocyten       8.5     G/L      3.7-10.0
    """
    results = []
    text = filepath.read_text(encoding="utf-8", errors="replace")

    # Datum aus dem Header extrahieren: "Laborbefund vom DD.MM.YYYY HH:MM"
    date_pattern = re.compile(r"Laborbefund vom (\d{2})\.(\d{2})\.(\d{4})")

    # Zeilen mit Laborwerten matchen:
    # Testname  [opt.Zusatz]  Wert  [opt.Flag H/L]  Einheit  Normbereich
    # Robusteres Pattern: alles vor dem numerischen Wert ist Testname
    value_pattern = re.compile(
        r"^([A-Za-zÄÖÜäöüß()./\-\s]+?)\s+"  # Testname (nicht-gierig)
        r"([<>]?\d+[.,]?\d*)\s*"  # Wert (numerisch, evtl. mit < oder >)
        r"(H|L|hämolyt\.)?\s*"  # Flag (optional)
        r"([A-Za-z%µ/^_°응]+(?:[/][A-Za-z²³]+)?\.?)\s*"  # Einheit (inkl. 응, Punkt am Ende)
        r"([<>]?\s*\d+[.,]?\d*(?:\s*-\s*\d+[.,]?\d*)?)?$"  # Norm (optional)
    )

    # Spezielles Pattern für GFR-CKD (Testname enthält Zahlen und /)
    gfr_pattern = re.compile(
        r"^GFR-CKD[\w\s/.]*?\s+(\d+)\s*(L|H)?\s*mL/min\s*([<>]?\d+)?$"
    )

    # Pattern für PTT/Quick mit Sek. oder 응
    ptt_pattern = re.compile(
        r"^(Quick \(Prothrombinzeit\)|PTT Actin FS)\s+([<>]?\d+[.,]?\d*)\s*(H|L)?\s*(Sek\.|응|%)\s*([\d.\-\s]+)?$"
    )

    current_date = None

    # Fallback: Datum aus Dateinamen extrahieren
    fname_date = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", filepath.name)
    if not fname_date:
        # Auch DD.MM.YYYY im Dateinamen
        fname_date = re.search(r"(\d{4})-(\d{2})-(\d{2})", filepath.name)
        if fname_date:
            current_date = f"{fname_date.group(1)}-{fname_date.group(2)}-{fname_date.group(3)}"
    else:
        current_date = f"{fname_date.group(3)}-{fname_date.group(2)}-{fname_date.group(1)}"

    for line in text.splitlines():
        line = line.strip()

        # Datum suchen
        dm = date_pattern.search(line)
        if dm:
            day, month, year = dm.group(1), dm.group(2), dm.group(3)
            current_date = f"{year}-{month}-{day}"
            continue

        # Abschnitts-Header überspringen
        if "--------" in line or not line:
            continue
        if line.startswith("Text ") or line.startswith("Lupus"):
            continue

        # Wert-Zeile matchen
        # Erst spezielle Patterns probieren
        gfr_m = gfr_pattern.match(line)
        if gfr_m and current_date:
            results.append({
                "Datum": current_date,
                "Test": "GFR-CKD",
                "Wert": gfr_m.group(1),
                "Einheit": "mL/min",
                "Normbereich": gfr_m.group(3) or "",
                "Flag": gfr_m.group(2) or "",
            })
            continue

        ptt_m = ptt_pattern.match(line)
        if ptt_m and current_date:
            unit = ptt_m.group(4)
            if unit == "응":
                unit = "%"
            results.append({
                "Datum": current_date,
                "Test": ptt_m.group(1),
                "Wert": ptt_m.group(2).replace(",", "."),
                "Einheit": unit,
                "Normbereich": (ptt_m.group(5) or "").strip(),
                "Flag": ptt_m.group(3) or "",
            })
            continue

        m = value_pattern.match(line)
        if m and current_date:
            test_name = m.group(1).strip()
            value = m.group(2).replace(",", ".")
            flag = m.group(3) or ""
            unit = m.group(4)
            norm = (m.group(5) or "").strip()

            # Texteinträge wie "neg", "pos" ausfiltern (kein numerischer Wert)
            if test_name and value:
                results.append({
                    "Datum": current_date,
                    "Test": test_name,
                    "Wert": value,
                    "Einheit": unit,
                    "Normbereich": norm,
                    "Flag": flag,
                })

    return results


def parse_table_format(filepath: Path) -> list[dict]:
    """Parse das Tabellenformat (2024-12-06).

    Header: Test  Norm  Erst-Wert  Min-Wert  Max-Wert  Letzt-Wert  Einheit
    Wir nehmen den Letzt-Wert (aktuellster), oder Erst-Wert als Fallback.
    """
    results = []
    text = filepath.read_text(encoding="utf-8", errors="replace")

    # Datum aus Dateinamen extrahieren
    date_match = re.search(r"(\d{4})-(\d{2})-(\d{2})", filepath.name)
    if not date_match:
        return results
    file_date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"

    # Zeilen mit Tabellenwerten matchen
    # Format: Testname  Norm  Erst-Wert  [Min]  [Max]  [Letzt]  Einheit
    lines = text.splitlines()
    in_data = False

    for line in lines:
        line = line.strip()

        # Header-Zeile erkennen
        if line.startswith("Test") and "Norm" in line and "Einheit" in line:
            in_data = True
            continue

        # Abschnitts-Header
        if any(h in line for h in ["Blutbild", "Klinische Chemie", "Gerinnung"]) and "Test" not in line:
            continue

        if not in_data or not line:
            continue

        # Tabellen-Zeile parsen (durch Whitespace getrennt)
        parts = line.split()
        if len(parts) < 3:
            continue

        test_name = parts[0]
        # Norm ist das zweite Feld
        norm = parts[1] if len(parts) > 1 else ""

        # Einheit ist das letzte Feld (wenn es typische Einheitsmuster hat)
        unit_pattern = re.compile(r"^(%|10\^[0-9]+/l|g/dl|mg/dl|mmol/l|U/l|fl|pg|ml/min/kof)$", re.IGNORECASE)
        unit = ""
        data_parts = parts[2:]

        if data_parts and unit_pattern.match(data_parts[-1]):
            unit = data_parts[-1]
            data_parts = data_parts[:-1]

        # Werte: Erst-Wert ist der erste numerische Wert nach Norm
        # Letzt-Wert ist der letzte
        numeric_values = []
        for p in data_parts:
            try:
                float(p.replace(",", "."))
                numeric_values.append(p.replace(",", "."))
            except ValueError:
                pass

        if not numeric_values:
            continue

        # Letzt-Wert bevorzugen, sonst Erst-Wert
        value = numeric_values[-1] if len(numeric_values) > 1 else numeric_values[0]

        results.append({
            "Datum": file_date,
            "Test": test_name,
            "Wert": value,
            "Einheit": unit,
            "Normbereich": norm,
            "Flag": "",
        })

    return results


def parse_kuerzel_space_format(filepath: Path) -> list[dict]:
    """Parse OCR-gescannte Befunde im Kürzel-Format mit Leerzeichen.

    Zeilen wie:
      KREA Kreatinin 1,01 mg/dl 0,70- 1,20 mg/dl
      WBC Leukozyten H 13,4 G/L 4,0 - 11,0 G/L
    """
    results = []
    text = filepath.read_text(encoding="utf-8", errors="replace")

    # Datum aus Dateinamen: "Peter 07.04.2019 Laborwerte.txt" oder "Peter 10.7.2019"
    date_match = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", filepath.name)
    if not date_match:
        return results
    day = date_match.group(1).zfill(2)
    month = date_match.group(2).zfill(2)
    year = date_match.group(3)
    file_date = f"{year}-{month}-{day}"

    # Mehrzeilige Einträge zusammenführen (OCR bricht manchmal Zeilen)
    lines = text.splitlines()
    merged_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Zeilen die mit Kürzel beginnen (Großbuchstaben, evtl. mit # oder Zahl)
        if re.match(r"^[A-Z][A-Z0-9#/]*\s", line) or line.startswith("Kürzel"):
            merged_lines.append(line)
        elif merged_lines:
            # Fortsetzungszeile an letzte anhängen
            merged_lines[-1] += " " + line

    # Bekannte Einheiten für die Erkennung
    unit_patterns = re.compile(
        r"\b(mg/dl|mg/d1|ng/ml|ug/dl|µg/dl|G/L|T/L|Т/L|g/dl|g/d1|fL|fl|pg|U/L|KU/l|"
        r"ml/Min|mm|mmol/mol|µmol/l|10[³3]/µl|10[⁶6]/µl|%|응)\b",
        re.IGNORECASE,
    )

    for line in merged_lines:
        if line.startswith("Kürzel") or "Thrombozytenaggregate" in line:
            continue

        # Pattern: KÜRZEL Bezeichnung [H|L] Wert Einheit [Referenz]
        m = re.match(
            r"^([A-Z][A-Z0-9#/]*)\s+"  # Kürzel
            r"(.+?)\s+"  # Bezeichnung
            r"(H|L)?\s*"  # Flag (optional)
            r"(\d+[.,]?\d*)\s*"  # Wert
            r"(.+)$",  # Rest (Einheit + Referenz)
            line,
        )
        if not m:
            continue

        bezeichnung = m.group(2).strip()
        flag = m.group(3) or ""
        wert = m.group(4).replace(",", ".")
        rest = m.group(5).strip()

        # Einheit aus Rest extrahieren (erste Einheit die wir finden)
        unit_match = unit_patterns.search(rest)
        unit = unit_match.group(1) if unit_match else ""

        # OCR-Korrekturen
        unit = unit.replace("응", "%").replace("d1", "dL").replace("Т/L", "T/L")

        # Referenzbereich: alles nach der Einheit bis zur nächsten Einheit
        norm = ""
        if unit_match:
            after_unit = rest[unit_match.end():].strip()
            # Referenz extrahieren: "0,70- 1,20 mg/dl" oder "0,1 - 0,6 mg/dl"
            norm_match = re.search(r"([\d,.<>]+\s*-?\s*[\d,.]*)", after_unit)
            if norm_match:
                norm = norm_match.group(1).replace(",", ".").strip()
                norm = re.sub(r"\s*-\s*", "-", norm)

        results.append({
            "Datum": file_date,
            "Test": bezeichnung,
            "Wert": wert,
            "Einheit": unit,
            "Normbereich": norm,
            "Flag": flag,
        })

    return results


def parse_pivot_format(filepath: Path) -> list[dict]:
    """Parse das Pivot-Tabellen-Format (laborwerte_2013-2029).

    Header: Parameter;Einheit;Referenz;18.10.13;12.12.13;24.10.14;...
    Zeilen: Testname;Einheit;Normbereich;Wert1;Wert2;Wert3;...

    Jede Spalte ab Position 3 ist ein Datum mit zugehörigem Wert.
    """
    results = []
    text = filepath.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    if not lines:
        return results

    # Header-Zeile parsen: Datumsspalten ab Index 3
    header_parts = lines[0].split(";")
    dates: list[str] = []
    for i, h in enumerate(header_parts[3:], start=3):
        h = h.strip()
        if not h:
            dates.append("")
            continue
        # Datum parsen: DD.MM.YY oder DD.MM.YYYY
        dm = re.match(r"(\d{2})\.(\d{2})\.(\d{2,4})", h)
        if dm:
            day, month, year = dm.group(1), dm.group(2), dm.group(3)
            if len(year) == 2:
                year = "20" + year if int(year) < 50 else "19" + year
            dates.append(f"{year}-{month}-{day}")
        else:
            dates.append("")

    # Daten-Zeilen parsen
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue

        parts = line.split(";")
        if len(parts) < 4:
            continue

        test_name = parts[0].strip()
        # Klammer-Kürzel entfernen: "Leukozyten (WBC)" -> "Leukozyten"
        clean_name = re.sub(r"\s*\([^)]+\)\s*$", "", test_name).strip()
        if not clean_name:
            continue

        unit = parts[1].strip() if len(parts) > 1 else ""
        norm_raw = parts[2].strip() if len(parts) > 2 else ""

        # Referenz bereinigen: Einheit am Ende entfernen, Komma->Punkt
        norm = norm_raw
        # Einheit aus Norm entfernen (z.B. "0,70 - 1,20 mg/dl" -> "0.70-1.20")
        if unit and norm.lower().endswith(unit.lower()):
            norm = norm[:-len(unit)].strip()
        if unit and norm.endswith("%"):
            norm = norm[:-1].strip()
        norm = norm.replace(",", ".").strip()
        norm = re.sub(r"\s*-\s*", "-", norm)

        # Werte pro Datum
        for idx, date_str in enumerate(dates):
            if not date_str:
                continue
            col_idx = idx + 3
            if col_idx >= len(parts):
                break

            value = parts[col_idx].strip().replace(",", ".")
            if not value:
                continue

            # Nicht-numerische Werte überspringen (z.B. "Thrombozytenaggregate vorhanden")
            if not re.match(r"[<>]?\d", value):
                continue

            results.append({
                "Datum": date_str,
                "Test": clean_name,
                "Wert": value,
                "Einheit": unit,
                "Normbereich": norm,
                "Flag": "",
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


def parse_pdf_text_format(filepath: Path) -> list[dict]:
    """Parse das aus PDF extrahierte Format (2024-12-01, 2024-12-11).

    Zeilen wie:
      Leukozyten 13.7 10^9/l 4.20- 9.10 +
      CRP 5.28 mg/dl -0.49 +
      Kreatinin 0.89 mg/dl 0.70- 1.20
    """
    results = []
    text = filepath.read_text(encoding="utf-8", errors="replace")

    # Datum aus Dateinamen
    date_match = re.search(r"(\d{4})-(\d{2})-(\d{2})", filepath.name)
    if not date_match:
        return results
    file_date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"

    # Einheiten die in diesem Format vorkommen
    known_units = {
        "10^9/l", "10^12/l", "g/dl", "mg/dl", "mmol/l", "U/l", "fl", "pg",
        "%", "ml/min/kof", "sek", "ng/ml", "µg/l",
    }

    lines = text.splitlines()
    skip_lines = {"In", "ter", "pre", "ta", "ti", "on"}

    for line in lines:
        line = line.strip()

        # Mehrzeilige Header-Fragmente überspringen
        if line in skip_lines or not line:
            continue

        # Abschnitts-Header, Fußnoten, PDF-Metazeilen überspringen
        if line.startswith(("Hämatologie", "Blutbild", "Gerinnung", "Klinische Chemie",
                           "Proteindiagnostik", "Hämostaseologie", "Analyse", "PDF-",
                           "Patient:", "1)", "2)", "3)")):
            continue

        # Zeile mit Laborwert matchen
        # Pattern: Testname (ein oder mehr Wörter)  Wert  Einheit  [Referenz]  [Flag]
        # Strategie: Einheit in der Zeile finden und davon ausgehend parsen
        match = None
        for unit in known_units:
            # Einheit in der Zeile suchen (als ganzes Wort)
            unit_escaped = re.escape(unit)
            unit_match = re.search(rf"\s({unit_escaped})(?:\s|$)", line, re.IGNORECASE)
            if unit_match:
                # Alles vor der Einheit aufteilen: letzte "Zahl" ist der Wert, Rest ist Testname
                before_unit = line[: unit_match.start()].strip()
                after_unit = line[unit_match.end():].strip()

                # Wert ist das letzte Token vor der Einheit
                parts = before_unit.rsplit(None, 1)
                if len(parts) == 2:
                    test_name = parts[0].strip()
                    value = parts[1].strip()
                elif len(parts) == 1:
                    # Nur ein Token -> könnte Wert ohne Testname sein, skip
                    continue
                else:
                    continue

                # Prüfen ob Wert numerisch ist (oder mit < / > beginnt)
                if not re.match(r"[<>]?\d", value):
                    continue

                # Flag aus dem Ende extrahieren (+, -, *)
                flag = ""
                if after_unit and after_unit[-1] in ("+", "-", "*"):
                    flag = "H" if after_unit[-1] == "+" else ("L" if after_unit[-1] == "-" else "")
                    after_unit = after_unit[:-1].strip()

                # Referenzbereich: was nach der Einheit übrig ist
                # Format: "4.20- 9.10" oder "-0.49" oder ">80" oder "0.70- 1.20"
                norm = re.sub(r"\s*-\s*", "-", after_unit).strip()

                match = {
                    "Datum": file_date,
                    "Test": test_name,
                    "Wert": value.replace(",", "."),
                    "Einheit": unit,
                    "Normbereich": norm,
                    "Flag": flag,
                }
                break

        # Sonderfall: Werte ohne Einheit (z.B. INR 1.14, Quotient)
        if not match:
            m = re.match(r"^([\w\s.()\-/]+?)\s+(\d+[.,]?\d*)\s*$", line)
            if m:
                test_name = m.group(1).strip()
                value = m.group(2).replace(",", ".")
                # Nur wenn der Testname sinnvoll aussieht
                if len(test_name) > 2 and not test_name[0].isdigit():
                    match = {
                        "Datum": file_date,
                        "Test": test_name,
                        "Wert": value,
                        "Einheit": "",
                        "Normbereich": "",
                        "Flag": "",
                    }

        if match:
            results.append(match)

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


# Mapping von Testnamen zu Gruppen.
# Schlüssel sind lowercase-Substrings die im Testnamen gesucht werden.
# Reihenfolge ist relevant: erste Übereinstimmung gewinnt.
GROUP_RULES: list[tuple[str, str]] = [
    # Harnanalyse (vor allgemeinen Matches wie "glucose", "eiweiß")
    ("u-", "Harnanalyse"),
    ("uf-", "Harnanalyse"),
    ("harn im", "Harnanalyse"),
    ("blut im harn", "Harnanalyse"),
    ("nitrit", "Harnanalyse"),
    ("ketone", "Harnanalyse"),
    ("urobilinogen", "Harnanalyse"),
    ("plattenepithel", "Harnanalyse"),
    ("hyaline zylinder", "Harnanalyse"),
    ("schleim", "Harnanalyse"),
    ("spez. gewicht", "Harnanalyse"),
    ("ph-wert", "Harnanalyse"),
    ("eiweiß qualitat", "Harnanalyse"),
    # Differentialblutbild
    ("neutrophil", "Differentialblutbild"),
    ("lymph", "Differentialblutbild"),
    ("mono", "Differentialblutbild"),
    ("eosinophil", "Differentialblutbild"),
    ("eos", "Differentialblutbild"),
    ("basophil", "Differentialblutbild"),
    ("baso", "Differentialblutbild"),
    ("gran", "Differentialblutbild"),
    ("ig-wert", "Differentialblutbild"),
    ("ig-absolut", "Differentialblutbild"),
    ("nrbc", "Differentialblutbild"),
    ("normoblast", "Differentialblutbild"),
    ("unreife", "Differentialblutbild"),
    # Blutbild
    ("leuko", "Blutbild"),
    ("leukocyt", "Blutbild"),
    ("erythro", "Blutbild"),
    ("ery", "Blutbild"),
    ("hämoglobin", "Blutbild"),
    ("hb", "Blutbild"),
    ("hämatokrit", "Blutbild"),
    ("hk", "Blutbild"),
    ("mcv", "Blutbild"),
    ("mch", "Blutbild"),
    ("mchc", "Blutbild"),
    ("rdw", "Blutbild"),
    ("thrombo", "Blutbild"),
    ("mpv", "Blutbild"),
    # Entzündung
    ("crp", "Entzündung"),
    ("interleukin", "Entzündung"),
    ("procalcitonin", "Entzündung"),
    ("bsg", "Entzündung"),
    ("blutsenk", "Entzündung"),
    ("blutkörperchensenkung", "Entzündung"),
    # Leber
    ("got", "Leber"),
    ("gpt", "Leber"),
    ("ast", "Leber"),
    ("alt(gpt)", "Leber"),
    ("asat", "Leber"),
    ("alat", "Leber"),
    ("ggt", "Leber"),
    ("gamma-gt", "Leber"),
    ("alk.phos", "Leber"),
    ("bilirubin", "Leber"),
    ("ldh", "Leber"),
    ("che", "Leber"),
    ("cholinesterase", "Leber"),
    # Niere
    ("kreatinin", "Niere"),
    ("gfr", "Niere"),
    ("harnstoff", "Niere"),
    ("harnsäure", "Niere"),
    # Elektrolyte
    ("natrium", "Elektrolyte"),
    ("kalium", "Elektrolyte"),
    ("chlorid", "Elektrolyte"),
    ("calcium", "Elektrolyte"),
    ("magnesium", "Elektrolyte"),
    ("phosphat", "Elektrolyte"),
    # Stoffwechsel
    ("gluc", "Stoffwechsel"),
    ("gluko", "Stoffwechsel"),
    ("hba1c", "Stoffwechsel"),
    ("totalprotein", "Stoffwechsel"),
    ("g.eiweiss", "Stoffwechsel"),
    # Lipide
    ("cholesterin", "Lipide"),
    ("hdl", "Lipide"),
    ("ldl", "Lipide"),
    ("non-hdl", "Lipide"),
    ("triglycerid", "Lipide"),
    ("quot. chol", "Lipide"),
    ("q-ldl", "Lipide"),
    ("ldl/hdl", "Lipide"),
    ("nonhdl", "Lipide"),
    # Pankreas
    ("amylase", "Pankreas"),
    ("lipase", "Pankreas"),
    # Gerinnung
    ("quick", "Gerinnung"),
    ("ptz", "Gerinnung"),
    ("inr", "Gerinnung"),
    ("ptt", "Gerinnung"),
    ("aptt", "Gerinnung"),
    # Schilddrüse
    ("tsh", "Schilddrüse"),
    ("t3", "Schilddrüse"),
    ("t4", "Schilddrüse"),
    ("calcitonin", "Schilddrüse"),
    ("pth", "Schilddrüse"),
    ("tg-ak", "Schilddrüse"),
    ("tpo-ak", "Schilddrüse"),
    ("thyreoglobulin", "Schilddrüse"),
    # Tumor-Marker
    ("psa", "Tumor-Marker"),
    # Autoimmun
    ("anti-ccp", "Autoimmun"),
    ("ccpr", "Autoimmun"),
    ("anti-cardiolipin", "Autoimmun"),
    ("ß2-glycoprotein", "Autoimmun"),
    ("rheumafaktor", "Autoimmun"),
    ("ana ", "Autoimmun"),
    ("anca", "Autoimmun"),
    ("la-screen", "Autoimmun"),
    ("la-confirm", "Autoimmun"),
    ("lupus", "Autoimmun"),
    # Sonstige / Spezial
    ("myoglobin", "Blutbild"),
    ("eisen", "Blutbild"),
    ("ferritin", "Blutbild"),
    ("senkung", "Entzündung"),
    ("gamma-glutamyl", "Leber"),
    ("testosteron", "Hormone"),
    ("peroxide", "Sonstige"),
    ("antioxid", "Sonstige"),
    ("gewicht", "Körperdaten"),
    ("fettgehalt", "Körperdaten"),
    ("fett", "Körperdaten"),
    ("bmi", "Körperdaten"),
    ("muskelmasse", "Körperdaten"),
]


def classify_test(test_name: str) -> str:
    """Ordnet einen Testnamen einer Gruppe zu."""
    name_lower = test_name.lower()
    for pattern, group in GROUP_RULES:
        if pattern in name_lower:
            return group
    return "Sonstige"


def normalize_test_name(test_name: str) -> str:
    """Normalisiert den Testnamen auf einen Standard-Namen."""
    name_lower = test_name.lower().strip()

    # Exakter Match (höchste Priorität)
    if name_lower in TEST_ALIASES:
        return TEST_ALIASES[name_lower]

    # Teilmatch: längere Patterns zuerst prüfen (spezifischer vor allgemein)
    sorted_aliases = sorted(TEST_ALIASES.items(), key=lambda x: -len(x[0]))
    for alias, standard in sorted_aliases:
        if alias in name_lower:
            # Schutz: kurze Aliases (<=3 Zeichen) nur am Wortanfang matchen
            if len(alias) <= 3:
                if name_lower.startswith(alias) and (len(name_lower) == len(alias) or not name_lower[len(alias)].isalnum()):
                    return standard
            else:
                return standard

    # Kein Match: Original zurückgeben (bereinigt)
    return test_name.strip()


def normalize_unit_and_value(test_standard: str, value_str: str, unit: str) -> tuple[str, str, str]:
    """Normalisiert Einheit und Wert.

    Returns: (normalisierter_wert, normalisierte_einheit, original_einheit)
    """
    unit_lower = unit.lower().strip()

    # Prüfen ob Konversion definiert
    conv_key = (unit_lower, test_standard)
    if conv_key in UNIT_CONVERSIONS:
        target_unit, factor = UNIT_CONVERSIONS[conv_key]

        # Wert konvertieren (nur wenn numerisch)
        try:
            numeric_val = float(value_str.replace(",", ".").replace("<", "").replace(">", ""))
            # Spezialfall Hämatokrit: nur konvertieren wenn Wert < 1 (also in L/L)
            if test_standard == "Hämatokrit" and numeric_val > 1:
                return value_str, unit, unit
            converted = numeric_val * factor
            # Sinnvolle Rundung
            if converted >= 100:
                converted_str = str(int(round(converted)))
            elif converted >= 10:
                converted_str = f"{converted:.1f}"
            else:
                converted_str = f"{converted:.2f}"
            # Prefix (< oder >) beibehalten
            prefix = ""
            if value_str.startswith("<"):
                prefix = "<"
            elif value_str.startswith(">"):
                prefix = ">"
            return prefix + converted_str, target_unit, unit
        except ValueError:
            return value_str, unit, unit

    # Einheit standardisieren (nur Schreibweise)
    unit_map = {
        "mg/dl": "mg/dL", "mmol/l": "mmol/L", "u/l": "U/L",
        "g/dl": "g/dL", "ng/ml": "ng/mL", "pg/ml": "pg/mL",
        "ml/min/kof": "mL/min", "ml/min": "mL/min",
        "10^9/l": "10^9/L", "10^12/l": "10^12/L",
    }
    std_unit = unit_map.get(unit_lower, unit)
    return value_str, std_unit, unit


def calculate_age_at_date(measurement_date: str) -> int | None:
    """Berechnet das Alter zum Messzeitpunkt."""
    try:
        d = datetime.strptime(measurement_date, "%Y-%m-%d").date()
        age = d.year - PATIENT_GEBURTSDATUM.year
        if (d.month, d.day) < (PATIENT_GEBURTSDATUM.month, PATIENT_GEBURTSDATUM.day):
            age -= 1
        return age
    except (ValueError, TypeError):
        return None


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


def main():
    all_results: list[dict] = []
    file_results: list[tuple[str, str, list[dict]]] = []  # (filename, format, results)

    txt_files = sorted(BEFUNDE_DIR.glob("*.txt")) + sorted(BEFUNDE_DIR.glob("*.csv"))
    # Output-Datei und Vorlage ausschließen
    txt_files = [f for f in txt_files if f.name not in ("laborwerte_gesamt.csv", "VORLAGE_laborbefund.csv")]

    if not txt_files:
        print(f"Keine .txt-Dateien gefunden in {BEFUNDE_DIR}")
        return

    for filepath in txt_files:
        fmt = detect_format(filepath)
        print(f"  {filepath.name} -> Format: {fmt}")

        # Nüchtern-Tag aus Datei erkennen (# nüchtern: nein/ja)
        file_text = filepath.read_text(encoding="utf-8", errors="replace")
        nuechtern = 1  # Default: ja/unbekannt
        nuechtern_match = re.search(r"#\s*nüchtern\s*:\s*(nein|ja|no|yes)", file_text, re.IGNORECASE)
        if nuechtern_match:
            nuechtern = 0 if nuechtern_match.group(1).lower() in ("nein", "no") else 1

        if fmt == "simple_csv":
            results = parse_simple_csv(filepath)
        elif fmt == "csv":
            results = parse_csv_format(filepath)
        elif fmt == "pivot":
            results = parse_pivot_format(filepath)
        elif fmt == "table":
            results = parse_table_format(filepath)
        elif fmt == "tab":
            results = parse_tab_format(filepath)
        elif fmt == "kuerzel_space":
            results = parse_kuerzel_space_format(filepath)
        elif fmt == "pdf_text":
            results = parse_pdf_text_format(filepath)
        else:
            results = parse_freetext_file(filepath)

        print(f"    -> {len(results)} Werte extrahiert")

        # Normalisierung direkt pro Datei (für DB-Import mit Quelldatei)
        for row in results:
            row["Test_Standard"] = normalize_test_name(row["Test"])
            row["Gruppe"] = classify_test(row["Test"])
            wert_norm, einheit_norm, _ = normalize_unit_and_value(
                row["Test_Standard"], row["Wert"], row["Einheit"]
            )
            row["Wert_Norm"] = wert_norm
            row["Einheit_Norm"] = einheit_norm

            # Korrektur: rel/abs Zuordnung anhand Einheit
            unit_lower = row["Einheit"].lower().strip()
            if row["Test_Standard"].endswith(" abs.") and unit_lower in ("%", "응"):
                row["Test_Standard"] = row["Test_Standard"].replace(" abs.", " rel.")
            elif row["Test_Standard"].endswith(" rel.") and unit_lower in ("g/l", "10^9/l", "10^9/L"):
                row["Test_Standard"] = row["Test_Standard"].replace(" rel.", " abs.")

            # Korrektur: Hämoglobin-Fehlzuordnungen anhand Einheit/Wert
            if row["Test_Standard"] == "Hämoglobin":
                if unit_lower == "pg":
                    row["Test_Standard"] = "MCH"
                elif not unit_lower:
                    try:
                        v = float(row["Wert_Norm"].replace("<", "").replace(">", ""))
                        if v > 20:
                            row["Test_Standard"] = "HbA1c (IFCC)"
                            row["Einheit_Norm"] = "mmol/mol"
                    except ValueError:
                        pass

            # Korrektur: HbA1c Werte >15 sind IFCC (mmol/mol), nicht NGSP (%)
            if row["Test_Standard"] == "HbA1c":
                try:
                    v = float(row["Wert_Norm"].replace("<", "").replace(">", ""))
                    if v > 15:
                        row["Test_Standard"] = "HbA1c (IFCC)"
                        row["Einheit_Norm"] = "mmol/mol"
                except ValueError:
                    pass

            age = calculate_age_at_date(row["Datum"])
            row["Alter"] = str(age) if age else ""

        # Ungültige Werte filtern (Parser-Artefakte)
        BLACKLIST = {"hans-peter", "spez. untersuchung", "arztbrief", "text blutbild", "letzte bearbeitung"}
        # Körperdaten werden aus hc_scale importiert, nicht aus Befunden
        KOERPERDATEN_BLACKLIST = {"gewicht", "fettgehalt", "fett", "bmi", "muskelmasse"}
        clean_results = []
        for row in results:
            # Testname-Blacklist
            if any(bl in row["Test_Standard"].lower() for bl in BLACKLIST):
                continue
            # Körperdaten aus Befunden überspringen (kommen aus hc_scale)
            if row["Test_Standard"].lower() in KOERPERDATEN_BLACKLIST:
                continue
            wert_clean = row["Wert_Norm"].replace("<", "").replace(">", "").strip()
            if not wert_clean:
                continue
            if wert_clean[0].isdigit() or wert_clean[0] == ".":
                try:
                    float(wert_clean)
                    clean_results.append(row)
                except ValueError:
                    pass
        results = clean_results

        # Flags berechnen/korrigieren anhand des Normbereichs
        # Auch vorhandene Flags werden neu geprüft (könnten durch Einheiten-Konvertierung falsch sein)
        fallback_norms = _config.get("fallback_normbereiche", {})
        for row in results:
            norm = row.get("Normbereich", "").strip()
            # Fallback-Norm verwenden wenn keine vorhanden
            if not norm or not any(c.isdigit() for c in norm):
                norm = fallback_norms.get(row.get("Test_Standard", ""), "")
                if norm:
                    row["Normbereich"] = norm
            wert_str = row.get("Wert_Norm", "").replace("<", "").replace(">", "").strip()
            if not norm or not wert_str:
                continue
            try:
                wert = float(wert_str)
            except ValueError:
                continue

            # Norm parsen: "4.00-11.00", "< 0.50", "> 90", "<-200", ">-90", "-50"
            import re as _re
            norm_lo, norm_hi = None, None
            # Range: "4.00-11.00" oder "136-145"
            m = _re.match(r"^([\d.]+)\s*-\s*([\d.]+)$", norm)
            if m:
                norm_lo, norm_hi = float(m.group(1)), float(m.group(2))

            # Korrektur: Hämatokrit Norm in L/L (0.41-0.53) → auf % konvertieren
            if row.get("Test_Standard") == "Hämatokrit" and norm_hi is not None and norm_hi < 1:
                norm_lo = norm_lo * 100 if norm_lo else None
                norm_hi = norm_hi * 100
                row["Normbereich"] = f"{norm_lo:.0f}-{norm_hi:.0f}" if norm_lo else f"<{norm_hi:.0f}"

            # Korrektur: Hämoglobin/MCHC Norm in g/L (>100) → auf g/dL konvertieren (÷10)
            if row.get("Test_Standard") in ("Hämoglobin", "MCHC") and norm_hi is not None and norm_hi > 50:
                norm_lo = norm_lo / 10 if norm_lo else None
                norm_hi = norm_hi / 10
                row["Normbereich"] = f"{norm_lo:.1f}-{norm_hi:.1f}" if norm_lo else f"<{norm_hi:.1f}"

            # Korrektur: Cholinesterase Norm in KU/l (<15) → auf U/L konvertieren (×1000)
            if row.get("Test_Standard") == "Cholinesterase" and norm_hi is not None and norm_hi < 20:
                norm_lo = norm_lo * 1000 if norm_lo else None
                norm_hi = norm_hi * 1000
                row["Normbereich"] = f"{norm_lo:.0f}-{norm_hi:.0f}" if norm_lo else f"<{norm_hi:.0f}"
            # Nur Obergrenze: "< 0.50" oder "<-200"
            m2 = _re.match(r"^[<]\s*-?\s*([\d.]+)$", norm)
            if m2:
                norm_hi = float(m2.group(1))
            # Nur Untergrenze: "> 90" oder ">-90"
            m3 = _re.match(r"^[>]\s*-?\s*([\d.]+)$", norm)
            if m3:
                norm_lo = float(m3.group(1))
            # Format "-50" (Obergrenze)
            m4 = _re.match(r"^-\s*([\d.]+)$", norm)
            if m4 and not m:
                norm_hi = float(m4.group(1))

            # Flag setzen (oder korrigieren wenn Norm konvertiert wurde)
            if norm_hi is not None and wert > norm_hi:
                row["Flag"] = "H"
            elif norm_lo is not None and wert < norm_lo:
                row["Flag"] = "L"
            else:
                # Wert ist im Normbereich → Flag entfernen (auch wenn Original-Befund eines hatte)
                row["Flag"] = ""

        file_results.append((filepath.name, fmt, results, nuechtern))
        all_results.extend(results)

    # ─── Berechnete Werte: Non-HDL-Cholesterin ──────────────────────────────────
    # Non-HDL = Cholesterin - HDL (wenn beide am selben Datum vorhanden, aber Non-HDL fehlt)
    from collections import defaultdict
    by_datum = defaultdict(dict)
    for row in all_results:
        by_datum[row["Datum"]][row["Test_Standard"]] = row

    non_hdl_added = 0
    chol_hdl_added = 0
    ldl_hdl_added = 0
    for datum, tests in by_datum.items():
        # Non-HDL-Cholesterin = Cholesterin - HDL
        if "Non-HDL-Cholesterin" not in tests and "Cholesterin" in tests and "HDL" in tests:
            try:
                chol_val = float(tests["Cholesterin"]["Wert_Norm"].replace("<", "").replace(">", ""))
                hdl_val = float(tests["HDL"]["Wert_Norm"].replace("<", "").replace(">", ""))
            except (ValueError, TypeError):
                pass
            else:
                non_hdl = round(chol_val - hdl_val, 1)
                flag = "H" if non_hdl >= 160 else ""
                age = tests["Cholesterin"].get("Alter", "")
                all_results.append({
                    "Datum": datum, "Alter": age, "Gruppe": "Lipide",
                    "Test_Standard": "Non-HDL-Cholesterin",
                    "Test": "Non-HDL-Cholesterin (berechnet)",
                    "Wert_Norm": str(non_hdl), "Einheit_Norm": "mg/dL",
                    "Wert": str(non_hdl), "Einheit": "mg/dL",
                    "Normbereich": "<160", "Flag": flag,
                })
                non_hdl_added += 1

        # Quotient Chol/HDL = Cholesterin / HDL
        if "Quotient Chol/HDL" not in tests and "Cholesterin" in tests and "HDL" in tests:
            try:
                chol_val = float(tests["Cholesterin"]["Wert_Norm"].replace("<", "").replace(">", ""))
                hdl_val = float(tests["HDL"]["Wert_Norm"].replace("<", "").replace(">", ""))
            except (ValueError, TypeError):
                pass
            else:
                if hdl_val > 0:
                    quot = round(chol_val / hdl_val, 1)
                    flag = "H" if quot > 5.0 else ""
                    age = tests["Cholesterin"].get("Alter", "")
                    all_results.append({
                        "Datum": datum, "Alter": age, "Gruppe": "Lipide",
                        "Test_Standard": "Quotient Chol/HDL",
                        "Test": "Quotient Chol/HDL (berechnet)",
                        "Wert_Norm": str(quot), "Einheit_Norm": "",
                        "Wert": str(quot), "Einheit": "",
                        "Normbereich": "0.0-5.0", "Flag": flag,
                    })
                    chol_hdl_added += 1

        # Quotient LDL/HDL = LDL / HDL
        if "Quotient LDL/HDL" not in tests and "LDL" in tests and "HDL" in tests:
            try:
                ldl_val = float(tests["LDL"]["Wert_Norm"].replace("<", "").replace(">", ""))
                hdl_val = float(tests["HDL"]["Wert_Norm"].replace("<", "").replace(">", ""))
            except (ValueError, TypeError):
                pass
            else:
                if hdl_val > 0:
                    quot = round(ldl_val / hdl_val, 1)
                    flag = "H" if quot > 3.0 else ""
                    age = tests["LDL"].get("Alter", "")
                    all_results.append({
                        "Datum": datum, "Alter": age, "Gruppe": "Lipide",
                        "Test_Standard": "Quotient LDL/HDL",
                        "Test": "Quotient LDL/HDL (berechnet)",
                        "Wert_Norm": str(quot), "Einheit_Norm": "",
                        "Wert": str(quot), "Einheit": "",
                        "Normbereich": "0.0-3.0", "Flag": flag,
                    })
                    ldl_hdl_added += 1

    berechnet_total = non_hdl_added + chol_hdl_added + ldl_hdl_added
    if berechnet_total:
        print(f"\n  📐 Berechnete Werte:")
        if non_hdl_added:
            print(f"    Non-HDL-Cholesterin: {non_hdl_added} (Cholesterin − HDL)")
        if chol_hdl_added:
            print(f"    Quotient Chol/HDL: {chol_hdl_added} (Cholesterin ÷ HDL)")
        if ldl_hdl_added:
            print(f"    Quotient LDL/HDL: {ldl_hdl_added} (LDL ÷ HDL)")

    # Nach Gruppe, Standard-Test und Datum sortieren
    all_results.sort(key=lambda x: (x["Gruppe"], x["Test_Standard"], x["Datum"]))

    # ─── CSV Export ─────────────────────────────────────────────────────────────
    fieldnames = [
        "Datum", "Alter", "Gruppe", "Test_Standard", "Test",
        "Wert_Norm", "Einheit_Norm", "Wert", "Einheit", "Normbereich", "Flag",
    ]
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(all_results)

    # ─── SQLite Import ──────────────────────────────────────────────────────────
    from labor_db import LaborDB

    with LaborDB() as db:
        patient_id = db.get_or_create_patient(
            vorname=_patient.get("vorname", ""),
            nachname=_patient.get("nachname", ""),
            geburtsdatum=PATIENT_GEBURTSDATUM,
            geschlecht=PATIENT_GESCHLECHT,
        )

        db_total = 0
        for filename, fmt, results, nuechtern_flag in file_results:
            # Labor aus Dateiformat/Name ableiten
            if fmt == "tab":
                labor = "Dr. Zünd, Lustenau"
            elif "laborbefund" in filename.lower():
                labor = "Krankenhaus"
            else:
                labor = ""

            count = db.import_results(
                results, quelldatei=filename, patient_id=patient_id, format=fmt, labor=labor, nuechtern=nuechtern_flag
            )
            db_total += count

        # Berechnete Werte (Non-HDL etc.) separat importieren
        berechnete = [r for r in all_results if "(berechnet)" in r.get("Test", "")]
        if berechnete:
            count = db.import_results(
                berechnete, quelldatei="berechnet", patient_id=patient_id, format="berechnet", labor="berechnet"
            )
            db_total += count

        stats = db.stats()
        print(f"\n  SQLite: {stats['laborwerte']} Werte in {db.db_path}")
        print(f"    Zeitraum: {stats['zeitraum']['von']} bis {stats['zeitraum']['bis']}")
        print(f"    Befunde: {stats['befunde']}, Patienten: {stats['patienten']}")

    # ─── Statistik ──────────────────────────────────────────────────────────────
    groups = {}
    for row in all_results:
        groups[row["Gruppe"]] = groups.get(row["Gruppe"], 0) + 1
    print("\n  Gruppen-Verteilung:")
    for group, count in sorted(groups.items()):
        print(f"    {group}: {count}")

    # Warnung: Tests die in "Sonstige" gelandet sind (fehlende Gruppen-Zuordnung)
    sonstige_tests = sorted(set(
        r["Test_Standard"] for r in all_results if r["Gruppe"] == "Sonstige"
    ))
    if sonstige_tests:
        print(f"\n  ⚠️  Ohne Gruppen-Zuordnung → 'Sonstige' ({len(sonstige_tests)} Tests):")
        for t in sonstige_tests:
            print(f"    - {t}")
        print("    → GROUP_RULES in extract_labvalues.py ergänzen um zuzuordnen")

    normalized = sum(1 for r in all_results if r["Test_Standard"] != r["Test"])
    converted = sum(1 for r in all_results if r["Wert_Norm"] != r["Wert"])
    print(f"\n  Normalisiert: {normalized} Testnamen, {converted} Einheiten-Konversionen")
    print(f"\n✓ {len(all_results)} Laborwerte in {OUTPUT_FILE} geschrieben")
    from labor_db import DB_PATH
    print(f"✓ SQLite-Datenbank: {DB_PATH}")


if __name__ == "__main__":
    main()
