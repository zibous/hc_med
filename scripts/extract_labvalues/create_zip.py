import zipfile
from pathlib import Path

def make_zip(src_dir: Path, out_zip: Path):
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for p in src_dir.rglob("*"):
            z.write(p, p.relative_to(src_dir))

if __name__ == "__main__":
    import sys
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("extract_labvalues.zip")
    make_zip(src, out)
    print("ZIP erstellt:", out)
