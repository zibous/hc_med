"""Norm-Bar HTML-Rendering (Apple Health Style) für Jinja-Templates."""

import re


def parse_normbereich(norm_str: str) -> dict | None:
    """Parst einen Normbereich-String in {'min': float|None, 'max': float|None}."""
    if not norm_str or not isinstance(norm_str, str):
        return None
    s = norm_str.strip().replace(",", ".")

    # Ungültige Strings
    if s.lower() in ("abs", "aut%", "aut", "rel%", "rel", "%"):
        return None

    # Format: "< X" oder "<X"
    m = re.match(r"^<\s*-?\s*([\d.]+)$", s)
    if m:
        return {"min": None, "max": float(m.group(1))}

    # Format: "> X"
    m = re.match(r"^>\s*-?\s*([\d.]+)$", s)
    if m:
        return {"min": float(m.group(1)), "max": None}

    # Format: "X-Y" oder "X - Y"
    m = re.match(r"^([\d.]+)\s*[-–]\s*([\d.]+)$", s)
    if m:
        min_val = float(m.group(1))
        max_val = float(m.group(2))
        # Ungültig wenn min == max (z.B. "0.0-0.0")
        if min_val == max_val:
            return None
        return {"min": min_val, "max": max_val}

    # Format: "-X" (nur Obergrenze)
    m = re.match(r"^-\s*([\d.]+)$", s)
    if m:
        return {"min": None, "max": float(m.group(1))}

    # Format: Einzelne Zahl "200" → interpretiere als Obergrenze "< 200"
    m = re.match(r"^([\d.]+)$", s)
    if m:
        return {"min": None, "max": float(m.group(1))}

    return None


def norm_bar_html(wert: str, norm_str: str, flag: str = "") -> str:
    """Generiert einen Norm-Balken als inline HTML für Druckberichte.
    
    Gibt einen HTML-String zurück. Im Template mit |safe verwenden.
    """
    norm = parse_normbereich(norm_str)
    if not norm:
        return f'<span style="color:#666">{norm_str}</span>'

    # Wert parsen
    raw = str(wert).replace(",", ".")
    raw = re.sub(r"^[<>]\s*", "", raw)
    try:
        val = float(raw)
    except (ValueError, TypeError):
        return f'<span style="color:#666">{norm_str}</span>'

    norm_min = norm["min"]
    norm_max = norm["max"]

    # Skala berechnen
    if norm_min is not None and norm_max is not None:
        rng = norm_max - norm_min
        padding = rng * 0.4
        scale_min = max(0, norm_min - padding)
        scale_max = norm_max + padding
    elif norm_max is not None:
        scale_min = 0
        scale_max = norm_max * 3
    elif norm_min is not None:
        scale_min = 0
        scale_max = norm_min * 2
    else:
        return f'<span style="color:#666">{norm_str}</span>'

    # Wert muss in Skala passen
    if val < scale_min:
        scale_min = val * 0.8
    if val > scale_max:
        scale_max = val * 1.1

    total_range = scale_max - scale_min or 1

    # Positionen berechnen (0-100%)
    val_pos = max(0, min(100, ((val - scale_min) / total_range) * 100))
    norm_start = max(0, ((norm_min - scale_min) / total_range) * 100) if norm_min is not None else 0
    norm_end = min(100, ((norm_max - scale_min) / total_range) * 100) if norm_max is not None else 100

    dot_class = "nb-dot-bad" if flag in ("H", "L") else "nb-dot-ok"

    return (
        f'<span class="norm-bar-print" title="Wert: {val} | Norm: {norm_str}">'
        f'<span class="nb-low" style="width:{norm_start:.1f}%"></span>'
        f'<span class="nb-ok" style="left:{norm_start:.1f}%;width:{norm_end - norm_start:.1f}%"></span>'
        f'<span class="nb-high" style="left:{norm_end:.1f}%;width:{100 - norm_end:.1f}%"></span>'
        f'<span class="nb-dot {dot_class}" style="left:{val_pos:.1f}%"></span>'
        f'</span>'
    )
