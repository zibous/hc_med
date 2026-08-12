TEST_ALIASES = {
    "leukocyten": "Leukozyten",
    "leuko": "Leukozyten",
    "ery": "Erythrozyten",
    "hgb": "Hämoglobin",
    "hb": "Hämoglobin",
    "crp": "CRP",
    "kreatinin": "Kreatinin",
    "natrium": "Natrium",
    "kalium": "Kalium",
    "gfr-ckd": "GFR",
    # … hier kommen alle deine Aliase rein …
}


def normalize_testname(name: str) -> str:
    key = name.lower().strip()
    return TEST_ALIASES.get(key, name)
