# SynCAD

AI-powered CAD code generation with validation. Describe parts in plain English, get manufacturable STL files in seconds.

## Quick Demo
```bash
# Set OpenSCAD path (Windows)
$env:OPENSCAD_EXE="C:\Program Files\OpenSCAD\openscad.exe"

# Run the agent
python cad_agent.py
```

Then type:
```
A mounting bracket: L-shape, 60mm wide, 40mm tall, 5mm thick, with two 4mm holes
```

## What it does

1. **Natural language → OpenSCAD code** via LLM (Groq/Gemini)
2. **Automatic validation** - compiles with OpenSCAD, catches errors
3. **Retry on failure** - feeds error back to LLM for correction
4. **Outputs STL** - ready for 3D printing or manufacturing

## CADBench

Included benchmark for evaluating LLM-generated CAD:

- **Format compliance** - clean code output (no markdown, no preamble)
- **Compilation** - OpenSCAD parses without errors
- **Geometric accuracy** - bounds, volume, surface area match expected
- **Parametric robustness** - CLI `-D` overrides work correctly
```bash
python -m scripts.score_cadbench --data data/cadbench_v0.jsonl --scad_dir out_scad_raw --mode best
```

## Setup
```bash
pip install -r requirements.txt
```

Add to `.env`:
```
GROQ_API_KEY=your_key_here
```

## Examples

| Prompt | Result |
|--------|--------|
| "A cube 30x30x30mm centered at origin" | ✓ Compiled |
| "A plate 80x50x5mm with 10mm hole in center" | ✓ Compiled |
| "L-bracket with mounting holes" | ✓ Compiled |
| "Gear with 8 holes around perimeter" | ✓ Compiled |

## License

MIT
