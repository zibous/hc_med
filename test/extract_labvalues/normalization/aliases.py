# normalization/aliases.py
"""
Testnamen-Normalisierung und Einheiten-Konversion.
"""
import re

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
    "mono abs": "Monozyten abs.",
    "mono": "Monozyten abs.",
    "monozyten": "Monozyten rel.",
    "eosinophile %": "Eosinophile rel.",
    "eosinophile gr. abs.": "Eosinophile abs.",
    "eosinophile gr. rel.": "Eosinophile rel.",
    "eosinophile": "Eosinophile rel.",
    "eos.aut.": "Eosinophile rel.",
    "eos abs": "Eosinophile abs.",
    "eos": "Eosinophile abs.",
    "basophile %": "Basophile rel.",
    "basophile gr.abs.": "Basophile abs.",
    "basophile gr.rel.": "Basophile rel.",
    "baso.aut.": "Basophile rel.",
    "baso abs": "Basophile abs.",
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
    "alk. phosphatase": "Alk. Phosphatase",
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
    "gfr-ckd kreatinin/1.73 m2": "GFR",
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


# (Original-Einheit lowercase, Standard-Testname) -> (Ziel-Einheit, Umrechnungsfaktor)
UNIT_CONVERSIONS: dict[tuple[str, str], tuple[str, float]] = {
    # Hämoglobin: g/L -> g/dL (÷10)
    ("g/l_", "Hämoglobin"): ("g/dL", 0.1),
    ("g/l", "Hämoglobin"): ("g/dL", 0.1),
    ("g/dl", "Hämoglobin"): ("g/dL", 1.0),
    # MCHC: g/L -> g/dL (÷10)
    ("g/l_", "MCHC"): ("g/dL", 0.1),
    ("g/l", "MCHC"): ("g/dL", 0.1),
    ("g/dl", "MCHC"): ("g/dL", 1.0),
    # Hämatokrit: L/L -> % (×100) – nur wenn Wert < 1
    ("l/l", "Hämatokrit"): ("%", 100.0),
    ("/l", "Hämatokrit"): ("%", 100.0),
    # Cholinesterase: KU/l -> U/L (×1000)
    ("ku/l", "Cholinesterase"): ("U/L", 1000.0),
    # Leukozyten: verschiedene Schreibweisen -> 10^9/L
    ("g/l", "Leukozyten"): ("10^9/L", 1.0),
    ("10^9/l", "Leukozyten"): ("10^9/L", 1.0),
    ("103/µl", "Leukozyten"): ("103/µl", 1.0),
    # Erythrozyten: verschiedene Schreibweisen
    ("t/l", "Erythrozyten"): ("10^12/L", 1.0),
    ("10^12/l", "Erythrozyten"): ("10^12/L", 1.0),
    ("106/µl", "Erythrozyten"): ("106/µl", 1.0),
    # Thrombozyten
    ("g/l", "Thrombozyten"): ("10^9/L", 1.0),
    ("10^9/l", "Thrombozyten"): ("10^9/L", 1.0),
    ("103/µl", "Thrombozyten"): ("103/µl", 1.0),
    # MPV: g/dl ist falsch geparst aus Pivot -> fL
    ("g/dl", "MPV"): ("fL", 1.0),
    # CRP
    ("mg/dl", "CRP"): ("mg/dL", 1.0),
    # Cholinesterase: KU/l (verschiedene Schreibweisen)
    ("ku/l", "Cholinesterase"): ("KU/l", 1.0),
    # Case-Normalisierung: fl -> fL (SI-Standard)
    ("fl", "MCV"): ("fL", 1.0),
    ("fl", "MPV"): ("fL", 1.0),
    # G/l -> G/l (lowercase l)
    ("g/l", "Lymphozyten abs."): ("G/l", 1.0),
    ("g/l", "Neutrophile abs."): ("G/l", 1.0),
    ("g/l", "Monozyten abs."): ("G/l", 1.0),
    ("g/l", "Eosinophile abs."): ("G/l", 1.0),
    ("g/l", "Basophile abs."): ("G/l", 1.0),
    ("g/l", "Granulozyten abs."): ("G/l", 1.0),
    # 10^9/l -> 10^9/L (consistent casing)
    ("10^9/l", "Leukozyten"): ("10^9/L", 1.0),
    ("10^9/l", "Thrombozyten"): ("10^9/L", 1.0),
    ("10^9/l", "Neutrophile abs."): ("10^9/L", 1.0),
    ("10^9/l", "Lymphozyten abs."): ("10^9/L", 1.0),
    ("10^9/l", "Monozyten abs."): ("10^9/L", 1.0),
    ("10^9/l", "Eosinophile abs."): ("10^9/L", 1.0),
    ("10^9/l", "Basophile abs."): ("10^9/L", 1.0),
    ("10^9/l", "Granulozyten abs."): ("10^9/L", 1.0),
    ("10^9/l", "IG-Absolut"): ("10^9/L", 1.0),
    ("10^9/l", "NRBC-A"): ("10^9/L", 1.0),
    # 10^12/l -> 10^12/L
    ("10^12/l", "Erythrozyten"): ("10^12/L", 1.0),
    # mg/dl -> mg/dL
    ("mg/dl", "Kreatinin"): ("mg/dL", 1.0),
    ("mg/dl", "Harnstoff"): ("mg/dL", 1.0),
    ("mg/dl", "Harnsäure"): ("mg/dL", 1.0),
    ("mg/dl", "Glucose"): ("mg/dL", 1.0),
    ("mg/dl", "Cholesterin"): ("mg/dL", 1.0),
    ("mg/dl", "HDL"): ("mg/dL", 1.0),
    ("mg/dl", "LDL"): ("mg/dL", 1.0),
    ("mg/dl", "Non-HDL-Cholesterin"): ("mg/dL", 1.0),
    ("mg/dl", "Triglyceride"): ("mg/dL", 1.0),
    ("mg/dl", "Bilirubin"): ("mg/dL", 1.0),
    # mmol/l -> mmol/L
    ("mmol/l", "Natrium"): ("mmol/L", 1.0),
    ("mmol/l", "Kalium"): ("mmol/L", 1.0),
    ("mmol/l", "Chlorid"): ("mmol/L", 1.0),
    ("mmol/l", "Calcium"): ("mmol/L", 1.0),
    # U/l -> U/L
    ("u/l", "GOT"): ("U/L", 1.0),
    ("u/l", "GPT"): ("U/L", 1.0),
    ("u/l", "GGT"): ("U/L", 1.0),
    ("u/l", "LDH"): ("U/L", 1.0),
    ("u/l", "Alk. Phosphatase"): ("U/L", 1.0),
    ("u/l", "Cholinesterase"): ("U/L", 1.0),
    ("u/l", "Pankreas-Amylase"): ("U/L", 1.0),
    ("u/l", "Amylase"): ("U/L", 1.0),
    ("u/l", "Lipase"): ("U/L", 1.0),
    # ng/ml -> ng/mL
    ("ng/ml", "PSA"): ("ng/mL", 1.0),
    ("ng/ml", "Ferritin"): ("ng/mL", 1.0),
    # ug/dl -> ug/dl (keep as is)
    ("ug/dl", "Eisen"): ("ug/dl", 1.0),
    # pg/ml -> pg/mL
    ("pg/ml", "Calcitonin"): ("pg/mL", 1.0),
    ("pg/ml", "T3 Frei"): ("pg/mL", 1.0),
    ("pg/ml", "T4 Frei"): ("pg/mL", 1.0),
    ("pg/ml", "PTH"): ("pg/mL", 1.0),
    # µu/ml -> µU/mL (beibehalten)
    ("µu/ml", "TSH"): ("µU/mL", 1.0),
    ("miu/l", "TSH"): ("mIU/L", 1.0),
    # Sek. -> Sek.
    ("sek.", "aPTT"): ("Sek.", 1.0),
    ("sek", "aPTT"): ("Sek.", 1.0),
}


# Standard-Einheiten pro Test (Fallback wenn Einheit komplett leer)
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
    "Ferritin": "ng/mL",
    "Eisen": "ug/dl",
    "PSA": "ng/mL",
}


def resolve_test_standard(test_name: str) -> str:
    """Resolve a test name to its standard name via alias matching."""
    if not test_name:
        return ""
    lower = test_name.lower().strip()

    # Exact match first (longest key first for specificity)
    for alias, standard in sorted(TEST_ALIASES.items(), key=lambda x: -len(x[0])):
        if lower == alias:
            return standard

    # Partial match: strip parenthetical suffixes like "(RBC)", "(WBC)"
    # e.g. "Erythrozyten (RBC)" -> try "erythrozyten"
    stripped = re.sub(r"\s*\(.*?\)\s*$", "", lower).strip()
    if stripped != lower:
        for alias, standard in sorted(TEST_ALIASES.items(), key=lambda x: -len(x[0])):
            if stripped == alias:
                return standard

    # Fallback: return original
    return test_name


def normalize_unit(einheit: str, test_standard: str, wert: float | None) -> tuple[str, float | None]:
    """
    Normalize unit and convert value if needed.
    Returns (normalized_unit, converted_value).
    Only converts if there's an explicit conversion rule.
    """
    if not einheit:
        # No unit at all: use standard if defined
        if test_standard in STANDARD_UNITS:
            return STANDARD_UNITS[test_standard], wert
        return "", wert

    unit_lower = einheit.lower().strip()
    key = (unit_lower, test_standard)

    if key in UNIT_CONVERSIONS:
        target_unit, factor = UNIT_CONVERSIONS[key]
        if wert is not None and factor != 1.0:
            # Special case: Hämatokrit L/L -> % only if value < 1
            if test_standard == "Hämatokrit" and factor == 100.0 and wert >= 1:
                return einheit, wert
            wert = round(wert * factor, 2)
        return target_unit, wert

    # No conversion rule: keep original unit
    return einheit, wert
