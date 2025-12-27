# scripts/extract_scad.py
import argparse
from pathlib import Path
import json
from scripts.scad_utils import extract_text_from_row, sanitize_scad

def load_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preds", required=True, help="runs/*.jsonl from run_eval.py")
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--mode", choices=["raw", "clean", "both"], default="raw",
                    help="raw = exact model text; clean = sanitized; both = write both")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    n = 0
    for row in load_jsonl(Path(args.preds)):
        ex_id = row.get("id") or (row.get("item") or {}).get("id")
        if not ex_id:
            continue

        text = extract_text_from_row(row)
        clean, _ = sanitize_scad(text)

        if args.mode in ("raw", "both"):
            (out_dir / f"{ex_id}.scad").write_text(text, encoding="utf-8")
        if args.mode in ("clean", "both"):
            (out_dir / f"{ex_id}__clean.scad").write_text(clean, encoding="utf-8")

        n += 1

    print(f"Wrote {n} .scad files to {out_dir.resolve()}")

if __name__ == "__main__":
    main()
