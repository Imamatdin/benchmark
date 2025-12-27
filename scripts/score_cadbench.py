# scripts/score_cadbench.py
import argparse
import json
import math
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------
# Utilities: JSONL + OpenSCAD
# ---------------------------

def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def find_openscad(args_openscad: Optional[str]) -> str:
    if args_openscad and Path(args_openscad).exists():
        return args_openscad
    env = os.getenv("OPENSCAD_EXE")
    if env and Path(env).exists():
        return env
    # fallback: rely on PATH
    return "openscad"


# ---------------------------
# Option C: format + sanitize
# ---------------------------

SCAD_TOKENS = (
    "module", "cube", "cylinder", "sphere", "polyhedron",
    "difference", "union", "intersection",
    "translate", "rotate", "scale", "mirror",
    "linear_extrude", "rotate_extrude",
    "$fn", "$fa", "$fs"
)

_CODE_FENCE_RE = re.compile(r"```(?:\w+)?\s*([\s\S]*?)```", re.M)

def strip_code_fences(text: str) -> str:
    m = _CODE_FENCE_RE.search(text)
    if m:
        return m.group(1).strip()
    return text

def trim_to_first_scad_token(text: str) -> str:
    t = text.lstrip()
    # If it looks like a JSON blob, keep it (format will fail anyway)
    # (we don't try to parse here; raw should be "raw" already)
    best_i = None
    for tok in SCAD_TOKENS:
        i = t.find(tok)
        if i != -1 and (best_i is None or i < best_i):
            best_i = i
    if best_i is None:
        return t.strip()
    return t[best_i:].strip()

def drop_bad_lines(text: str) -> str:
    out = []
    for line in text.splitlines():
        # common garbage / truncation artifacts
        if line.strip() in {"$", "```"}:
            continue
        out.append(line)
    return "\n".join(out).strip()

_ASSIGN_RE_TPL = r"^\s*{name}\s*=\s*[^;]*;\s*$"

def strip_cli_var_assignments(text: str, var_names: List[str]) -> str:
    if not var_names:
        return text
    out_lines = []
    patterns = [re.compile(_ASSIGN_RE_TPL.format(name=re.escape(v))) for v in var_names]
    for line in text.splitlines():
        if any(p.match(line) for p in patterns):
            # delete assignments like W = 50; (they override -D W=...)
            continue
        out_lines.append(line)
    return "\n".join(out_lines).strip()

def sanitize_scad(raw: str, cli_vars: List[str]) -> str:
    t = raw.strip()
    t = strip_code_fences(t)
    t = trim_to_first_scad_token(t)
    t = drop_bad_lines(t)
    t = strip_cli_var_assignments(t, cli_vars)
    return t.strip()

def format_compliant_scad(raw: str, cli_vars: List[str]) -> bool:
    """
    "Format compliance" = interface contract:
    - must be only code (no fences, no prose headers)
    - must not output null
    - must not override CLI vars (W=..., etc.) when those are used in cases
    """
    s = raw.strip()
    if not s:
        return False
    lowered = s.lower()
    if "```" in s:
        return False
    if "here is" in lowered or "json requested" in lowered:
        return False
    if lowered == "null" or "null" in lowered:
        return False
    # crude check: must contain some scad-ish token
    if not any(tok in s for tok in SCAD_TOKENS):
        return False
    # forbid overriding CLI vars when present
    if cli_vars:
        for v in cli_vars:
            if re.search(rf"^\s*{re.escape(v)}\s*=", s, flags=re.M):
                return False
    return True


# ---------------------------
# STL metrics (no extra deps)
# ---------------------------

def parse_stl(path: Path):
    """
    Returns (verts, faces) where verts is a list of (x,y,z) and faces is list of (i,j,k).
    Supports BOTH binary and ASCII STL.
    """
    import struct

    data = path.read_bytes()
    if len(data) < 84:
        raise ValueError("STL too small")

    # Try to detect binary reliably:
    # Binary STL size should be: 84 + tri_count * 50
    tri_count = struct.unpack_from("<I", data, 80)[0]
    expected_size = 84 + tri_count * 50

    if expected_size == len(data):
        # ---- Binary path ----
        off = 84
        verts = []
        faces = []
        for _ in range(tri_count):
            off += 12  # normal
            idxs = []
            for _k in range(3):
                x, y, z = struct.unpack_from("<fff", data, off)
                off += 12
                idxs.append(len(verts))
                verts.append((x, y, z))
            faces.append((idxs[0], idxs[1], idxs[2]))
            off += 2  # attribute
        return verts, faces

    # ---- ASCII fallback ----
    text = data.decode("utf-8", errors="ignore")
    verts = []
    faces = []
    tri = []

    for line in text.splitlines():
        line = line.strip()
        if line.startswith("vertex"):
            parts = line.split()
            if len(parts) >= 4:
                x = float(parts[1]); y = float(parts[2]); z = float(parts[3])
                tri.append((x, y, z))
                if len(tri) == 3:
                    i0 = len(verts); verts.append(tri[0])
                    i1 = len(verts); verts.append(tri[1])
                    i2 = len(verts); verts.append(tri[2])
                    faces.append((i0, i1, i2))
                    tri = []
    if not faces:
        raise ValueError("Failed to parse STL (neither valid binary nor ASCII facets found)")
    return verts, faces

    import struct
    data = path.read_bytes()
    if len(data) < 84:
        raise ValueError("STL too small")
    tri_count = struct.unpack_from("<I", data, 80)[0]
    off = 84
    verts: List[Tuple[float,float,float]] = []
    faces: List[Tuple[int,int,int]] = []
    for _ in range(tri_count):
        # normal (ignored)
        off += 12
        idxs = []
        for _k in range(3):
            x, y, z = struct.unpack_from("<fff", data, off)
            off += 12
            idxs.append(len(verts))
            verts.append((x, y, z))
        faces.append((idxs[0], idxs[1], idxs[2]))
        off += 2  # attribute
    return verts, faces

def bounds_from_verts(verts: List[Tuple[float,float,float]]) -> Tuple[Tuple[float,float,float], Tuple[float,float,float]]:
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))

def volume_and_area(verts: List[Tuple[float,float,float]], faces: List[Tuple[int,int,int]]) -> Tuple[float, float]:
    # volume via tetrahedra w.r.t origin; area via triangle area sum
    vol6 = 0.0
    area = 0.0
    for a, b, c in faces:
        x1,y1,z1 = verts[a]
        x2,y2,z2 = verts[b]
        x3,y3,z3 = verts[c]
        # cross (v2 x v3)
        cx = y2*z3 - z2*y3
        cy = z2*x3 - x2*z3
        cz = x2*y3 - y2*x3
        vol6 += x1*cx + y1*cy + z1*cz
        # area
        ux, uy, uz = (x2-x1, y2-y1, z2-z1)
        vx, vy, vz = (x3-x1, y3-y1, z3-z1)
        ax = uy*vz - uz*vy
        ay = uz*vx - ux*vz
        az = ux*vy - uy*vx
        area += 0.5 * math.sqrt(ax*ax + ay*ay + az*az)
    return abs(vol6) / 6.0, area


# ---------------------------
# Scoring
# ---------------------------

def run_openscad(openscad_exe: str, scad_path: Path, stl_out: Path, defines: Dict[str, Any], timeout_s: float) -> Tuple[bool, str]:
    cmd = [openscad_exe, "-o", str(stl_out)]
    for k, v in defines.items():
        cmd += ["-D", f"{k}={v}"]
    cmd += [str(scad_path)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
        if r.returncode != 0:
            return False, (r.stderr or r.stdout or "").strip()
        return True, ""
    except Exception as e:
        return False, str(e)

def close_enough_bounds(got: List[float], exp: List[float], tol_abs: float) -> bool:
    return all(abs(got[i] - exp[i]) <= tol_abs for i in range(3))

def close_enough_frac(got: float, exp: float, tol_frac: float) -> bool:
    if exp == 0:
        return abs(got) <= tol_frac
    return abs(got - exp) / abs(exp) <= tol_frac

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="cadbench jsonl")
    ap.add_argument("--scad_dir", required=True, help="directory of .scad files named <id>.scad")
    ap.add_argument("--openscad", default=None)
    ap.add_argument("--timeout_s", type=float, default=20.0)
    ap.add_argument("--mode", choices=["best", "strict", "lenient"], default="best")
    args = ap.parse_args()

    data = load_jsonl(Path(args.data))
    scad_dir = Path(args.scad_dir)
    openscad_exe = find_openscad(args.openscad)

    total_cases = 0

    fmt_ok = 0

    strict_compile_ok = 0
    lenient_compile_ok = 0
    best_compile_ok = 0

    strict_bounds_ok = 0
    lenient_bounds_ok = 0
    best_bounds_ok = 0

    strict_vol_ok = 0
    lenient_vol_ok = 0
    best_vol_ok = 0

    strict_area_ok = 0
    lenient_area_ok = 0
    best_area_ok = 0

    per_cat: Dict[str, Dict[str, int]] = {}

    with tempfile.TemporaryDirectory(prefix="cadbench_stl_") as tmpd:
        tmpd = Path(tmpd)

        for item in data:
            ex_id = item["id"]
            cat = item.get("category", "unknown")
            per_cat.setdefault(cat, {"cases": 0, "fmt": 0,
                                     "strict_c": 0, "lenient_c": 0, "best_c": 0,
                                     "strict_b": 0, "lenient_b": 0, "best_b": 0,
                                     "strict_v": 0, "lenient_v": 0, "best_v": 0,
                                     "strict_a": 0, "lenient_a": 0, "best_a": 0})
            scad_path = scad_dir / f"{ex_id}.scad"
            raw = scad_path.read_text(encoding="utf-8", errors="ignore") if scad_path.exists() else ""

            cases = (item.get("eval") or {}).get("cases") or []
            tol = (item.get("eval") or {}).get("tol") or {}
            tol_bounds = float(tol.get("bounds_abs", 0.25))
            tol_vol = float(tol.get("volume_frac", 0.05))
            tol_area = float(tol.get("area_frac", 0.05))

            for case in cases:
                total_cases += 1
                per_cat[cat]["cases"] += 1

                defines = (case.get("defines") or {})
                cli_vars = list(defines.keys())

                # format compliance is checked on RAW
                fmt = format_compliant_scad(raw, cli_vars)
                if fmt:
                    fmt_ok += 1
                    per_cat[cat]["fmt"] += 1

                clean = sanitize_scad(raw, cli_vars)

                # write temp scad for lenient run
                strict_scad = scad_path
                lenient_scad = tmpd / f"{ex_id}__{case['name']}__clean.scad"
                lenient_scad.write_text(clean, encoding="utf-8")

                # expected metrics
                expect = (case.get("expect") or {})
                exp_bounds = expect.get("bounds")
                exp_vol = expect.get("volume")
                exp_area = expect.get("area")  # OPTIONAL: surface area

                # run strict
                strict_stl = tmpd / f"{ex_id}__{case['name']}__strict.stl"
                ok_s, err_s = run_openscad(openscad_exe, strict_scad, strict_stl, defines, args.timeout_s)

                sb = sv = sa = False
                if ok_s and exp_bounds is not None and exp_vol is not None:
                    verts, faces = parse_stl(strict_stl)
                    (mnx, mny, mnz), (mxx, mxy, mxz) = bounds_from_verts(verts)
                    got_bounds = [mxx - mnx, mxy - mny, mxz - mnz]
                    got_vol, got_area = volume_and_area(verts, faces)

                    sb = close_enough_bounds(got_bounds, exp_bounds, tol_bounds)
                    sv = close_enough_frac(got_vol, exp_vol, tol_vol)
                    sa = True if exp_area is None else close_enough_frac(got_area, exp_area, tol_area)

                # run lenient
                lenient_stl = tmpd / f"{ex_id}__{case['name']}__lenient.stl"
                ok_l, err_l = run_openscad(openscad_exe, lenient_scad, lenient_stl, defines, args.timeout_s)

                lb = lv = la = False
                if ok_l and exp_bounds is not None and exp_vol is not None:
                    verts, faces = parse_stl(lenient_stl)
                    (mnx, mny, mnz), (mxx, mxy, mxz) = bounds_from_verts(verts)
                    got_bounds = [mxx - mnx, mxy - mny, mxz - mnz]
                    got_vol, got_area = volume_and_area(verts, faces)

                    lb = close_enough_bounds(got_bounds, exp_bounds, tol_bounds)
                    lv = close_enough_frac(got_vol, exp_vol, tol_vol)
                    la = True if exp_area is None else close_enough_frac(got_area, exp_area, tol_area)

                # choose best per metric set
                def score_tuple(c_ok, b_ok, v_ok, a_ok) -> Tuple[int,int,int,int]:
                    return (1 if c_ok else 0, 1 if b_ok else 0, 1 if v_ok else 0, 1 if a_ok else 0)

                if args.mode == "strict":
                    best = (ok_s, sb, sv, sa)
                elif args.mode == "lenient":
                    best = (ok_l, lb, lv, la)
                else:
                    best = (ok_s, sb, sv, sa)
                    if score_tuple(ok_l, lb, lv, la) > score_tuple(ok_s, sb, sv, sa):
                        best = (ok_l, lb, lv, la)

                # aggregate
                if ok_s:
                    strict_compile_ok += 1; per_cat[cat]["strict_c"] += 1
                if ok_l:
                    lenient_compile_ok += 1; per_cat[cat]["lenient_c"] += 1
                if best[0]:
                    best_compile_ok += 1; per_cat[cat]["best_c"] += 1

                if sb:
                    strict_bounds_ok += 1; per_cat[cat]["strict_b"] += 1
                if lb:
                    lenient_bounds_ok += 1; per_cat[cat]["lenient_b"] += 1
                if best[1]:
                    best_bounds_ok += 1; per_cat[cat]["best_b"] += 1

                if sv:
                    strict_vol_ok += 1; per_cat[cat]["strict_v"] += 1
                if lv:
                    lenient_vol_ok += 1; per_cat[cat]["lenient_v"] += 1
                if best[2]:
                    best_vol_ok += 1; per_cat[cat]["best_v"] += 1

                if sa:
                    strict_area_ok += 1; per_cat[cat]["strict_a"] += 1
                if la:
                    lenient_area_ok += 1; per_cat[cat]["lenient_a"] += 1
                if best[3]:
                    best_area_ok += 1; per_cat[cat]["best_a"] += 1

                # print failures only when needed
                if not ok_s and err_s:
                    print(f"FAIL_STRICT_COMPILE {ex_id} case={case['name']} cat={cat}\n{err_s}\n")
                if not ok_l and err_l:
                    print(f"FAIL_LENIENT_COMPILE {ex_id} case={case['name']} cat={cat}\n{err_l}\n")

        def pct(x: int) -> float:
            return 0.0 if total_cases == 0 else 100.0 * x / total_cases

        print(f"=== CADBENCH SCORE (Option C, mode={args.mode}) ===")
        print(f"Total cases:        {total_cases}")
        print(f"Format compliance:  {fmt_ok}/{total_cases} ({pct(fmt_ok):.1f}%)")
        print("")
        print(f"Strict compile:     {strict_compile_ok}/{total_cases} ({pct(strict_compile_ok):.1f}%)")
        print(f"Lenient compile:    {lenient_compile_ok}/{total_cases} ({pct(lenient_compile_ok):.1f}%)")
        print(f"Best compile:       {best_compile_ok}/{total_cases} ({pct(best_compile_ok):.1f}%)")
        print("")
        print(f"Strict bounds:      {strict_bounds_ok}/{total_cases} ({pct(strict_bounds_ok):.1f}%)")
        print(f"Lenient bounds:     {lenient_bounds_ok}/{total_cases} ({pct(lenient_bounds_ok):.1f}%)")
        print(f"Best bounds:        {best_bounds_ok}/{total_cases} ({pct(best_bounds_ok):.1f}%)")
        print("")
        print(f"Strict volume:      {strict_vol_ok}/{total_cases} ({pct(strict_vol_ok):.1f}%)")
        print(f"Lenient volume:     {lenient_vol_ok}/{total_cases} ({pct(lenient_vol_ok):.1f}%)")
        print(f"Best volume:        {best_vol_ok}/{total_cases} ({pct(best_vol_ok):.1f}%)")
        print("")
        print(f"Strict area:        {strict_area_ok}/{total_cases} ({pct(strict_area_ok):.1f}%)")
        print(f"Lenient area:       {lenient_area_ok}/{total_cases} ({pct(lenient_area_ok):.1f}%)")
        print(f"Best area:          {best_area_ok}/{total_cases} ({pct(best_area_ok):.1f}%)")
        print("\nBy category:")
        for cat, d in per_cat.items():
            n = d["cases"]
            if n == 0:
                continue
            def p(x): return 100.0 * x / n
            print(
                f"- {cat:26} cases={n:2d} "
                f"fmt={p(d['fmt']):5.1f}% "
                f"strictC={p(d['strict_c']):5.1f}% lenC={p(d['lenient_c']):5.1f}% bestC={p(d['best_c']):5.1f}% "
                f"bestB={p(d['best_b']):5.1f}% bestV={p(d['best_v']):5.1f}% bestA={p(d['best_a']):5.1f}%"
            )

if __name__ == "__main__":
    main()
