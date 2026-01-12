# cad_agent.py
"""
CADBench Agent MVP - Interactive CAD code generator
"""
import os
import sys
import subprocess
import tempfile
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Lazy import provider
def get_provider():
    from src.providers.groq_provider import GroqProvider
    return GroqProvider()

SYSTEM_PROMPT = """You are an expert OpenSCAD code generator.

RULES:
1. Output ONLY valid OpenSCAD code
2. No markdown, no code fences, no explanations
3. No text before or after the code
4. Use millimeters as units
5. Center geometry at origin unless specified otherwise
6. Use $fn=64 for smooth curves

The user will describe a 3D part. Generate OpenSCAD code that creates it."""

def validate_scad(code: str, openscad_exe: str) -> tuple[bool, str, Path | None]:
    """Compile OpenSCAD code and return (success, error_msg, stl_path)"""
    with tempfile.TemporaryDirectory() as tmpdir:
        scad_path = Path(tmpdir) / "part.scad"
        stl_path = Path(tmpdir) / "part.stl"
        
        scad_path.write_text(code, encoding="utf-8")
        
        cmd = [openscad_exe, "-o", str(stl_path), str(scad_path)]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if r.returncode == 0 and stl_path.exists():
                # Copy STL to persistent location
                output_dir = Path("agent_outputs")
                output_dir.mkdir(exist_ok=True)
                
                import time
                ts = time.strftime("%Y%m%d_%H%M%S")
                final_scad = output_dir / f"part_{ts}.scad"
                final_stl = output_dir / f"part_{ts}.stl"
                
                final_scad.write_text(code, encoding="utf-8")
                final_stl.write_bytes(stl_path.read_bytes())
                
                return True, "", final_stl
            else:
                return False, (r.stderr or r.stdout or "Unknown error")[:500], None
        except subprocess.TimeoutExpired:
            return False, "OpenSCAD timed out", None
        except Exception as e:
            return False, str(e), None

def generate_code(provider, prompt: str, model: str = "llama-3.3-70b-versatile") -> str:
    """Call LLM to generate OpenSCAD code"""
    resp = provider.chat(
        model=model,
        system=SYSTEM_PROMPT,
        user=prompt,
        temperature=0.2,
        top_p=1.0,
        max_tokens=1000,
    )
    
    # Extract text from Gemini response
    # Extract text from response (OpenAI format)
    choices = resp.get("choices", [])
    if not choices:
        return ""
    return choices[0].get("message", {}).get("content", "").strip()

def clean_code(code: str) -> str:
    """Strip markdown fences if present"""
    code = code.strip()
    if code.startswith("```"):
        lines = code.split("\n")
        # Remove first line (```scad or ```)
        lines = lines[1:]
        # Remove last line if it's ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        code = "\n".join(lines)
    return code.strip()

def main():
    # Find OpenSCAD
    openscad_exe = os.environ.get("OPENSCAD_EXE", "openscad")
    if not Path(openscad_exe).exists() and openscad_exe == "openscad":
        # Try common Windows path
        win_path = r"C:\Program Files\OpenSCAD\openscad.exe"
        if Path(win_path).exists():
            openscad_exe = win_path
    
    print("=" * 60)
    print("CADBench Agent MVP")
    print("=" * 60)
    print(f"OpenSCAD: {openscad_exe}")
    print("Type 'quit' to exit, 'help' for examples")
    print("=" * 60)
    
    try:
        provider = get_provider()
        print("✓ Gemini API connected\n")
    except Exception as e:
        print(f"✗ Failed to connect: {e}")
        print("Make sure GEMINI_API_KEY is set in .env")
        sys.exit(1)
    
    while True:
        try:
            user_input = input("\nDescribe your part: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nBye!")
            break
        
        if not user_input:
            continue
        if user_input.lower() == "quit":
            break
        if user_input.lower() == "help":
            print("""
Examples:
  - A cube 20x30x10mm centered at origin
  - A cylinder radius 10mm, height 50mm, centered
  - A plate 60x40x6mm with a 5mm radius hole in the center
  - An L-bracket with width 40mm, height 30mm, thickness 4mm
  - A rounded box 50x30x20mm with 3mm fillet radius
""")
            continue
        
        print("\n⏳ Generating code...")
        
        # Generate
        code = generate_code(provider, user_input)
        code = clean_code(code)
        
        if not code:
            print("✗ No code generated")
            continue
        
        print("\n📝 Generated OpenSCAD:")
        print("-" * 40)
        print(code)
        print("-" * 40)
        
        # Validate
        print("\n⏳ Validating with OpenSCAD...")
        success, error, stl_path = validate_scad(code, openscad_exe)
        
        if success:
            print(f"✓ Compilation successful!")
            print(f"  STL saved: {stl_path}")
            print(f"  SCAD saved: {stl_path.with_suffix('.scad')}")
        else:
            print(f"✗ Compilation failed:")
            print(f"  {error}")
            
            # Retry with error feedback
            print("\n⏳ Retrying with error feedback...")
            retry_prompt = f"""The previous code failed to compile.

Original request: {user_input}

Error: {error}

Generate corrected OpenSCAD code. Output ONLY the code, no explanations."""
            
            code2 = generate_code(provider, retry_prompt)
            code2 = clean_code(code2)
            
            if code2:
                print("\n📝 Retry code:")
                print("-" * 40)
                print(code2)
                print("-" * 40)
                
                success2, error2, stl_path2 = validate_scad(code2, openscad_exe)
                if success2:
                    print(f"✓ Retry successful!")
                    print(f"  STL saved: {stl_path2}")
                else:
                    print(f"✗ Retry also failed: {error2}")

if __name__ == "__main__":
    main()