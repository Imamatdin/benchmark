import argparse, json, os, subprocess, tempfile
from pathlib import Path

def load_jsonl(p: Path):
    out=[]
    with p.open("r",encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if line: out.append(json.loads(line))
    return out

def write_jsonl(p: Path, rows):
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w",encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

def fmt_define(k,v):
    if isinstance(v,bool): return f"{k}={'true' if v else 'false'}"
    if isinstance(v,(int,float)): return f"{k}={v}"
    return f'{k}="{v}"'

def run_openscad(exe: str, scad: Path, stl: Path, defines: dict, timeout_s: float):
    cmd=[exe,"-o",str(stl)]
    for k,v in (defines or {}).items():
        cmd += ["-D", fmt_define(k,v)]
    cmd += [str(scad)]
    r=subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    return r.returncode, r.stdout, r.stderr, " ".join(cmd)

def mesh_metrics(stl: Path):
    import trimesh
    m = trimesh.load_mesh(str(stl), force="mesh")
    if hasattr(m,"geometry") and isinstance(m.geometry,dict) and len(m.geometry)>0:
        m = list(m.geometry.values())[0]
    b = m.bounds
    ext = (b[1]-b[0]).tolist()
    vol = float(m.volume)
    area = float(m.area)
    return ext, vol, area

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--gold_scad_dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--openscad", default=os.getenv("OPENSCAD_EXE",""))
    ap.add_argument("--timeout_s", type=float, default=20.0)
    args=ap.parse_args()

    exe = Path(args.openscad)
    if not args.openscad or not exe.exists():
        raise SystemExit("ERROR: set OPENSCAD_EXE or pass --openscad")

    data = load_jsonl(Path(args.data))
    gold_dir = Path(args.gold_scad_dir)

    tmp = Path(tempfile.mkdtemp(prefix="cadbench_gold_stl_"))

    for item in data:
        ex_id = item["id"]
        gold_scad = gold_dir / f"{ex_id}.scad"
        if not gold_scad.exists():
            # allow gold by id with same name already (your ids match)
            print(f"SKIP {ex_id}: missing gold scad {gold_scad}")
            continue

        eval_ = item.get("eval") or {}
        cases = eval_.get("cases") or []
        for case in cases:
            defines = case.get("defines") or {}
            stl = tmp / f"{ex_id}__{case.get('name','default')}.stl"
            rc, out, err, cmd = run_openscad(args.openscad, gold_scad, stl, defines, args.timeout_s)
            if rc != 0 or not stl.exists():
                raise SystemExit(f"GOLD COMPILE FAIL {ex_id} case={case.get('name')}\nCMD: {cmd}\n{(err or out)[:800]}")
            ext, vol, area = mesh_metrics(stl)
            expect = case.setdefault("expect", {})
            # keep your existing bounds/volume if you want; only add area now:
            expect["area"] = area

    write_jsonl(Path(args.out), data)
    print(f"Wrote: {Path(args.out).resolve()}")

if __name__ == "__main__":
    main()
