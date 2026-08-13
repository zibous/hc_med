# debug_detect_verbose.py
from pathlib import Path
from parsing.auto_detect import detect_format_for_file, PARSER_MAP

p = Path("../data/user/reni/import/2019-07-10_laborbefund_praxis-zuend.txt")
if not p.exists():
    print("Datei nicht gefunden:", p.resolve())
    raise SystemExit(1)

text = p.read_text(encoding="utf-8", errors="replace")
print("=== repr(text[:400]) ===")
print(repr(text[:400]))
print("\n=== first 12 lines (repr) ===")
for i, l in enumerate(text.splitlines()[:12], 1):
    print(f"{i:2d}:", repr(l))

detected = detect_format_for_file(p)
print("\nDetected format:", detected)

parser = PARSER_MAP.get(detected)
if not parser:
    print("Kein Parser für:", detected)
else:
    try:
        recs = parser(p)
        print("\nParser returned", len(recs), "records")
        for i, r in enumerate(recs[:20], 1):
            print(f"\nRecord {i}:")
            for k, v in r.items():
                print(f"  {k}: {v!r}")
    except Exception as e:
        print("Parser raised exception:", repr(e))
