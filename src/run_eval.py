import argparse
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from tqdm import tqdm


@dataclass
class RunConfig:
    system: str
    temperature: float
    top_p: float
    max_tokens: int
    seed: Optional[int] = None


PROVIDER_IMPORTS = {
    "anthropic": "providers.anthropic_provider:AnthropicProvider",
    "gemini": "providers.gemini_provider:GeminiProvider",
    "xai": "providers.xai_provider:XAIProvider",
    "deepseek": "providers.deepseek_provider:DeepSeekProvider",
}


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def import_provider(name: str):
    import importlib
    spec = PROVIDER_IMPORTS[name]
    mod_name, cls_name = spec.split(":")
    mod = importlib.import_module(mod_name)
    return getattr(mod, cls_name)


def build_prompt(item: Dict[str, Any]) -> str:
    if "prompt" in item:
        return str(item["prompt"])

    task = item.get("task", "").strip()
    ctx = item.get("context", "").strip()
    q = item.get("question", "").strip()

    parts = []
    if task:
        parts.append(task)
    if ctx:
        parts.append(f"Context:\n{ctx}")
    if q:
        parts.append(f"Question:\n{q}")

    return "\n\n".join(parts).strip()


def extract_text(provider: str, resp: Any) -> str:
    if resp is None:
        return ""
    if isinstance(resp, str):
        return resp

    if isinstance(resp, dict):
        try:
            if provider == "gemini":
                cands = resp.get("candidates") or []
                if not cands:
                    return ""
                content = (cands[0] or {}).get("content") or {}
                parts = content.get("parts") or []
                txt = "".join([p.get("text", "") for p in parts if isinstance(p, dict)]).strip()
                return txt

            if provider in ("xai", "deepseek"):
                return resp["choices"][0]["message"]["content"]

            if provider == "anthropic":
                content = resp.get("content", [])
                if content and isinstance(content[0], dict) and "text" in content[0]:
                    return content[0]["text"]
                return ""

        except Exception:
            return ""

    return str(resp)


def main():
    load_dotenv()

    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=PROVIDER_IMPORTS.keys(), required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--data", default="data/benchmark.jsonl")
    ap.add_argument("--out", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--system", default="You are a helpful assistant.")
    ap.add_argument("--temperature", type=float, default=0.2)
    ap.add_argument("--top_p", type=float, default=1.0)
    ap.add_argument("--max_tokens", type=int, default=800)
    ap.add_argument("--sleep_s", type=float, default=0.0)
    ap.add_argument("--list_models", action="store_true")

    # Gemini controls (no more hand-editing system prompts)
    ap.add_argument("--gemini_thinking_budget", type=int, default=0,
                    help="Gemini thinking budget. 0 = off. Only used when --provider gemini.")
    ap.add_argument("--gemini_thinking_level", default="",
                    help="Gemini thinkingLevel (e.g., minimal). Used for Gemini 3.* if set.")
    ap.add_argument("--gemini_force_json", action="store_true",
                    help="Force Gemini to return application/json (+ schema) at API level.")
    args = ap.parse_args()

    # Pass Gemini behavior through env vars so providers can read it
    if args.provider == "gemini":
        os.environ["CRAB_GEMINI_THINKING_BUDGET"] = str(args.gemini_thinking_budget)
        if args.gemini_thinking_level:
            os.environ["CRAB_GEMINI_THINKING_LEVEL"] = args.gemini_thinking_level
        os.environ["CRAB_GEMINI_FORCE_JSON"] = "1" if args.gemini_force_json else "0"

    ProviderCls = import_provider(args.provider)
    provider = ProviderCls()

    if args.list_models:
        models = provider.list_models()
        print(json.dumps(models, indent=2))
        return

    cfg = RunConfig(
        system=args.system,
        temperature=args.temperature,
        top_p=args.top_p,
        max_tokens=args.max_tokens,
    )

    data_path = Path(args.data)
    items = load_jsonl(data_path)
    if args.limit is not None:
        items = items[: args.limit]

    ts = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
    out_path = Path(args.out) if args.out else Path("runs") / f"{args.provider}_{args.model}_{ts}.jsonl"

    results = []
    for item in tqdm(items, desc=f"Running {args.provider}:{args.model}"):
        prompt = build_prompt(item)

        t0 = time.time()
        resp = provider.chat(
            model=args.model,
            system=cfg.system,
            user=prompt,
            temperature=cfg.temperature,
            top_p=cfg.top_p,
            max_tokens=cfg.max_tokens,
        )
        dt = time.time() - t0

        row = {
            "id": item.get("id"),
            "category": item.get("category"),
            "hard": item.get("hard"),
            "provider": args.provider,
            "model": args.model,
            "run_utc": ts,
            "request": {
                "system": cfg.system,
                "temperature": cfg.temperature,
                "top_p": cfg.top_p,
                "max_tokens": cfg.max_tokens,
            },
            "raw": extract_text(args.provider, resp),
            "response": resp,
            "latency_s": dt,
        }
        results.append(row)

        if args.sleep_s > 0:
            time.sleep(args.sleep_s)

    write_jsonl(out_path, results)
    print(f"\nWrote: {out_path.resolve()}")


if __name__ == "__main__":
    main()
    