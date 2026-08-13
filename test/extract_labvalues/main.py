#!/usr/bin/env python3
import argparse
import logging
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Config / Paths
from config.loader import load_config
from config.paths import get_paths

# Parsing / Normalization / Output
from parsing.auto_detect import detect_format_for_file, PARSER_MAP
from normalization.apply import normalize_record
from output.writer import write_csv
from output.database import write_to_db

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def setup_logging(log_path: Path, level=logging.INFO):
    """Configure root logger: console + file handler."""
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Basic console config
    root = logging.getLogger()
    root.setLevel(level)

    # Remove default handlers to avoid duplicate logs on repeated calls
    for h in list(root.handlers):
        root.removeHandler(h)

    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(logging.Formatter(LOG_FORMAT))
    root.addHandler(ch)

    # File handler
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(level)
    fh.setFormatter(logging.Formatter(LOG_FORMAT))
    root.addHandler(fh)


def parse_file_worker(filepath: Path):
    logger = logging.getLogger("parser")
    try:
        parser_name = detect_format_for_file(filepath)
        parser = PARSER_MAP.get(parser_name)
        if not parser:
            logger.warning("Kein Parser für %s (detected=%s)", filepath.name, parser_name)
            return []
        return parser(filepath)
    except Exception:
        logger.exception("Fehler beim Parsen von %s", filepath)
        return []


def main():
    ap = argparse.ArgumentParser(description="Extract lab values")
    ap.add_argument("user", nargs="?", default="peter", help="User id (z.B. peter, reni)")
    ap.add_argument("--data-dir", help="Override data directory (sets EXTRACT_LABVALUES_DATA_DIR)", default=None)
    ap.add_argument("-dryrun", action="store_true", help="Scan and normalize but do not write outputs")
    ap.add_argument("-save_csv", action="store_true", help="Write CSV output")
    ap.add_argument("-database", action="store_true", help="Write to SQLite database")
    ap.add_argument("-compare", action="store_true", help="Write CSV to /tmp and diff against existing output")
    ap.add_argument("-debug", action="store_true", help="Enable debug logging")
    args = ap.parse_args()

    # Allow CLI override of data dir via env var used by config.paths.resolve_data_dir
    if args.data_dir:
        os.environ["EXTRACT_LABVALUES_DATA_DIR"] = args.data_dir

    # Load config and users (loader returns cfg, users, data_dir)
    cfg, users, data_dir = load_config()
    patients = users.get("patient", {}) if isinstance(users, dict) else {}
    user = patients.get(args.user)
    if not user:
        # Friendly error with available users
        available = ", ".join(patients.keys()) if patients else "<keine user in userlist.yaml>"
        raise SystemExit(f"User '{args.user}' nicht in userlist.yaml gefunden. Verfügbar: {available}")

    # Resolve paths for this user
    paths = get_paths(args.user)

    # Setup logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    setup_logging(paths["log"], level=log_level)
    logger = logging.getLogger("main")
    logger.info("Start für user=%s, data_dir=%s", args.user, data_dir)

    # Ensure import directory exists
    if not paths["befunde"].exists():
        logger.warning("Befunde-Verzeichnis existiert nicht: %s", paths["befunde"])
        logger.info("Erstelle Verzeichnis (falls gewünscht) und beende Dryrun")
        # create directory so user can drop files later
        paths["befunde"].mkdir(parents=True, exist_ok=True)
        if args.dryrun:
            logger.info("Dryrun beendet (keine Dateien vorhanden).")
            return
        # continue: will find no files

    # Collect files
    files = [p for p in paths["befunde"].iterdir() if p.is_file()]
    logger.info("Gefundene Dateien in %s: %d", paths["befunde"], len(files))

    # Parallel parsing (I/O bound)
    records = []
    if files:
        max_workers = min(8, max(2, len(files)))
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = {ex.submit(parse_file_worker, f): f for f in files}
            for fut in as_completed(futures):
                res = fut.result()
                if res:
                    records.extend(res)

    logger.info("Rohwerte gesamt: %d", len(records))

    # Normalisieren (seriell; cheap CPU)
    # Geburtsdatum für Altersberechnung
    from datetime import date as _date
    
    geb_str = user.get("geburtsdatum", "")
    geburtsdatum = None
    if geb_str:
        try:
            parts = geb_str.split("-")
            geburtsdatum = _date(int(parts[0]), int(parts[1]), int(parts[2]))
        except (ValueError, IndexError):
            logger.warning("Geburtsdatum ungültig: %s", geb_str)

    normalized = []
    for r in records:
        try:
            normalized.append(normalize_record(r, geburtsdatum=geburtsdatum))
        except Exception:
            logging.getLogger("normalization").exception("Normalisierung fehlgeschlagen für %s", r)

    logger.info("Normalisierte Werte: %d", len(normalized))

    # Körperdaten rausfiltern wenn scaledb konfiguriert (kommen dann via import_scale.py)
    if user.get("scaledb"):
        normalized = [r for r in normalized if r.get("Gruppe") != "Körperdaten"]
        logger.info("Laborwerte (ohne Körperdaten, via scaledb): %d", len(normalized))

    # Deduplizierung: Bei gleichem Datum + Test_Standard den besseren Record behalten
    # "Besser" = hat Wert_Norm + Einheit_Norm + Normbereich + mehr Dezimalstellen (Pivot-Qualität)
    def record_score(r):
        score = 0
        if r.get("Wert_Norm"):
            score += 8
        if r.get("Einheit_Norm"):
            score += 4
        if r.get("Normbereich"):
            score += 2
        # Prefer values with more decimal places (Pivot tends to have trailing zeros)
        wn = r.get("Wert_Norm", "")
        if "." in wn:
            score += len(wn.split(".")[1])
        return score

    seen = {}
    for r in normalized:
        key = (r.get("Datum", ""), r.get("Test_Standard", ""))
        if key not in seen or record_score(r) >= record_score(seen[key]):
            seen[key] = r
    normalized = list(seen.values())
    logger.info("Nach Deduplizierung: %d", len(normalized))

    # Dryrun: do not write outputs
    if args.dryrun:
        logger.info("Dryrun: keine Ausgabe geschrieben")
        print(f"Dryrun: {len(normalized)} Werte erkannt")
        return

    # Compare mode: write to /tmp and diff against existing file
    if args.compare:
        import tempfile
        import subprocess

        existing = paths["output"]
        tmp_file = Path(tempfile.gettempdir()) / f"laborwerte_{args.user}_compare.csv"
        
        # Sort like the existing file: Gruppe, Test_Standard, Datum
        sorted_normalized = sorted(normalized, key=lambda r: (
            r.get("Gruppe") or "",
            r.get("Test_Standard") or "",
            r.get("Datum") or "",
        ))
        
        write_csv(sorted_normalized, tmp_file, include_empty=False)
        
        # Count actually written lines (after has_value filter)
        written_lines = sum(1 for _ in tmp_file.read_text().splitlines()) - 1
        logger.info("Compare-CSV geschrieben: %s (%d Werte)", tmp_file, written_lines)

        if not existing.exists():
            print(f"⚠️  Bestehende Datei nicht gefunden: {existing}")
            print(f"   Neue Datei liegt unter: {tmp_file}")
            return

        # Detect delimiter of existing file
        first_line = existing.read_text(encoding="utf-8").splitlines()[0]
        old_delimiter = ";" if ";" in first_line else ","

        result = subprocess.run(
            ["diff", "--unified=3", str(existing), str(tmp_file)],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print(f"✅ Keine Unterschiede! ({len(normalized)} Werte)")
        else:
            import csv as _csv

            # Count lines for summary (excluding Körperdaten from old)
            old_lines = 0
            with existing.open(encoding="utf-8") as f:
                for row in _csv.DictReader(f, delimiter=";"):
                    if row.get("Gruppe") != "Körperdaten":
                        old_lines += 1
            new_lines = len(sorted_normalized)
            print(f"❌ Unterschiede gefunden (alt: {old_lines}, neu: {written_lines} Werte):\n")

            # Analyse: fehlende/neue Zeilen pro Datum
            old_dates = {}
            with existing.open(encoding="utf-8") as f:
                for row in _csv.DictReader(f, delimiter=";"):
                    if row.get("Gruppe") == "Körperdaten":
                        continue
                    d = row.get("Datum", "?")
                    old_dates[d] = old_dates.get(d, 0) + 1
            new_dates = {}
            with tmp_file.open(encoding="utf-8") as f:
                for row in _csv.DictReader(f, delimiter=";"):
                    d = row.get("Datum", "?")
                    new_dates[d] = new_dates.get(d, 0) + 1

            all_dates = sorted(set(list(old_dates.keys()) + list(new_dates.keys())))
            print(f"{'Datum':<12} {'Alt':>4} {'Neu':>4} {'Diff':>5}")
            print("-" * 30)
            for d in all_dates:
                o = old_dates.get(d, 0)
                n = new_dates.get(d, 0)
                if o != n:
                    print(f"{d:<12} {o:>4} {n:>4} {n-o:>+5}")

            # Detail-Vergleich: basierend auf Schlüssel Datum+Test_Standard
            print(f"\n{'='*60}")
            print("DETAIL-VERGLEICH (Schlüssel: Datum + Test_Standard)")
            print(f"{'='*60}")

            old_records = {}
            with existing.open(encoding="utf-8") as f:
                for row in _csv.DictReader(f, delimiter=";"):
                    # Skip Körperdaten (come from import_scale.py, not from lab parser)
                    if row.get("Gruppe") == "Körperdaten":
                        continue
                    key = (row.get("Datum", ""), row.get("Test_Standard", ""))
                    old_records.setdefault(key, []).append(row)

            new_records = {}
            with tmp_file.open(encoding="utf-8") as f:
                for row in _csv.DictReader(f, delimiter=";"):
                    key = (row.get("Datum", ""), row.get("Test_Standard", ""))
                    new_records.setdefault(key, []).append(row)

            # Fehlend in neu
            missing = []
            for key in old_records:
                if key not in new_records:
                    for row in old_records[key]:
                        missing.append(row)

            if missing:
                print(f"\n🔴 In ALT aber NICHT in NEU ({len(missing)} Werte):")
                for row in missing[:30]:
                    print(f"  {row.get('Datum')} | {row.get('Gruppe') or '':<20} | {row.get('Test_Standard') or '':<20} | {row.get('Wert_Norm') or ''} {row.get('Einheit_Norm') or ''}")
                if len(missing) > 30:
                    print(f"  ... und {len(missing)-30} weitere")

            # Unterschiede bei gleichen Schlüsseln
            diffs = []
            for key in old_records:
                if key in new_records:
                    old_row = old_records[key][0]
                    new_row = new_records[key][0]
                    changes = []
                    for col in ["Gruppe", "Wert_Norm", "Einheit_Norm"]:
                        ov = old_row.get(col, "")
                        nv = new_row.get(col, "")
                        if ov != nv:
                            changes.append(f"{col}: '{ov}'→'{nv}'")
                    if changes:
                        diffs.append((key, changes))

            if diffs:
                print(f"\n🟡 Unterschiede bei gleichen Tests ({len(diffs)}):")
                for (datum, test), changes in diffs[:30]:
                    print(f"  {datum} | {test:<20} | {', '.join(changes)}")
                if len(diffs) > 30:
                    print(f"  ... und {len(diffs)-30} weitere")

            print(f"\nFull diff: diff {existing} {tmp_file}")
        return

    # Default behavior: if neither save_csv nor database specified, save CSV
    if args.save_csv or not (args.save_csv or args.database):
        try:
            # Standard: keine leeren Werte schreiben
            write_csv(normalized, paths["output"], include_empty=False)
            # Wenn du später alle Zeilen willst:
            # write_csv(normalized, paths["output"], include_empty=True)
            logger.info("CSV geschrieben: %s", paths["output"])
        except Exception:
            logger.exception("Fehler beim Schreiben der CSV")

    if args.database:
        try:            
            db_records = [r for r in normalized if r.get("Wert_Norm") not in (None, "") or any(ch.isdigit() for ch in str(r.get("Wert","")))]
            write_to_db(db_records, paths["db"])
            logger.info("DB geschrieben: %s", paths["db"])
        except Exception:
            logger.exception("Fehler beim Schreiben in die DB")

    logger.info("Fertig")


if __name__ == "__main__":
    main()
