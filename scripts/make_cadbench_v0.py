import json
from pathlib import Path

OUT = Path("data/cadbench_v0.jsonl")

def item(_id, category, prompt, cases):
    return {
        "id": _id,
        "category": category,
        "prompt": prompt,
        "eval": {
            "cases": cases,
            # global tolerances (you can override per-case later)
            "tol": {"bounds_abs": 0.25, "volume_frac": 0.05},
        },
    }

def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)

    SYS = (
        "You are an OpenSCAD code generator.\n"
        "Output ONLY valid OpenSCAD code. No markdown, no code fences, no explanations.\n"
        "Do not output `null`. Do not wrap in JSON.\n"
    )

    items = []

    items.append(item(
        "cad_v0_001",
        "primitive_cube_centered",
        SYS + "\nTask: Create a solid cube sized [20, 30, 10] millimeters, centered at the origin.\n"
              "Requirements:\n- Use millimeters.\n- Ensure the solid is centered.\n- No extra geometry.\n",
        cases=[{
            "name": "default",
            "defines": {},
            "expect": {"bounds": [20, 30, 10], "volume": 20*30*10},
        }]
    ))

    items.append(item(
        "cad_v0_002",
        "primitive_cylinder_centered",
        SYS + "\nTask: Create a solid cylinder with radius 7 and height 40, centered at origin.\n"
              "Requirements:\n- Cylinder axis along Z.\n- Centered (so z spans -20..+20).\n",
        cases=[{
            "name": "default",
            "defines": {},
            "expect": {"bounds": [14, 14, 40], "volume": 3.141592653589793*(7**2)*40},
        }]
    ))

    items.append(item(
        "cad_v0_003",
        "boolean_plate_hole",
        SYS + "\nTask: Create a plate: a cube [60, 40, 6] centered at origin, with ONE through-hole.\n"
              "Hole: cylinder radius 5, axis along Z, centered at origin, goes fully through.\n"
              "No extra holes.\n",
        cases=[{
            "name": "default",
            "defines": {},
            "expect": {
                "bounds": [60, 40, 6],
                "volume": (60*40*6) - (3.141592653589793*(5**2)*6),
            },
        }]
    ))

    items.append(item(
        "cad_v0_004",
        "parametric_box_module",
        SYS + "\nTask: Write a module `part(w, d, h)` that creates a centered box of size [w,d,h].\n"
              "Then call it ONCE using variables W,D,H (so we can override them via CLI).\n"
              "Rules:\n- Must use parameters, not hard-coded numbers.\n- Centered at origin.\n",
        cases=[
            {"name": "A", "defines": {"W": 20, "D": 20, "H": 20}, "expect": {"bounds": [20, 20, 20], "volume": 8000}},
            {"name": "B", "defines": {"W": 50, "D": 10, "H": 5},  "expect": {"bounds": [50, 10, 5],  "volume": 2500}},
            {"name": "C", "defines": {"W": 33, "D": 27, "H": 9},  "expect": {"bounds": [33, 27, 9],  "volume": 8019}},
        ]
    ))

    items.append(item(
        "cad_v0_005",
        "parametric_hole_plate",
        SYS + "\nTask: Create a centered plate [W, D, T] with ONE centered through-hole of radius R.\n"
              "Use variables W,D,T,R (override via CLI).\n"
              "Axis: Z. Hole must fully pass through.\n",
        cases=[
            {"name": "A", "defines": {"W": 60, "D": 40, "T": 6, "R": 5},
             "expect": {"bounds": [60, 40, 6], "volume": (60*40*6) - (3.141592653589793*(5**2)*6)}},
            {"name": "B", "defines": {"W": 80, "D": 20, "T": 4, "R": 3},
             "expect": {"bounds": [80, 20, 4], "volume": (80*20*4) - (3.141592653589793*(3**2)*4)}},
        ]
    ))

    # Write jsonl
    with OUT.open("w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")

    print(f"Wrote {OUT} with {len(items)} items")

if __name__ == "__main__":
    main()
