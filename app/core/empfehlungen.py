"""Empfehlungslogik für Laborwerte und Verknüpfungen."""

import sqlite3

from app.config.settings import EMPFEHLUNGEN_TESTS


def get_test_empfehlung(test: str, last_val: str, last_flag: str, norm: str, conn: sqlite3.Connection) -> str:
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

    text = f"Aktuell: HDL {hdl:.0f} + LDL {ldl:.0f} + Trig÷5 ({trig:.0f}÷5={trig/5:.0f}) = {berechnet:.0f} mg/dL (gemessen: {val:.0f}). "
    if trig > 200 and ldl < 150:
        text += f"Haupttreiber des hohen Gesamtwerts sind die Triglyceride ({trig:.0f}), LDL ({ldl:.0f}) ist OK. Triglyceride separat behandeln. "
    return text


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
            return float(str(last["wert"]).replace(",", ".").replace("<", "").replace(">", "")), last.get("flag", "")
        except (ValueError, TypeError):
            return None, None

    empfehlungen = []

    if name == "Gewicht & Stoffwechsel":
        empfehlungen = _empfehlung_gewicht(get_latest)
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

    if not empfehlungen:
        empfehlungen = ["Keine spezifischen Auffälligkeiten in dieser Kombination."]

    return " · ".join(empfehlungen)


def _empfehlung_gewicht(get_latest):
    e = []
    bmi, _ = get_latest("BMI")
    glucose, _ = get_latest("Glucose")
    hba1c, _ = get_latest("HbA1c")
    trig, _ = get_latest("Triglyceride")

    if bmi and bmi > 25:
        e.append(f"BMI {bmi:.1f} liegt über Normalbereich. Gewichtsreduktion um {((bmi-23)*1.8):.0f} kg würde normalisieren.")
    elif bmi:
        e.append(f"BMI {bmi:.1f} ist im Normalbereich – sehr gut.")
    if glucose and glucose > 100:
        e.append(f"Glucose {glucose:.0f} mg/dL grenzwertig. Weniger Zucker/Weißmehl, Bewegung nach Mahlzeiten.")
    if hba1c and hba1c > 5.7:
        e.append(f"HbA1c {hba1c:.1f}% zeigt beginnende Zuckerstoffwechselstörung. Kontrolle empfohlen.")
    if trig and trig > 200:
        e.append(f"Triglyceride {trig:.0f} mg/dL deutlich erhöht. Weniger Alkohol, Zucker, gesättigte Fette.")
    return e or ["Alle Werte im Zusammenspiel unauffällig – weiter so!"]


def _empfehlung_bauchfett(get_latest):
    e = []
    vf, _ = get_latest("Viszeralfett")
    crp, _ = get_latest("CRP")
    if vf and vf > 12:
        e.append(f"Viszeralfett Level {vf:.0f} erhöht. Ausdauersport und Intervallfasten helfen.")
    elif vf:
        e.append(f"Viszeralfett Level {vf:.1f} im guten Bereich.")
    if crp and crp > 0.5:
        e.append(f"CRP {crp:.2f} mg/dL deutet auf Entzündung. Zusammenhang mit Bauchfett prüfen.")
    return e


def _empfehlung_muskeln_niere(get_latest):
    e = []
    muskel, _ = get_latest("Muskelmasse")
    krea, _ = get_latest("Kreatinin")
    gfr, _ = get_latest("GFR")
    if gfr and gfr < 60:
        e.append(f"GFR {gfr:.0f} mL/min eingeschränkt. Nephrologische Kontrolle empfohlen.")
    elif gfr and gfr < 90:
        e.append(f"GFR {gfr:.0f} mL/min leicht reduziert – bei Alter 70 akzeptabel, regelmäßig kontrollieren.")
    if muskel and krea:
        e.append(f"Bei {muskel:.0f}% Muskelmasse ist Kreatinin {krea:.2f} plausibel. GFR-Formel kann unterschätzen.")
    return e


def _empfehlung_koerperfett(get_latest):
    e = []
    fett, _ = get_latest("Fettgehalt")
    hdl, _ = get_latest("HDL")
    ldl, _ = get_latest("LDL")
    if fett and fett < 20:
        e.append(f"Körperfett {fett:.1f}% gut für das Alter. Unterstützt gute Blutfettwerte.")
    if hdl and hdl >= 60:
        e.append(f"HDL {hdl:.0f} mg/dL optimal – schützt die Gefäße.")
    elif hdl and hdl < 40:
        e.append(f"HDL {hdl:.0f} zu niedrig. Mehr Bewegung und ungesättigte Fette.")
    if ldl and ldl > 150:
        e.append(f"LDL {ldl:.0f} erhöht. Weniger gesättigte Fette, mehr Ballaststoffe.")
    return e


def _empfehlung_niere(get_latest):
    e = []
    gfr, _ = get_latest("GFR")
    krea, _ = get_latest("Kreatinin")
    if gfr and gfr < 60:
        e.append(f"GFR {gfr:.0f}: Stadium 3. Eiweiß begrenzen, viel trinken, regelmäßige Kontrolle.")
    elif gfr and gfr < 90:
        e.append(f"GFR {gfr:.0f}: Leichte Einschränkung, alterstypisch. 2L/Tag trinken, Blutdruck kontrollieren.")
    if krea and krea > 1.2:
        e.append(f"Kreatinin {krea:.2f} leicht erhöht – mit GFR zusammen betrachten.")
    return e


def _empfehlung_entzuendung(get_latest):
    e = []
    crp, _ = get_latest("CRP")
    leuko, _ = get_latest("Leukozyten")
    if crp and crp > 5:
        e.append(f"CRP {crp:.1f} stark erhöht – akuter Infekt/Gewebeschaden wahrscheinlich.")
    elif crp and crp > 0.5:
        e.append(f"CRP {crp:.2f} leicht erhöht. Mögliche Ursachen: Entzündung, Übergewicht, Stress.")
    if leuko and leuko > 11:
        e.append(f"Leukozyten {leuko:.1f} erhöht. Bei anhaltender Erhöhung ohne Infekt: abklären.")
    return e


def _empfehlung_lipid(get_latest):
    e = []
    chol, _ = get_latest("Cholesterin")
    hdl, _ = get_latest("HDL")
    ldl, _ = get_latest("LDL")
    trig, _ = get_latest("Triglyceride")
    if chol and chol > 200:
        e.append(f"Gesamt-Cholesterin {chol:.0f} über Zielwert. LDL/HDL-Verhältnis entscheidend.")
    if ldl and hdl:
        ratio = ldl / hdl
        if ratio > 3:
            e.append(f"LDL/HDL {ratio:.1f} ungünstig (Ziel <3). Bewegung und pflanzliche Ernährung.")
        else:
            e.append(f"LDL/HDL {ratio:.1f} ist gut.")
    if trig and trig > 200:
        e.append(f"Triglyceride {trig:.0f} erhöht. Weniger Zucker, Alkohol, raffinierte KH.")
    return e


def _empfehlung_cholesterin(get_latest):
    e = []
    chol, _ = get_latest("Cholesterin")
    hdl, _ = get_latest("HDL")
    ldl, _ = get_latest("LDL")
    trig, _ = get_latest("Triglyceride")

    if chol and hdl and ldl and trig:
        berechnet = hdl + ldl + (trig / 5)
        e.append(f"Formel: HDL ({hdl:.0f}) + LDL ({ldl:.0f}) + Trig÷5 ({trig:.0f}÷5={trig/5:.0f}) = {berechnet:.0f} (gemessen: {chol:.0f}).")
    if trig and trig > 200 and ldl and ldl < 150:
        e.append(f"Triglyceride ({trig:.0f}) sind Haupttreiber – NICHT LDL ({ldl:.0f}).")
        e.append("Maßnahmen: Alkohol meiden, Zucker/Weißmehl einschränken, Omega-3 (2g/Tag), Bewegung.")
    elif trig and trig > 200:
        e.append(f"Triglyceride {trig:.0f} deutlich erhöht.")
    if hdl and hdl >= 55:
        e.append(f"HDL {hdl:.0f} gut (schützt Gefäße).")
    if ldl and ldl < 130:
        e.append(f"LDL {ldl:.0f} im Zielbereich.")
    return e


def _empfehlung_gefaesse(get_latest):
    e = []
    ldl, _ = get_latest("LDL")
    hdl, _ = get_latest("HDL")
    trig, _ = get_latest("Triglyceride")
    crp, _ = get_latest("CRP")
    hba1c, _ = get_latest("HbA1c")
    hs, _ = get_latest("Harnsäure")

    # Risiko-Score (vereinfacht)
    risiko = 0
    if trig and trig > 200: risiko += 2
    if crp and crp > 0.5: risiko += 2
    if hba1c and hba1c > 5.7: risiko += 1
    if ldl and ldl > 130: risiko += 1
    if hs and hs > 7.0: risiko += 1
    if hdl and hdl < 40: risiko += 1

    if risiko >= 5:
        pass  # Score-Anzeige erfolgt über die Score-Card im Frontend
    elif risiko >= 3:
        pass  # Score-Anzeige erfolgt über die Score-Card im Frontend
    else:
        e.append(f"Geringes Gefäßrisiko (Score {risiko}/8) – gut!")

    # Spezifische Empfehlungen
    if trig and trig > 200:
        e.append(f"PRIORITÄT 1: Triglyceride ({trig:.0f}) senken – Zucker/Alkohol meiden, Omega-3, Bewegung. Effekt in 4-8 Wochen messbar.")
    if crp and crp > 1.0:
        e.append(f"PRIORITÄT 2: Entzündung (CRP {crp:.1f}) reduzieren – destabilisiert bestehende Plaques. Ursache suchen.")
    if hba1c and hba1c > 5.7:
        e.append(f"PRIORITÄT 3: Blutzucker (HbA1c {hba1c:.1f}%) schädigt Gefäßinnenwand. Zucker/Weißmehl reduzieren, nach Essen bewegen.")
    if ldl and ldl > 130:
        e.append(f"LDL {ldl:.0f} leicht über Zielwert 130. Bei zusätzlichen Risikofaktoren mit Arzt über Therapie sprechen.")
    if hdl and hdl >= 55:
        e.append(f"HDL {hdl:.0f} ist gut – schützt die Gefäße aktiv. Weiter mit Bewegung und ungesättigten Fetten.")
    if hs and hs > 7.0:
        e.append(f"Harnsäure {hs:.1f} leicht erhöht – fördert Gefäßentzündung. Viel trinken, weniger Fleisch.")

    e.append("Allgemein: 30min Bewegung/Tag (Gehen reicht), mediterrane Ernährung, Nichtrauchen, Blutdruck <135/85.")
    return e
