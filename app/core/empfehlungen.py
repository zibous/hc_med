"""Empfehlungslogik für Laborwerte und Verknüpfungen."""

import sqlite3
from datetime import datetime
from pathlib import Path

import yaml

from app.config.settings import EMPFEHLUNGEN_TESTS

# ─── Text-Templates aus YAML laden ───────────────────────────────────────────
_TEXTE_PATH = (
    Path(__file__).resolve().parent.parent.parent / "data" / "empfehlungen_texte.yaml"
)
with open(_TEXTE_PATH, "r", encoding="utf-8") as _f:
    TEXTE = yaml.safe_load(_f)


def _t(kategorie: str, key: str, **kwargs) -> str:
    """Holt ein Text-Template und füllt Platzhalter."""
    template = TEXTE.get(kategorie, {}).get(key, "")
    if not template:
        return ""
    try:
        return template.format(**kwargs)
    except (KeyError, ValueError):
        return template


# ═══════════════════════════════════════════════════════════════════════════════
# Trend-Empfehlung (einzelner Test)
# ═══════════════════════════════════════════════════════════════════════════════


def get_test_empfehlung(
    test: str, last_val: str, last_flag: str, norm: str, conn: sqlite3.Connection
) -> str:
    """Generiert eine test-spezifische Empfehlung für die Trend-Ansicht."""
    if not last_flag:
        return ""

    try:
        val = float(str(last_val).replace(",", ".").replace("<", "").replace(">", ""))
    except (ValueError, TypeError):
        return ""

    emp_config = EMPFEHLUNGEN_TESTS.get(test, {})
    static_text = emp_config.get("text", "")
    is_dynamic = emp_config.get("dynamisch", False)

    bedingung = emp_config.get("bedingung", "")
    if bedingung == "erhöht" and last_flag != "H":
        return ""
    if bedingung == "erniedrigt" and last_flag != "L":
        return ""

    dynamic_text = ""
    if is_dynamic and test == "Cholesterin":
        dynamic_text = _cholesterin_dynamic(val, conn)

    parts = []
    if dynamic_text:
        parts.append(dynamic_text)
    if static_text:
        parts.append(static_text)
    return " ".join(parts)


def _cholesterin_dynamic(val: float, conn: sqlite3.Connection) -> str:
    """Berechnet die Cholesterin-Aufschlüsselung dynamisch."""
    hdl_row = conn.execute(
        "SELECT wert_norm FROM laborwerte WHERE test_standard='HDL' ORDER BY datum DESC LIMIT 1"
    ).fetchone()
    ldl_row = conn.execute(
        "SELECT wert_norm FROM laborwerte WHERE test_standard='LDL' ORDER BY datum DESC LIMIT 1"
    ).fetchone()
    trig_row = conn.execute(
        "SELECT wert_norm FROM laborwerte WHERE test_standard='Triglyceride' ORDER BY datum DESC LIMIT 1"
    ).fetchone()

    if not (hdl_row and ldl_row and trig_row):
        return ""

    hdl = float(str(hdl_row[0]).replace(",", "."))
    ldl = float(str(ldl_row[0]).replace(",", "."))
    trig = float(str(trig_row[0]).replace(",", "."))
    berechnet = hdl + ldl + (trig / 5)

    text = _t(
        "cholesterin",
        "formel",
        hdl=hdl,
        ldl=ldl,
        trig=trig,
        trig5=trig / 5,
        berechnet=berechnet,
        chol=val,
    )
    if trig > 200 and ldl < 150:
        text += " " + _t("cholesterin", "trig_haupttreiber", trig=trig, ldl=ldl)
        text += " " + _t("cholesterin", "trig_massnahmen")
    return text


# ═══════════════════════════════════════════════════════════════════════════════
# Verknüpfungs-Empfehlungen
# ═══════════════════════════════════════════════════════════════════════════════


def generate_verknuepfung_empfehlung(name: str, tests: dict) -> str:
    """Generiert eine detaillierte Empfehlung für Verknüpfungs-Ansicht."""

    def get_latest(test_name):
        if test_name not in tests:
            return None, None
        werte = tests[test_name]["werte"]
        if not werte:
            return None, None
        last = werte[-1]
        try:
            return float(
                str(last["wert"]).replace(",", ".").replace("<", "").replace(">", "")
            ), last.get("flag", "")
        except (ValueError, TypeError):
            return None, None

    def get_series(test_name):
        """Gibt Liste von (datum, wert) Tupeln zurück."""
        if test_name not in tests:
            return []
        result = []
        for w in tests[test_name]["werte"]:
            try:
                val = float(
                    str(w["wert"]).replace(",", ".").replace("<", "").replace(">", "")
                )
                result.append((w["datum"], val))
            except (ValueError, TypeError):
                continue
        return result

    empfehlungen = []

    if name == "Gewicht & Stoffwechsel":
        empfehlungen = _empfehlung_gewicht(get_latest, get_series)
    elif name == "Bauchfett & Entzündung":
        empfehlungen = _empfehlung_bauchfett(get_latest)
    elif name == "Muskeln & Nierenwerte":
        empfehlungen = _empfehlung_muskeln_niere(get_latest)
    elif name == "Körperfett & Blutfette":
        empfehlungen = _empfehlung_koerperfett(get_latest)
    elif name == "Nierenfunktion":
        empfehlungen = _empfehlung_niere(get_latest)
    elif name == "Entzündungs-Kaskade":
        empfehlungen = _empfehlung_entzuendung(get_latest)
    elif name == "Lipid-Profil":
        empfehlungen = _empfehlung_lipid(get_latest)
    elif name == "Cholesterin-Aufschlüsselung":
        empfehlungen = _empfehlung_cholesterin(get_latest)
    elif name == "Gefäßgesundheit":
        empfehlungen = _empfehlung_gefaesse(get_latest)
    elif name == "Stoffwechsel-Risiko":
        empfehlungen = _empfehlung_stoffwechsel(get_latest)

    if not empfehlungen:
        empfehlungen = [_t("default", "keine_auffaelligkeiten")]

    return " · ".join(empfehlungen)


# ═══════════════════════════════════════════════════════════════════════════════
# Einzelne Verknüpfungs-Funktionen
# ═══════════════════════════════════════════════════════════════════════════════


def _empfehlung_gewicht(get_latest, get_series=None):
    e = []
    bmi, _ = get_latest("BMI")
    glucose, _ = get_latest("Glucose")
    hba1c, _ = get_latest("HbA1c")
    trig, _ = get_latest("Triglyceride")

    if bmi and bmi > 25:
        e.append(_t("gewicht", "bmi_hoch", bmi=bmi, kg=(bmi - 23) * 1.8))
    elif bmi:
        e.append(_t("gewicht", "bmi_ok", bmi=bmi))
    if glucose and glucose > 100:
        e.append(_t("gewicht", "glucose_hoch", val=glucose))
    if hba1c and hba1c > 5.7:
        e.append(_t("gewicht", "hba1c_hoch", val=hba1c))
    if trig and trig > 200:
        e.append(_t("gewicht", "trig_hoch", val=trig))

    # Korrelationsanalyse
    if get_series:
        korrelationen = _analyse_gewicht_korrelation(get_series)
        if korrelationen:
            e.extend(korrelationen)

    return e or [_t("gewicht", "alles_ok")]


def _empfehlung_bauchfett(get_latest):
    e = []
    vf, _ = get_latest("Viszeralfett")
    crp, _ = get_latest("CRP")
    if vf and vf > 12:
        e.append(_t("bauchfett", "vf_hoch", val=vf))
        if crp and crp > 0.5:
            e.append(_t("bauchfett", "vf_hoch_crp", crp=crp))
    elif vf:
        e.append(_t("bauchfett", "vf_ok", val=vf))
        if crp and crp > 0.5:
            e.append(_t("bauchfett", "vf_ok_crp", crp=crp))
    return e


def _empfehlung_muskeln_niere(get_latest):
    e = []
    muskel, _ = get_latest("Muskelmasse")
    krea, _ = get_latest("Kreatinin")
    gfr, _ = get_latest("GFR")
    if gfr and gfr < 60:
        e.append(_t("muskeln_niere", "gfr_niedrig", val=gfr))
    elif gfr and gfr < 90:
        e.append(_t("muskeln_niere", "gfr_leicht", val=gfr))
    if muskel and krea:
        e.append(_t("muskeln_niere", "muskel_krea", muskel=muskel, krea=krea))
    return e


def _empfehlung_koerperfett(get_latest):
    e = []
    fett, _ = get_latest("Fettgehalt")
    hdl, _ = get_latest("HDL")
    ldl, _ = get_latest("LDL")
    if fett and fett < 20:
        e.append(_t("koerperfett", "fett_gut", val=fett))
    if hdl and hdl >= 60:
        e.append(_t("koerperfett", "hdl_optimal", val=hdl))
    elif hdl and hdl < 40:
        e.append(_t("koerperfett", "hdl_niedrig", val=hdl))
    if ldl and ldl > 150:
        e.append(_t("koerperfett", "ldl_hoch", val=ldl))
    return e


def _empfehlung_niere(get_latest):
    e = []
    gfr, _ = get_latest("GFR")
    krea, _ = get_latest("Kreatinin")
    if gfr and gfr < 60:
        e.append(_t("niere", "gfr_stadium3", val=gfr))
    elif gfr and gfr < 90:
        e.append(_t("niere", "gfr_leicht", val=gfr))
    if krea and krea > 1.2:
        e.append(_t("niere", "krea_hoch", val=krea))
    return e


def _empfehlung_entzuendung(get_latest):
    e = []
    crp, _ = get_latest("CRP")
    leuko, _ = get_latest("Leukozyten")
    if crp and crp > 5:
        e.append(_t("entzuendung", "crp_stark", val=crp))
    elif crp and crp > 0.5:
        e.append(_t("entzuendung", "crp_leicht", val=crp))
    if leuko and leuko > 11:
        e.append(_t("entzuendung", "leuko_hoch", val=leuko))
    return e


def _empfehlung_lipid(get_latest):
    e = []
    chol, _ = get_latest("Cholesterin")
    hdl, _ = get_latest("HDL")
    ldl, _ = get_latest("LDL")
    trig, _ = get_latest("Triglyceride")
    if chol and chol > 200:
        e.append(_t("lipid", "chol_hoch", val=chol))
    if ldl and hdl:
        ratio = ldl / hdl
        if ratio > 3:
            e.append(_t("lipid", "ratio_schlecht", ratio=ratio))
        else:
            e.append(_t("lipid", "ratio_gut", ratio=ratio))
    if trig and trig > 200:
        e.append(_t("lipid", "trig_hoch", val=trig))
    return e


def _empfehlung_cholesterin(get_latest):
    e = []
    chol, _ = get_latest("Cholesterin")
    hdl, _ = get_latest("HDL")
    ldl, _ = get_latest("LDL")
    trig, _ = get_latest("Triglyceride")

    if chol and hdl and ldl and trig:
        berechnet = hdl + ldl + (trig / 5)
        e.append(
            _t(
                "cholesterin",
                "formel",
                hdl=hdl,
                ldl=ldl,
                trig=trig,
                trig5=trig / 5,
                berechnet=berechnet,
                chol=chol,
            )
        )
    if trig and trig > 200 and ldl and ldl < 150:
        e.append(_t("cholesterin", "trig_haupttreiber", trig=trig, ldl=ldl))
        e.append(_t("cholesterin", "trig_massnahmen"))
    elif trig and trig > 200:
        e.append(_t("cholesterin", "trig_hoch", val=trig))
    if hdl and hdl >= 55:
        e.append(_t("cholesterin", "hdl_gut", val=hdl))
    if ldl and ldl < 130:
        e.append(_t("cholesterin", "ldl_ok", val=ldl))
    return e


def _empfehlung_gefaesse(get_latest):
    e = []
    ldl, _ = get_latest("LDL")
    hdl, _ = get_latest("HDL")
    trig, _ = get_latest("Triglyceride")
    crp, _ = get_latest("CRP")
    hba1c, _ = get_latest("HbA1c")
    hs, _ = get_latest("Harnsäure")

    # Risiko-Score
    risiko = 0
    if trig and trig > 200:
        risiko += 2
    if crp and crp > 0.5:
        risiko += 2
    if hba1c and hba1c > 5.7:
        risiko += 1
    if ldl and ldl > 130:
        risiko += 1
    if hs and hs > 7.0:
        risiko += 1
    if hdl and hdl < 40:
        risiko += 1

    if risiko < 3:
        e.append(_t("gefaesse", "risiko_gering", score=risiko))

    # Spezifische Empfehlungen
    if trig and trig > 200:
        e.append(_t("gefaesse", "prio1_trig", val=trig))
    if crp and crp > 1.0:
        e.append(_t("gefaesse", "prio2_crp", val=crp))
    if hba1c and hba1c > 5.7:
        e.append(_t("gefaesse", "prio3_hba1c", val=hba1c))
    if ldl and ldl > 130:
        e.append(_t("gefaesse", "ldl_hoch", val=ldl))
    if hdl and hdl >= 55:
        e.append(_t("gefaesse", "hdl_gut", val=hdl))
    if hs and hs > 7.0:
        e.append(_t("gefaesse", "hs_hoch", val=hs))

    e.append(_t("gefaesse", "allgemein"))
    return e


def _empfehlung_stoffwechsel(get_latest):
    e = []
    hba1c, _ = get_latest("HbA1c")
    glucose, _ = get_latest("Glucose")
    trig, _ = get_latest("Triglyceride")
    hs, _ = get_latest("Harnsäure")
    ggt, _ = get_latest("GGT")
    gpt, _ = get_latest("GPT")
    got, _ = get_latest("GOT")

    # Diabetes
    if hba1c and hba1c > 6.0:
        e.append(_t("stoffwechsel", "hba1c_diabetes", val=hba1c))
    elif hba1c and hba1c > 5.7:
        e.append(_t("stoffwechsel", "hba1c_praediabetes", val=hba1c))

    if glucose and glucose > 126:
        e.append(_t("stoffwechsel", "glucose_diabetes", val=glucose))
    elif glucose and glucose > 100:
        e.append(_t("stoffwechsel", "glucose_praediabetes", val=glucose))

    # Triglyceride
    if trig and trig > 200:
        e.append(_t("stoffwechsel", "trig_deutlich", val=trig))
    elif trig and trig > 150:
        e.append(_t("stoffwechsel", "trig_leicht", val=trig))

    # Harnsäure
    if hs and hs > 8.0:
        e.append(_t("stoffwechsel", "hs_gicht", val=hs))
    elif hs and hs > 7.0:
        e.append(_t("stoffwechsel", "hs_grenzwert", val=hs))

    # Leber
    leber_auffaellig = []
    if ggt and ggt > 60:
        leber_auffaellig.append(f"GGT {ggt:.0f}")
    if gpt and gpt > 50:
        leber_auffaellig.append(f"GPT {gpt:.0f}")
    if got and got > 50:
        leber_auffaellig.append(f"GOT {got:.0f}")
    if leber_auffaellig:
        e.append(_t("stoffwechsel", "leber_hoch", details=", ".join(leber_auffaellig)))

    # Metabolisches Syndrom
    risiken = sum(
        [
            bool(hba1c and hba1c > 5.7),
            bool(trig and trig > 150),
            bool(hs and hs > 7.0),
            bool(ggt and ggt > 60),
        ]
    )
    if risiken >= 3:
        e.append(_t("stoffwechsel", "metabolisch"))

    if not e:
        e.append(_t("stoffwechsel", "alles_ok"))

    return e


# ═══════════════════════════════════════════════════════════════════════════════
# Korrelationsanalyse
# ═══════════════════════════════════════════════════════════════════════════════


def _analyse_gewicht_korrelation(get_series) -> list[str]:
    """Prüft ob Gewichtsänderungen mit Laborwert-Änderungen korrelieren."""
    gewicht_series = get_series("Gewicht")
    if len(gewicht_series) < 3:
        return []

    korrelationen = []
    labor_tests = [
        ("Triglyceride", "Blutfette"),
        ("HbA1c", "Langzeit-Blutzucker"),
        ("Glucose", "Nüchtern-Blutzucker"),
    ]

    for test_name, label in labor_tests:
        labor_series = get_series(test_name)
        if len(labor_series) < 3:
            continue

        pairs = _match_series(gewicht_series, labor_series, max_days=60)
        if len(pairs) < 3:
            continue

        corr = _simple_correlation(pairs)
        if corr is None:
            continue

        if corr > 0.6:
            korrelationen.append(
                _t(
                    "gewicht",
                    "korrelation_positiv",
                    label=label,
                    corr=corr,
                    test=test_name,
                )
            )
        elif corr < -0.6:
            korrelationen.append(
                _t("gewicht", "korrelation_negativ", label=label, corr=corr)
            )

    return korrelationen


def _match_series(series_a, series_b, max_days=60) -> list[tuple]:
    """Findet Wertepaare mit ähnlichem Datum (±max_days)."""
    pairs = []
    for datum_a, val_a in series_a:
        best_diff = None
        best_val_b = None
        try:
            date_a = datetime.strptime(datum_a, "%Y-%m-%d")
        except ValueError:
            continue
        for datum_b, val_b in series_b:
            try:
                date_b = datetime.strptime(datum_b, "%Y-%m-%d")
            except ValueError:
                continue
            diff = abs((date_a - date_b).days)
            if diff <= max_days and (best_diff is None or diff < best_diff):
                best_diff = diff
                best_val_b = val_b
        if best_val_b is not None:
            pairs.append((val_a, best_val_b))
    return pairs


def _simple_correlation(pairs: list[tuple]):
    """Berechnet Pearson-Korrelation für Wertepaare."""
    n = len(pairs)
    if n < 3:
        return None

    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]

    mean_x = sum(xs) / n
    mean_y = sum(ys) / n

    num = sum((x - mean_x) * (y - mean_y) for x, y in pairs)
    den_x = sum((x - mean_x) ** 2 for x in xs) ** 0.5
    den_y = sum((y - mean_y) ** 2 for y in ys) ** 0.5

    if den_x == 0 or den_y == 0:
        return None

    return num / (den_x * den_y)
