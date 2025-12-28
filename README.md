# CADBench

CADBench is a lightweight benchmark for evaluating how reliably language models can produce **valid, geometric-accurate OpenSCAD**. It emphasizes format compliance, correct boolean operations, and robustness to parametric overrides rather than raw text similarity.

## Why it matters
- LLMs often emit malformed OpenSCAD (markdown fences, trailing garbage) that fails to parse.
- Correct parametric behavior is critical: CLI `-D` overrides must propagate without the model re-defining the variables.
- Geometric fidelity (bounds, volume, area) matters for downstream CAD/CAM workflows, not just compilability.

## Quick start
1. Install dependencies:
   ```bash
   python -m venv .venv && source .venv/bin/activate  # or use your preferred environment
   pip install -r requirements.txt
   ```
2. Point to OpenSCAD (defaults to `openscad` on PATH). On Windows, for example:
   ```bash
   set OPENSCAD_EXE="C:\Program Files\OpenSCAD\openscad.exe"
   ```
3. Generate the CADBench v1 dataset and gold geometries:
   ```bash
   python scripts/make_cadbench_v1.py
   ```
4. Run an evaluation (produces raw model outputs in `out_scad_raw/`):
   ```bash
   python src/run_eval.py
   ```
5. Clean/sanitize the outputs and extract OpenSCAD:
   ```bash
   python scripts/extract_scad.py
   ```
6. Score against the gold geometries:
   ```bash
   python scripts/score_cadbench.py
   ```

## Metrics
- **Format compliance**: plain OpenSCAD only (no markdown/preamble).
- **Compile**: OpenSCAD must parse and export.
- **Bounds match**: axis-aligned bounding box within tolerance (`bounds_abs`).
- **Volume match**: solid volume within fractional tolerance (`volume_frac`).
- **Area match**: (when provided) 2D/planar area agreement.

## Example output
```
{"id": "cad_v1_001", "category": "primitive_sphere", "format_ok": true, "compiled": true, "bounds_ok": true, "volume_ok": true, "area_ok": true}
```

## License

MIT
