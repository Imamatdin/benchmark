import argparse
import subprocess
from pathlib import Path
import os
import tempfile

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in_dir", required=True)
    ap.add_argument("--timeout_s", type=float, default=30.0)
    ap.add_argument(
        "--openscad",
        default=os.environ.get("OPENSCAD_EXE", "openscad"),
        help="Path to OpenSCAD executable (or set OPENSCAD_EXE env var).",
    )
    args = ap.parse_args()

    in_dir = Path(args.in_dir)
    scad_files = sorted(in_dir.glob("*.scad"))

    if not scad_files:
        print("Compile pass rate: 0/0 (0.0%)")
        return

    ok = 0
    total = 0

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        for f in scad_files:
            total += 1
            out_csg = tmpdir / (f.stem + ".csg")

            # Exporting .csg is usually lighter than STL; still validates parsing + most errors.
            cmd = [args.openscad, "-o", str(out_csg), str(f)]

            try:
                r = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=args.timeout_s,
                )
                passed = (r.returncode == 0) and out_csg.exists()
            except FileNotFoundError:
                print(f"\nERROR: OpenSCAD executable not found: {args.openscad}")
                print("Fix: pass --openscad 'C:\\Path\\to\\openscad.exe' or set OPENSCAD_EXE.")
                raise
            except subprocess.TimeoutExpired:
                passed = False

            if passed:
                ok += 1
            else:
                # Print a short failure snippet (don’t spam)
                err = (r.stderr or r.stdout or "").strip()
                if err:
                    print(f"\nFAIL {f.name}:\n{err[:500]}")

    pct = 100.0 * ok / total if total else 0.0
    print(f"\nCompile pass rate: {ok}/{total} ({pct:.1f}%)")

if __name__ == "__main__":
    main()
