# normalization/gruppen.py
"""
Mapping von Testnamen zu Gruppen.
Schlüssel sind lowercase-Substrings die im Testnamen gesucht werden.
Reihenfolge ist relevant: erste Übereinstimmung gewinnt.
"""

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
    ("β2-glycoprotein", "Autoimmun"),
    ("rheumafaktor", "Autoimmun"),
    ("ana ", "Autoimmun"),
    ("anca", "Autoimmun"),
    ("la-screen", "Autoimmun"),
    ("la-confirm", "Autoimmun"),
    ("lupus", "Autoimmun"),
    ("komplement", "Autoimmun"),
    ("ratio", "Gerinnung"),
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


def resolve_gruppe(test_name: str) -> str:
    """
    Find gruppe for a test name via substring matching.
    First match wins (order matters!).
    """
    if not test_name:
        return ""
    lower = test_name.lower()
    for substring, gruppe in GROUP_RULES:
        if substring in lower:
            return gruppe
    return ""
