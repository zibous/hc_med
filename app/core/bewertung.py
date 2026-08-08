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
    Validiert den Flag gegen den aktuellen Normbereich (nicht blind vertrauen).
    Returns: (bewertung_text, bewertung_status)
    """
    if not rows:
        return "", "gut"

    last_val = rows[-1]["wert_norm"]
    last_flag = rows[-1]["flag"]
    einheit = rows[-1]["einheit_norm"] or ""

    # Besten Normbereich suchen (neuester mit Ziffern)
    norm = ""
    for r in reversed(rows):
        nb = (r.get("normbereich") or "").strip()
        if nb and any(c.isdigit() for c in nb):
            norm = nb
            break

    # Flag validieren: Wert gegen angezeigten Normbereich prüfen
    last_flag = _validate_flag(last_val, last_flag, norm)

    flag_text = ""
    if last_flag == "H":
        flag_text = " (erhöht)"
    elif last_flag == "L":
        flag_text = " (erniedrigt)"

    # Status primär am letzten Wert
    if not last_flag:
        # Letzter Wert OK – prüfe ob letzte 3 auch OK
        recent3 = rows[-3:] if len(rows) >= 3 else rows
        r3_path = sum(1 for r in recent3 if r["flag"] in ("H", "L"))
        if r3_path == 0:
            status = "gut"
        else:
            status = "gut"  # Letzter OK, Tendenz besser
        text = _trend_texte.get("gut", "").format(wert=last_val, einheit=einheit, flag_text=flag_text, norm=norm)
    else:
        # Letzter Wert auffällig – prüfe Schwere (auch hier Flags validieren)
        recent3 = rows[-3:] if len(rows) >= 3 else rows
        r3_path = sum(1 for r in recent3 if _validate_flag(r["wert_norm"], r["flag"], norm))

        # Toleranz: bei <5% Abweichung vom Normbereich nie "kritisch"
        knapp = _is_knapp_daneben(last_val, norm)

        if r3_path >= 3 and not knapp:
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


def _validate_flag(wert_str: str, flag: str, normbereich: str) -> str:
    """Validiert einen Flag gegen den Normbereich.

    Wenn der Wert innerhalb des Normbereichs liegt, wird der Flag gelöscht.
    Verhindert falsche 'kritisch'-Meldungen bei wechselnden Normbereichen.
    """
    if not flag or not normbereich:
        return flag

    try:
        val = float(str(wert_str).replace(",", ".").replace("<", "").replace(">", ""))
    except (ValueError, TypeError):
        return flag

    lo, hi = _parse_norm_range(normbereich)
    if lo is not None and hi is not None:
        if lo <= val <= hi:
            return ""
    elif hi is not None:  # nur Obergrenze (< X)
        if val < hi:
            return ""
    elif lo is not None:  # nur Untergrenze (> X)
        if val > lo:
            return ""

    return flag


def _is_knapp_daneben(wert_str: str, normbereich: str, toleranz: float = 0.10) -> bool:
    """Prüft ob der Wert nur knapp (<10%) außerhalb des Normbereichs liegt."""
    if not normbereich:
        return False

    try:
        val = float(str(wert_str).replace(",", ".").replace("<", "").replace(">", ""))
    except (ValueError, TypeError):
        return False

    lo, hi = _parse_norm_range(normbereich)

    if lo is not None and val < lo:
        spanne = hi - lo if hi is not None else lo
        if spanne > 0:
            return (lo - val) / spanne <= toleranz
    elif hi is not None and val > hi:
        spanne = hi - lo if lo is not None else hi
        if spanne > 0:
            return (val - hi) / spanne <= toleranz

    return False


def _parse_norm_range(normbereich: str) -> tuple[float | None, float | None]:
    """Parst einen Normbereich-String in (lo, hi). None wenn nicht parsbar."""
    norm = normbereich.strip()

    # Format: "lo-hi"
    if "-" in norm and not norm.startswith("<") and not norm.startswith(">"):
        parts = norm.replace("–", "-").split("-")
        if len(parts) == 2:
            try:
                return float(parts[0].strip()), float(parts[1].strip())
            except (ValueError, TypeError):
                pass
        elif len(parts) == 3 and parts[0] == "":
            try:
                return -float(parts[1].strip()), float(parts[2].strip())
            except (ValueError, TypeError):
                pass

    # Format: "< X"
    elif norm.startswith("<"):
        try:
            return None, float(norm[1:].strip())
        except (ValueError, TypeError):
            pass

    # Format: "> X"
    elif norm.startswith(">"):
        try:
            return float(norm[1:].strip()), None
        except (ValueError, TypeError):
            pass

    return None, None
