# debug_detect.py
from pathlib import Path
from parsing.auto_detect import detect_format_for_file, PARSER_MAP

p = Path("../data/user/reni/import/2019-07-10_laborbefund_praxis-zuend.txt")
print("File:", p.resolve())
detected = detect_format_for_file(p)
print("Detected format:", detected)

parser = PARSER_MAP.get(detected)
if not parser:
    print("No parser found for", detected)
else:
    try:
        records = parser(p)
        print("Parser returned", len(records), "records")
        for i, r in enumerate(records[:10]):
            print(i+1, r)
    except Exception as e:
        print("Parser raised exception:", e)
