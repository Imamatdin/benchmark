import json
import math
from pathlib import Path

OUT = Path("data/cadbench_v1.jsonl")
GOLD_DIR = Path("gold_scad")

SYS = (
    "You are an OpenSCAD code generator.\n"
    "Output ONLY valid OpenSCAD code. No markdown, no code fences, no explanations.\n"
    "Do not output `null`. Do not wrap in JSON.\n"
    "Calculate expected bounds/volume/area mathematically. Reference gold_scad/ examples for correct OpenSCAD syntax.\n"
)


def item(_id, category, prompt, cases, scad_src):
    return {
        "id": _id,
        "category": category,
        "prompt": prompt,
        "eval": {
            "cases": cases,
            "tol": {"bounds_abs": 0.25, "volume_frac": 0.05},
        },
        "scad": scad_src,
    }


def sphere_volume(r: float) -> float:
    return (4.0 / 3.0) * math.pi * (r ** 3)


def cone_volume(r1: float, r2: float, h: float) -> float:
    return (math.pi * h * (r1 * r1 + r1 * r2 + r2 * r2)) / 3.0


def bracket_volume(w: float, h: float, t: float) -> float:
    return t * t * (w + h - t)


def offset_box_volume(l: float, w: float, h: float, r: float) -> float:
    surface_area = 2 * (l * w + l * h + w * h)
    mean_curvature = 4 * (l + w + h)
    return (l * w * h) + surface_area * r + mean_curvature * (r ** 2) + (4.0 / 3.0) * math.pi * (r ** 3)


def slot_volume(r: float, spacing: float, height: float) -> float:
    return (math.pi * (r ** 2) + 2 * r * spacing) * height


def write_jsonl(items):
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for it in items:
            data = dict(it)
            data.pop("scad", None)
            f.write(json.dumps(data, ensure_ascii=False) + "\n")
    print(f"Wrote {OUT} with {len(items)} prompts")


def write_gold(items):
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    for it in items:
        scad = it.get("scad", "").strip() + "\n"
        path = GOLD_DIR / f"{it['id']}.scad"
        path.write_text(scad, encoding="utf-8")
    print(f"Wrote {len(items)} gold .scad files to {GOLD_DIR}")


def main():
    items = []
    idx = 1

    # 1) primitive_sphere
    sphere_specs = [6, 10, 4, 12, 7]
    for r in sphere_specs:
        prompt = (
            SYS
            + f"Category: primitive_sphere. Create a centered solid sphere of radius {r} millimeters.\n"
            + "No extra geometry or modifiers.\n"
        )
        cases = [{
            "name": "default",
            "defines": {},
            "expect": {
                "bounds": [2 * r, 2 * r, 2 * r],
                "volume": sphere_volume(r),
            },
        }]
        scad_src = f"sphere(r={r});"
        items.append(item(f"cad_v1_{idx:03d}", "primitive_sphere", prompt, cases, scad_src))
        idx += 1

    # 2) primitive_cone
    cone_specs = [
        (8, 4, 30),
        (10, 3, 18),
        (6, 12, 26),
        (5, 5, 22),
        (9, 2, 16),
    ]
    for r1, r2, h in cone_specs:
        prompt = (
            SYS
            + "Category: primitive_cone. Create a centered cone (use cylinder with r1, r2, h) aligned to Z.\n"
            + f"Use r1={r1}, r2={r2}, height={h}. Center it at the origin.\n"
        )
        bounds_xy = 2 * max(r1, r2)
        cases = [{
            "name": "default",
            "defines": {},
            "expect": {
                "bounds": [bounds_xy, bounds_xy, h],
                "volume": cone_volume(r1, r2, h),
            },
        }]
        scad_src = f"cylinder(h={h}, r1={r1}, r2={r2}, center=true);"
        items.append(item(f"cad_v1_{idx:03d}", "primitive_cone", prompt, cases, scad_src))
        idx += 1

    # 3) boolean_union (disjoint shapes, volumes add)
    union_specs = [
        {
            "cube": ([20, 14, 10], [0, 0, 0]),
            "sphere": (6, [18, 0, 0]),
        },
        {
            "cylinder": ((5, 5, 18), [0, 0, 0]),
            "cube": ([12, 30, 14], [-20, 0, 0]),
        },
        {
            "cube": ([16, 16, 16], [0, 0, 0]),
            "cube2": ([10, 22, 8], [20, 0, 0]),
        },
        {
            "cone": ((8, 4, 20), [0, 0, 0]),
            "cube": ([18, 12, 8], [0, 18, 0]),
        },
        {
            "sphere": (5, [0, 0, 0]),
            "cylinder": ((4, 4, 14), [0, 0, 18]),
        },
    ]
    for spec in union_specs:
        cube1 = spec.get("cube")
        cube2 = spec.get("cube2")
        sphere = spec.get("sphere")
        cylinder = spec.get("cylinder")
        cone = spec.get("cone")

        min_x = min_y = min_z = float("inf")
        max_x = max_y = max_z = float("-inf")
        volume = 0.0

        scad_parts = []

        if cube1:
            size, pos = cube1
            hx, hy, hz = [s / 2 for s in size]
            cx, cy, cz = pos
            min_x = min(min_x, cx - hx)
            max_x = max(max_x, cx + hx)
            min_y = min(min_y, cy - hy)
            max_y = max(max_y, cy + hy)
            min_z = min(min_z, cz - hz)
            max_z = max(max_z, cz + hz)
            volume += size[0] * size[1] * size[2]
            scad_parts.append(f"translate([{cx}, {cy}, {cz}]) cube([{size[0]}, {size[1]}, {size[2]}], center=true);")

        if cube2:
            size, pos = cube2
            hx, hy, hz = [s / 2 for s in size]
            cx, cy, cz = pos
            min_x = min(min_x, cx - hx)
            max_x = max(max_x, cx + hx)
            min_y = min(min_y, cy - hy)
            max_y = max(max_y, cy + hy)
            min_z = min(min_z, cz - hz)
            max_z = max(max_z, cz + hz)
            volume += size[0] * size[1] * size[2]
            scad_parts.append(f"translate([{cx}, {cy}, {cz}]) cube([{size[0]}, {size[1]}, {size[2]}], center=true);")

        if sphere:
            r, pos = sphere
            cx, cy, cz = pos
            min_x = min(min_x, cx - r)
            max_x = max(max_x, cx + r)
            min_y = min(min_y, cy - r)
            max_y = max(max_y, cy + r)
            min_z = min(min_z, cz - r)
            max_z = max(max_z, cz + r)
            volume += sphere_volume(r)
            scad_parts.append(f"translate([{cx}, {cy}, {cz}]) sphere(r={r});")

        if cylinder:
            (r1, r2, h), pos = cylinder
            cx, cy, cz = pos
            rmax = max(r1, r2)
            min_x = min(min_x, cx - rmax)
            max_x = max(max_x, cx + rmax)
            min_y = min(min_y, cy - rmax)
            max_y = max(max_y, cy + rmax)
            min_z = min(min_z, cz - h / 2)
            max_z = max(max_z, cz + h / 2)
            volume += cone_volume(r1, r2, h)
            scad_parts.append(f"translate([{cx}, {cy}, {cz}]) cylinder(h={h}, r1={r1}, r2={r2}, center=true);")

        if cone:
            (r1, r2, h), pos = cone
            cx, cy, cz = pos
            rmax = max(r1, r2)
            min_x = min(min_x, cx - rmax)
            max_x = max(max_x, cx + rmax)
            min_y = min(min_y, cy - rmax)
            max_y = max(max_y, cy + rmax)
            min_z = min(min_z, cz - h / 2)
            max_z = max(max_z, cz + h / 2)
            volume += cone_volume(r1, r2, h)
            scad_parts.append(f"translate([{cx}, {cy}, {cz}]) cylinder(h={h}, r1={r1}, r2={r2}, center=true);")

        bounds = [max_x - min_x, max_y - min_y, max_z - min_z]
        desc_parts = []
        if cube1:
            desc_parts.append(f"Cube size {cube1[0]} at {cube1[1]}")
        if cube2:
            desc_parts.append(f"Cube size {cube2[0]} at {cube2[1]}")
        if sphere:
            desc_parts.append(f"Sphere r={sphere[0]} at {sphere[1]}")
        if cylinder:
            desc_parts.append(f"Cylinder (r1,r2,h)=({cylinder[0][0]},{cylinder[0][1]},{cylinder[0][2]}) at {cylinder[1]}")
        if cone and not cylinder:
            desc_parts.append(f"Cone (r1,r2,h)=({cone[0][0]},{cone[0][1]},{cone[0][2]}) at {cone[1]}")
        prompt = (
            SYS
            + "Category: boolean_union. Create a union of two primitives using the specified dimensions and translations.\n"
            + "Place each primitive exactly once with the listed transforms: "
            + "; ".join(desc_parts)
            + ".\n"
            + "Ensure no extra copies or stray geometry.\n"
        )
        cases = [{"name": "default", "defines": {}, "expect": {"bounds": bounds, "volume": volume}}]
        scad_src = "union(){\n  " + "\n  ".join(scad_parts) + "\n}"
        items.append(item(f"cad_v1_{idx:03d}", "boolean_union", prompt, cases, scad_src))
        idx += 1

    # 4) boolean_intersection (inner shape fully contained)
    intersection_specs = [
        {"outer_cube": [24, 24, 24], "inner_cylinder": (10, 10, 24)},
        {"outer_cube": [30, 18, 18], "inner_sphere": 8},
        {"outer_cylinder": (10, 10, 30), "inner_cylinder": (6, 6, 30)},
        {"outer_cube": [28, 16, 12], "inner_cylinder": (6, 6, 12)},
        {"outer_cube": [30, 30, 26], "inner_cone": (9, 4, 26)},
    ]
    for spec in intersection_specs:
        prompt = (
            SYS
            + "Category: boolean_intersection. Keep only the shared volume of the primitives.\n"
            + "Center everything at origin and avoid extra geometry.\n"
        )
        volume = 0.0
        bounds = [0, 0, 0]
        scad_parts = []

        if spec.get("outer_cube"):
            size = spec["outer_cube"]
            scad_parts.append(f"cube([{size[0]}, {size[1]}, {size[2]}], center=true)")
        if spec.get("outer_cylinder"):
            r1, r2, h = spec["outer_cylinder"]
            scad_parts.append(f"cylinder(h={h}, r1={r1}, r2={r2}, center=true)")

        if spec.get("inner_cylinder"):
            r1, r2, h = spec["inner_cylinder"]
            volume = cone_volume(r1, r2, h)
            bounds = [2 * max(r1, r2), 2 * max(r1, r2), h]
            scad_parts.append(f"cylinder(h={h}, r1={r1}, r2={r2}, center=true)")
        elif spec.get("inner_sphere"):
            r = spec["inner_sphere"]
            volume = sphere_volume(r)
            bounds = [2 * r, 2 * r, 2 * r]
            scad_parts.append(f"sphere(r={r})")
        elif spec.get("inner_cone"):
            r1, r2, h = spec["inner_cone"]
            volume = cone_volume(r1, r2, h)
            bounds = [2 * max(r1, r2), 2 * max(r1, r2), h]
            scad_parts.append(f"cylinder(h={h}, r1={r1}, r2={r2}, center=true)")

        cases = [{"name": "default", "defines": {}, "expect": {"bounds": bounds, "volume": volume}}]
        scad_src = "intersection(){\n  " + ";\n  ".join(scad_parts) + ";\n}"
        items.append(item(f"cad_v1_{idx:03d}", "boolean_intersection", prompt, cases, scad_src))
        idx += 1

    # 5) transform_translate
    translate_specs = [
        ("cube", {"size": [12, 10, 8], "offset": [15, -5, 3]}),
        ("cylinder", {"r": 6, "h": 20, "offset": [-12, 8, -6]}),
        ("sphere", {"r": 9, "offset": [5, 10, 0]}),
        ("cone", {"r1": 5, "r2": 10, "h": 18, "offset": [-20, 0, 12]}),
        ("cube", {"size": [16, 24, 6], "offset": [0, -14, -4]}),
    ]
    for shape, cfg in translate_specs:
        prompt = (
            SYS
            + "Category: transform_translate. Translate the primitive by the given offset without altering its size.\n"
            + f"Offset: {cfg['offset']} (millimeters).\n"
        )
        if shape == "cube":
            size = cfg["size"]
            bounds = size
            volume = size[0] * size[1] * size[2]
            scad_src = f"translate([{cfg['offset'][0]}, {cfg['offset'][1]}, {cfg['offset'][2]}]) cube([{size[0]}, {size[1]}, {size[2]}], center=true);"
        elif shape == "cylinder":
            r = cfg["r"]
            h = cfg["h"]
            bounds = [2 * r, 2 * r, h]
            volume = math.pi * (r ** 2) * h
            scad_src = f"translate([{cfg['offset'][0]}, {cfg['offset'][1]}, {cfg['offset'][2]}]) cylinder(r={r}, h={h}, center=true);"
        elif shape == "sphere":
            r = cfg["r"]
            bounds = [2 * r, 2 * r, 2 * r]
            volume = sphere_volume(r)
            scad_src = f"translate([{cfg['offset'][0]}, {cfg['offset'][1]}, {cfg['offset'][2]}]) sphere(r={r});"
        elif shape == "cone":
            r1 = cfg["r1"]
            r2 = cfg["r2"]
            h = cfg["h"]
            bounds = [2 * max(r1, r2), 2 * max(r1, r2), h]
            volume = cone_volume(r1, r2, h)
            scad_src = f"translate([{cfg['offset'][0]}, {cfg['offset'][1]}, {cfg['offset'][2]}]) cylinder(h={h}, r1={r1}, r2={r2}, center=true);"
        else:
            raise ValueError("unknown shape")

        cases = [{"name": "default", "defines": {}, "expect": {"bounds": bounds, "volume": volume}}]
        items.append(item(f"cad_v1_{idx:03d}", "transform_translate", prompt, cases, scad_src))
        idx += 1

    # 6) transform_rotate
    rotate_specs = [
        {"shape": "cube", "size": [10, 18, 6], "rot": [0, 0, 90]},
        {"shape": "cylinder", "r": 5, "h": 20, "rot": [90, 0, 0]},
        {"shape": "cube", "size": [8, 14, 22], "rot": [0, 90, 0]},
        {"shape": "cube", "size": [12, 30, 10], "rot": [0, 0, 180]},
        {"shape": "cylinder", "r": 4, "h": 12, "rot": [0, 90, 0]},
    ]
    for spec in rotate_specs:
        prompt = (
            SYS
            + "Category: transform_rotate. Apply the specified rotation in degrees, keeping geometry centered.\n"
            + f"Rotation: {spec['rot']} (XYZ Euler).\n"
        )
        if spec["shape"] == "cube":
            x, y, z = spec["size"]
            rot = spec["rot"]
            if rot == [0, 0, 90] or rot == [0, 0, 270]:
                bounds = [y, x, z]
            elif rot == [0, 90, 0] or rot == [0, 270, 0]:
                bounds = [z, y, x]
            else:
                bounds = [x, y, z]
            volume = x * y * z
            scad_src = f"rotate([{rot[0]}, {rot[1]}, {rot[2]}]) cube([{x}, {y}, {z}], center=true);"
        else:
            r = spec["r"]
            h = spec["h"]
            rot = spec["rot"]
            # Cylinder dimensions are invariant to 90-degree rotations of orthogonal axes
            if rot in ([90, 0, 0], [0, 90, 0]):
                bounds = [h, 2 * r, 2 * r]
            else:
                bounds = [2 * r, 2 * r, h]
            volume = math.pi * (r ** 2) * h
            scad_src = f"rotate([{rot[0]}, {rot[1]}, {rot[2]}]) cylinder(r={r}, h={h}, center=true);"

        cases = [{"name": "default", "defines": {}, "expect": {"bounds": bounds, "volume": volume}}]
        items.append(item(f"cad_v1_{idx:03d}", "transform_rotate", prompt, cases, scad_src))
        idx += 1

    # 7) parametric_bracket
    bracket_case_sets = [
        [("A", 40, 30, 4), ("B", 60, 50, 5), ("C", 25, 35, 3)],
        [("A", 70, 40, 6), ("B", 45, 55, 4), ("C", 32, 28, 3)],
        [("A", 55, 60, 5), ("B", 80, 45, 6), ("C", 36, 48, 4)],
        [("A", 65, 35, 5), ("B", 50, 70, 6), ("C", 42, 42, 4)],
        [("A", 90, 50, 7), ("B", 58, 62, 5), ("C", 48, 36, 4)],
    ]
    bracket_scad = (
        "module bracket(w, h, t){\n"
        "  union(){\n"
        "    cube([w, t, t]);\n"
        "    cube([t, h, t]);\n"
        "  }\n"
        "}\n"
        "bracket(W, H, T);"
    )
    for cases_in_set in bracket_case_sets:
        prompt = (
            SYS
            + "Category: parametric_bracket. Model an L-bracket defined by width W, height H, thickness T.\n"
            + "Use modules and the provided variables so CLI -D overrides work.\n"
        )
        cases = []
        for name, w, h, t in cases_in_set:
            cases.append({
                "name": name,
                "defines": {"W": w, "H": h, "T": t},
                "expect": {"bounds": [w, h, t], "volume": bracket_volume(w, h, t)},
            })
        items.append(item(f"cad_v1_{idx:03d}", "parametric_bracket", prompt, cases, bracket_scad))
        idx += 1

    # 8) multi_hole_plate
    plate_case_sets = [
        {
            "holes": [([0.25, 0.25], 4), ([-0.25, -0.25], 3)],
            "cases": [("A", 80, 50, 6), ("B", 60, 40, 5)],
        },
        {
            "holes": [([0.3, -0.3], 5), ([-0.3, 0.3], 5), ([0, 0], 2.5)],
            "cases": [("A", 90, 60, 6), ("B", 70, 50, 5)],
        },
        {
            "holes": [([0.35, 0], 4.5), ([-0.35, 0], 4.5)],
            "cases": [("A", 100, 40, 6), ("B", 80, 30, 5)],
        },
        {
            "holes": [([0.25, 0.0], 3.5), ([0.0, 0.25], 3.5), ([-0.25, 0], 3.5), ([0, -0.25], 3.5)],
            "cases": [("A", 70, 70, 6), ("B", 60, 60, 5)],
        },
        {
            "holes": [([0.2, 0.2], 4), ([-0.2, 0.2], 4), ([0.2, -0.2], 4), ([-0.2, -0.2], 4)],
            "cases": [("A", 80, 80, 6), ("B", 64, 64, 5)],
        },
    ]
    for plate_set in plate_case_sets:
        prompt = (
            SYS
            + "Category: multi_hole_plate. Create a centered plate [W, D, T] with through-holes at specified offsets.\n"
            + "Hole coordinates are fractions of W and D (e.g., 0.25 means W*0.25 from center).\n"
        )
        holes = plate_set["holes"]
        cases = []
        for name, w, d, t in plate_set["cases"]:
            total_hole_volume = 0.0
            for (hx_frac, hy_frac), r in holes:
                total_hole_volume += math.pi * (r ** 2) * t
            cases.append({
                "name": name,
                "defines": {"W": w, "D": d, "T": t},
                "expect": {"bounds": [w, d, t], "volume": (w * d * t) - total_hole_volume},
            })
        hole_lines = []
        for (hx_frac, hy_frac), r in holes:
            hole_lines.append(
                f"    translate([w*{hx_frac}, d*{hy_frac}, 0]) cylinder(r={r}, h=t+2, center=true);"
            )
        scad_src = (
            "module plate(w, d, t){\n"
            "  difference(){\n"
            "    cube([w, d, t], center=true);\n"
            + "\n".join(hole_lines)
            + "\n  }\n}\\n"
            "plate(W, D, T);"
        )
        scad_src = scad_src.replace("\\n", "\n")
        items.append(item(f"cad_v1_{idx:03d}", "multi_hole_plate", prompt, cases, scad_src))
        idx += 1

    # 9) slot_plate
    slot_case_sets = [
        ("A", [80, 40, 6], 12, 6, [("A", 80, 40, 6, 12, 6), ("B", 70, 36, 5, 10, 5.5)]),
        ("B", [90, 50, 6], 16, 7, [("A", 90, 50, 6, 16, 7), ("B", 72, 44, 5, 12, 6)]),
        ("C", [70, 60, 5], 18, 5, [("A", 70, 60, 5, 18, 5), ("B", 64, 52, 5, 14, 4.5)]),
        ("D", [100, 50, 6], 20, 6, [("A", 100, 50, 6, 20, 6), ("B", 84, 44, 5, 16, 5)]),
        ("E", [60, 60, 5], 14, 5, [("A", 60, 60, 5, 14, 5), ("B", 54, 48, 5, 12, 4.5)]),
    ]
    for _, base_size, spacing, radius, cases_raw in slot_case_sets:
        prompt = (
            SYS
            + "Category: slot_plate. Create a centered plate and cut a slot formed by the hull of two cylinders.\n"
            + "Place cylinder centers along X separated by SLOT, using radius R.\n"
        )
        cases = []
        for name, w, d, t, slot_len, r in cases_raw:
            base_volume = w * d * t
            removal = slot_volume(r, slot_len, t)
            cases.append({
                "name": name,
                "defines": {"W": w, "D": d, "T": t, "SLOT": slot_len, "R": r},
                "expect": {"bounds": [w, d, t], "volume": base_volume - removal},
            })
        scad_src = (
            "module slot_plate(w, d, t, slot_len, r){\n"
            "  difference(){\n"
            "    cube([w, d, t], center=true);\n"
            "    hull(){\n"
            "      translate([slot_len/2, 0, 0]) cylinder(r=r, h=t+2, center=true);\n"
            "      translate([-slot_len/2, 0, 0]) cylinder(r=r, h=t+2, center=true);\n"
            "    }\n"
            "  }\n"
            "}\n"
            "slot_plate(W, D, T, SLOT, R);"
        )
        items.append(item(f"cad_v1_{idx:03d}", "slot_plate", prompt, cases, scad_src))
        idx += 1

    # 10) fillet_box using minkowski
    fillet_case_sets = [
        [("A", 40, 30, 20, 2.5), ("B", 48, 36, 24, 3.0)],
        [("A", 60, 40, 22, 3.0), ("B", 72, 44, 26, 3.5)],
        [("A", 50, 50, 18, 2.0), ("B", 64, 64, 24, 2.5)],
        [("A", 70, 30, 16, 2.5), ("B", 84, 36, 20, 3.0)],
        [("A", 90, 60, 28, 3.5), ("B", 76, 52, 24, 3.0)],
    ]
    fillet_scad = (
        "module fillet_box(l, w, h, r){\n"
        "  minkowski(){\n"
        "    cube([l, w, h], center=true);\n"
        "    sphere(r=r);\n"
        "  }\n"
        "}\n"
        "fillet_box(L, W, H, R);"
    )
    for case_set in fillet_case_sets:
        prompt = (
            SYS
            + "Category: fillet_box. Build a rounded box via minkowski() of a cube [L,W,H] with a sphere radius R.\n"
            + "Do not add extra geometry beyond the Minkowski sum.\n"
        )
        cases = []
        for name, l, w, h, r in case_set:
            cases.append({
                "name": name,
                "defines": {"L": l, "W": w, "H": h, "R": r},
                "expect": {
                    "bounds": [l + 2 * r, w + 2 * r, h + 2 * r],
                    "volume": offset_box_volume(l, w, h, r),
                },
            })
        items.append(item(f"cad_v1_{idx:03d}", "fillet_box", prompt, cases, fillet_scad))
        idx += 1

    write_jsonl(items)
    write_gold(items)


if __name__ == "__main__":
    main()
