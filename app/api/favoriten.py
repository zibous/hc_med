"""API: /favoriten – Favorisierte Laborwerte verwalten."""

from pathlib import Path

import yaml
from fastapi import APIRouter

from app.config.settings import KURZNAMEN
from app.infrastructure.database import get_db, get_user_data_path

router = APIRouter(prefix="/api", tags=["favoriten"])


def _favoriten_path() -> Path:
    """Gibt den Pfad zur Favoriten-Datei des aktiven Users zurück."""
    return get_user_data_path() / "favoriten.yaml"


def _load_favoriten() -> list[str]:
    """Lädt die Favoriten-Liste aus der YAML-Datei."""
    path = _favoriten_path()
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data.get("favoriten", [])


def _save_favoriten(favoriten: list[str]) -> None:
    """Speichert die Favoriten-Liste in die YAML-Datei."""
    path = _favoriten_path()
    path.write_text(
        yaml.dump({"favoriten": favoriten}, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )


@router.get("/favoriten")
async def get_favoriten():
    """Gibt die Liste der favorisierten Tests zurück (mit aktuellem Wert)."""
    favoriten = _load_favoriten()
    if not favoriten:
        return {"favoriten": []}

    conn = get_db()
    try:
        result = []
        for test in favoriten:
            row = conn.execute(
                """SELECT wert_norm, einheit_norm, flag, datum, normbereich
                   FROM laborwerte WHERE test_standard=? ORDER BY datum DESC LIMIT 1""",
                (test,),
            ).fetchone()
            if row:
                result.append({
                    "test": test,
                    "wert": row["wert_norm"],
                    "einheit": row["einheit_norm"] or "",
                    "flag": row["flag"] or "",
                    "datum": row["datum"],
                    "normbereich": row["normbereich"] or "",
                })
            else:
                result.append({"test": test, "wert": "–", "einheit": "", "flag": "", "datum": "", "normbereich": ""})
        return {"favoriten": result}
    finally:
        conn.close()


@router.get("/favoriten/liste")
async def get_favoriten_liste():
    """Gibt nur die Testnamen der Favoriten zurück (für Star-Status)."""
    return {"favoriten": _load_favoriten()}


@router.get("/favoriten/detail")
async def get_favoriten_detail():
    """Gibt eine detaillierte Tabelle aller Favoriten zurück (für die Listen-Ansicht)."""
    favoriten = _load_favoriten()
    if not favoriten:
        return {"favoriten": []}

    conn = get_db()
    try:
        result = []
        for test in favoriten:
            # Letzte 2 Werte für Trend
            rows = conn.execute(
                """SELECT wert_norm, einheit_norm, flag, datum, normbereich, gruppe
                   FROM laborwerte WHERE test_standard=? ORDER BY datum DESC LIMIT 2""",
                (test,),
            ).fetchall()
            if not rows:
                continue

            aktuell = rows[0]
            vorwert = rows[1] if len(rows) > 1 else None

            # Trend berechnen
            trend = ""
            try:
                val_akt = float(str(aktuell["wert_norm"]).replace(",", ".").replace("<", "").replace(">", ""))
                if vorwert:
                    val_vor = float(str(vorwert["wert_norm"]).replace(",", ".").replace("<", "").replace(">", ""))
                    if val_vor != 0:
                        pct = round((val_akt - val_vor) / val_vor * 100)
                        if pct > 5:
                            trend = f"↑ +{pct}%"
                        elif pct < -5:
                            trend = f"↓ {pct}%"
                        else:
                            trend = "→ unverändert"
            except (ValueError, TypeError):
                pass

            # Anzahl pathologischer Werte
            path_count = conn.execute(
                "SELECT COUNT(*) FROM laborwerte WHERE test_standard=? AND flag IN ('H','L')",
                (test,),
            ).fetchone()[0]

            total_count = conn.execute(
                "SELECT COUNT(*) FROM laborwerte WHERE test_standard=?",
                (test,),
            ).fetchone()[0]

            result.append({
                "test": test,
                "kurzname": KURZNAMEN.get(test, ""),
                "gruppe": aktuell["gruppe"],
                "wert": aktuell["wert_norm"],
                "einheit": aktuell["einheit_norm"] or "",
                "flag": aktuell["flag"] or "",
                "datum": aktuell["datum"],
                "normbereich": aktuell["normbereich"] or "",
                "vorwert": vorwert["wert_norm"] if vorwert else "",
                "vor_datum": vorwert["datum"] if vorwert else "",
                "trend": trend,
                "pathologisch": path_count,
                "messungen": total_count,
            })

        return {"favoriten": result, "anzahl": len(result)}
    finally:
        conn.close()


@router.post("/favoriten/{test:path}")
async def add_favorit(test: str):
    """Fügt einen Test zu den Favoriten hinzu."""
    favoriten = _load_favoriten()
    if test not in favoriten:
        favoriten.append(test)
        _save_favoriten(favoriten)
    return {"ok": True, "favoriten": favoriten}


@router.delete("/favoriten/{test:path}")
async def remove_favorit(test: str):
    """Entfernt einen Test aus den Favoriten."""
    favoriten = _load_favoriten()
    if test in favoriten:
        favoriten.remove(test)
        _save_favoriten(favoriten)
    return {"ok": True, "favoriten": favoriten}
