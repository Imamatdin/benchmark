# scripts/scad_utils.py
import json
import re
from typing import Any, Dict, Tuple

_CODE_FENCE_RE = re.compile(r"```(?:scad|openscad)?\s*([\s\S]*?)```", re.IGNORECASE)

def extract_text_from_row(row: Dict[str, Any]) -> str:
    """
    Robustly get model text from your run jsonl rows.
    Handles:
      - row["raw"] already text
      - row["raw"] accidentally contains full Gemini API JSON
      - row["response"] has provider payload
    """
    raw = row.get("raw", "")
    if isinstance(raw, dict):
        return _extract_from_provider_payload(raw).strip()
    if isinstance(raw, str):
        s = raw.strip()
        # If raw is actually a JSON string of provider payload, try parse
        if s.startswith("{") and ("candidates" in s or "choices" in s or "\"content\"" in s):
            try:
                obj = json.loads(s)
                txt = _extract_from_provider_payload(obj).strip()
                return txt if txt else s
            except Exception:
                return s
        return s

    # Fallback: try row["response"]
    resp = row.get("response")
    if isinstance(resp, dict):
        return _extract_from_provider_payload(resp).strip()
    return str(raw).strip()

def _extract_from_provider_payload(payload: Dict[str, Any]) -> str:
    # Gemini (generativelanguage)
    cands = payload.get("candidates")
    if isinstance(cands, list) and cands:
        content = (cands[0] or {}).get("content") or {}
        parts = content.get("parts") or []
        out = "".join([p.get("text", "") for p in parts if isinstance(p, dict)])
        return out

    # OpenAI-style / xAI / DeepSeek
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        msg = (choices[0] or {}).get("message") or {}
        c = msg.get("content")
        if isinstance(c, str):
            return c

    # Anthropic Messages API style
    content = payload.get("content")
    if isinstance(content, list) and content:
        t = (content[0] or {}).get("text")
        if isinstance(t, str):
            return t

    # Unknown: best effort stringify
    try:
        return json.dumps(payload, ensure_ascii=False)
    except Exception:
        return str(payload)

def sanitize_scad(text: str) -> Tuple[str, bool]:
    """
    Lenient cleanup:
      - extract first fenced block if present
      - strip leading "Here is..." style preamble lines
      - drop a lone '$' line (common truncation artifact)
      - trim
    Returns (clean_text, changed_flag)
    """
    orig = text
    t = text.strip()

    # If fenced, extract content inside first fence
    m = _CODE_FENCE_RE.search(t)
    if m:
        t = m.group(1).strip()

    # Drop common preamble lines before real code
    lines = t.splitlines()
    cleaned_lines = []
    started = False
    for line in lines:
        s = line.strip()
        if not started:
            if not s:
                continue
            if s.startswith("```"):
                continue
            # Heuristic: OpenSCAD usually starts with comment, module, assignment, or primitive call
            if re.match(r"^(//|/\*|module\b|function\b|include\b|use\b|[A-Za-z_\$]\w*\s*=|[A-Za-z_\$]\w*\s*\(|\b(difference|union|intersection|translate|rotate|scale)\b\s*\()", s):
                started = True
                cleaned_lines.append(line)
            else:
                # skip preamble like "Here is the OpenSCAD code:"
                continue
        else:
            cleaned_lines.append(line)

    t2 = "\n".join(cleaned_lines).strip() if cleaned_lines else t.strip()

    # Drop a lone '$' line (invalid OpenSCAD)
    t3_lines = []
    for line in t2.splitlines():
        if re.match(r"^\s*\$\s*$", line):
            continue
        t3_lines.append(line)
    t3 = "\n".join(t3_lines).strip()

    changed = (t3 != orig.strip())
    return t3, changed

def format_compliant_scad(text: str) -> bool:
    """
    Strict format compliance (Nozomio-style):
      - no markdown fences
      - no preamble before code (must start like OpenSCAD)
    This is independent from compilation.
    """
    t = text.lstrip()
    if not t:
        return False
    if "```" in t:
        return False
    # First non-empty line must look like OpenSCAD-ish
    first = ""
    for line in t.splitlines():
        if line.strip():
            first = line.strip()
            break
    if not first:
        return False
    if re.match(r"^(//|/\*|module\b|function\b|include\b|use\b|[A-Za-z_\$]\w*\s*=|[A-Za-z_\$]\w*\s*\(|\b(difference|union|intersection|translate|rotate|scale)\b\s*\()", first):
        return True
    return False

def overrides_defines(scad_text: str, defines: Dict[str, Any]) -> bool:
    """
    If the model assigns a variable that we set via -D, it can override CLI (bad for param tests).
    Detect top-level 'W = ...;' style assignments.
    """
    if not defines:
        return False
    keys = set(defines.keys())
    for line in scad_text.splitlines():
        m = re.match(r"^\s*([A-Za-z_\$]\w*)\s*=", line)
        if m and m.group(1) in keys:
            return True
    return False
