"""Bewertungslogik für Gruppen und Trends."""

from app.config.settings import _config

_bewertungen = _config.get("bewertungen", {})
_gruppe_texte = _bewertungen.get("gruppe", {})
_trend_texte = _bewertungen.get("trend", {})


def bewerte_gruppe(ok_count: int, path_count: int, total: int) -> tuple[str, str]:
    """Bewertet eine Gruppe anhand des Anteils pathologischer Werte.

    Returns: (bewertung_text, bewertung_status)
    """
    ratio = path_count / total if total > 0 else 0

    if ratio == 0:
        return _gruppe_texte.get("gut", ""), "gut"
    elif ratio < 0.1:
        return _gruppe_texte.get("gut_leicht", ""), "gut"
    elif ratio < 0.25:
        return _gruppe_texte.get("ok", ""), "ok"
    elif ratio < 0.4:
        return _gruppe_texte.get("auffällig", ""), "auffällig"
    else:
        return _gruppe_texte.get("kritisch", ""), "kritisch"


def bewerte_trend(rows: list, recent_count: int = 5) -> tuple[str, str]:
    """Bewertet einen einzelnen Test anhand der letzten Werte.

    Primär am letzten Wert orientiert, mit Kontext der letzten Messungen.
    Returns: (bewertung_text, bewertung_status)
    """
    if not rows:
        return "", "gut"

    last_val = rows[-1]["wert_norm"]
    last_flag = rows[-1]["flag"]
    einheit = rows[-1]["einheit_norm"] or ""

    flag_text = ""
    if last_flag == "H":
        flag_text = " (erhöht)"
    elif last_flag == "L":
        flag_text = " (erniedrigt)"

    # Normbereich suchen
    norm = ""
    for r in rows:
        nb = (r.get("normbereich") or "").strip()
        if nb and any(c.isdigit() for c in nb):
            norm = nb
            break

    # Status primär am letzten Wert
    if not last_flag:
        # Letzter Wert OK – prüfe ob letzte 3 auch OK
        recent3 = rows[-3:] if len(rows) >= 3 else rows
        r3_path = sum(1 for r in recent3 if r["flag"] in ("H", "L"))
        if r3_path == 0:
            status = "gut"
        else:
            status = "gut"  # Letzter OK, tendenz besser
        text = _trend_texte.get("gut", "").format(wert=last_val, einheit=einheit, flag_text=flag_text, norm=norm)
    else:
        # Letzter Wert auffällig – prüfe Schwere
        recent3 = rows[-3:] if len(rows) >= 3 else rows
        r3_path = sum(1 for r in recent3 if r["flag"] in ("H", "L"))
        if r3_path >= 3:
            status = "kritisch"
            text = _trend_texte.get("kritisch", "").format(wert=last_val, einheit=einheit, flag_text=flag_text, norm=norm)
        else:
            status = "auffällig"
            text = _trend_texte.get("auffällig", "").format(wert=last_val, einheit=einheit, flag_text=flag_text, norm=norm)

    # Historischer Kontext
    all_path = sum(1 for r in rows if r["flag"] in ("H", "L"))
    if all_path > 0 and not last_flag:
        hist_tmpl = _trend_texte.get("historisch", "")
        text += " " + hist_tmpl.format(count=all_path, total=len(rows))

    return text, status
