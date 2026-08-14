"""Normbereich-Auflösung und Flag-Berechnung (H/L)."""

import re

from config.app_config import config


class NormFlagResolver:
    """Bestimmt Normbereiche und berechnet H/L-Flags."""

    def __init__(self):
        self.INVALID_NORMS = getattr(config, "INVALID_NORMS", set())

    def resolve_normbereich(self, row: dict) -> None:
        """Bestimmt den Normbereich: aus Befund, oder Fallback aus YAML-Config."""
        test_name = row.get("Test_Standard", "")
        norm = row.get("Normbereich", "").strip()

        # Übernahme aus "Norm"-Feld falls Normbereich leer
        if not norm and row.get("Norm"):
            norm = row["Norm"].strip()
            row["Normbereich"] = norm

        # Ungültige Normen bereinigen
        if norm.lower() in self.INVALID_NORMS:
            norm = ""
            row["Normbereich"] = ""

        # Formatierung: "<-X" → "<X"
        if norm:
            norm = re.sub(r"^(<\s*)-\s*", r"\1", norm)
            row["Normbereich"] = norm

        # Einzelne Zahl → "< X" interpretieren
        if norm and re.match(r"^\d+\.?\d*$", norm):
            norm = f"< {norm}"
            row["Normbereich"] = norm

        # Fallback auf YAML-Normbereiche wenn leer oder ungültig
        if not norm or norm.lower() == "quotient":
            yaml_range = config.STANDARD_RANGES.get(test_name, "")
            if yaml_range:
                norm = str(yaml_range)
                row["Normbereich"] = norm
            else:
                row["Normbereich"] = ""

        # Wert_Norm sicherstellen
        if not row.get("Wert_Norm"):
            row["Wert_Norm"] = row.get("Wert", "")

    def calculate_flag(self, row: dict) -> None:
        """Berechnet das Flag (H/L/leer) basierend auf Wert und Normbereich."""
        test_name = row.get("Test_Standard", "")
        norm = row.get("Normbereich", "").strip()
        wert_str = row.get("Wert_Norm", "").replace("<", "").replace(">", "").strip()

        if not norm or not wert_str:
            return

        try:
            wert = float(wert_str)
        except ValueError:
            return

        norm_lo, norm_hi = self._parse_norm_range(norm)

        # Normbereich-Korrekturen für konvertierte Einheiten
        norm_lo, norm_hi = self._correct_norm_for_unit(test_name, norm_lo, norm_hi, row)

        # GFR-Toleranz: 85 statt strikt 90
        if test_name == "GFR" and norm_lo == 90.0:
            norm_lo = 85.0 if wert < 85.0 else None

        # Flag bestimmen
        if norm_hi is not None and wert > norm_hi:
            row["Flag"] = "H"
        elif norm_lo is not None and wert < norm_lo:
            row["Flag"] = "L"
        else:
            row["Flag"] = ""

    # ──────────────────────────────────────────────────────────────────────────
    # PRIVATE HILFSMETHODEN
    # ──────────────────────────────────────────────────────────────────────────
    def _parse_norm_range(self, norm: str) -> tuple:
        """Parst einen Normbereich-String in (low, high) Tupel."""
        norm_lo, norm_hi = None, None

        # "X - Y" oder "X-Y"
        m = re.match(r"^([\d.]+)\s*-\s*([\d.]+)$", norm)
        if m:
            return float(m.group(1)), float(m.group(2))

        # "< X"
        m2 = re.match(r"^[<]\s*-?\s*([\d.]+)$", norm)
        if m2:
            return None, float(m2.group(1))

        # "> X"
        m3 = re.match(r"^[>]\s*-?\s*([\d.]+)$", norm)
        if m3:
            return float(m3.group(1)), None

        # "-X" (nur obere Grenze)
        m4 = re.match(r"^-\s*([\d.]+)$", norm)
        if m4:
            return None, float(m4.group(1))

        return norm_lo, norm_hi

    def _correct_norm_for_unit(self, test_name: str, norm_lo: float | None,
                                norm_hi: float | None, row: dict) -> tuple:
        """Korrigiert den Normbereich wenn Einheiten-Konversion stattfand."""

        # Hämatokrit: Norm in l/l → % umrechnen
        if test_name == "Hämatokrit" and norm_hi is not None and norm_hi < 1:
            norm_lo = norm_lo * 100 if norm_lo else None
            norm_hi = norm_hi * 100
            row["Normbereich"] = f"{norm_lo:.0f}-{norm_hi:.0f}" if norm_lo else f"<{norm_hi:.0f}"

        # Hämoglobin/MCHC: Norm in g/L → g/dL umrechnen
        if test_name in ("Hämoglobin", "MCHC") and norm_hi is not None and norm_hi > 50:
            norm_lo = norm_lo / 10 if norm_lo else None
            norm_hi = norm_hi / 10
            row["Normbereich"] = f"{norm_lo:.1f}-{norm_hi:.1f}" if norm_lo else f"<{norm_hi:.1f}"

        # Cholinesterase: Norm in kU/L → U/L umrechnen
        if test_name == "Cholinesterase" and norm_hi is not None and norm_hi < 20:
            norm_lo = norm_lo * 1000 if norm_lo else None
            norm_hi = norm_hi * 1000
            row["Normbereich"] = f"{norm_lo:.0f}-{norm_hi:.0f}" if norm_lo else f"<{norm_hi:.0f}"

        return norm_lo, norm_hi
