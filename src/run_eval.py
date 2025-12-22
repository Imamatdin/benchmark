import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from tqdm import tqdm
import httpx

from providers.anthropic_provider import AnthropicProvider
from providers.gemini_provider import GeminiProvider
from providers.xai_provider import XAIProvider
from providers.deepseek_provider import DeepSeekProvider


@dataclass
class RunConfig:
    system: str
    temperature: float
    top_p: float
    max_tokens: int
    seed: Optional[int] = None  # not supported by all providers; we still record it


PROVIDERS = {
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
    "xai": XAIProvider,
    "deepseek": DeepSeekProvider,
}


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows = []
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


def build_prompt(item: Dict[str, Any]) -> str:
    """
    Supports:
    - CRAB format: task/context/question
    - legacy format: prompt
    """
    if "task" in item and "question" in item:
        task = item.get("task", "").strip()
        context = item.get("context", "").strip()
        question = item.get("question", "").strip()
        parts = []
        if task:
            parts.append(task)
        if context:
            parts.append("Context:\n" + context)
        if question:
            parts.append("Question:\n" + question)
        return "\n\n".join(parts).strip()
    if "prompt" in item:
        return str(item["prompt"])
    raise KeyError("Item missing required fields. Expected CRAB {task,question} or legacy {prompt}.")


def extract_raw_text(resp: Any) -> str:
    """
    Providers might return:
    - str
    - dict with 'text' or 'content'
    - other -> str(resp)
    """
    if isinstance(resp, str):
        return resp
    if isinstance(resp, dict):
        for k in ("text", "content", "output_text", "message"):
            v = resp.get(k)
            if isinstance(v, str) and v.strip():
                return v
        # Some APIs return list-of-blocks; last resort:
        return json.dumps(resp, ensure_ascii=False)
    return str(resp)


def chat_with_retries(provider, *, model, system, user, temperature, top_p, max_tokens,
                      max_retries: int = 6, base_sleep_s: float = 1.0):
    """
    Retries on rate limits and transient upstream errors.
    """
    attempt = 0
    while True:
        attempt += 1
        try:
            return provider.chat(
                model=model,
                system=system,
                user=user,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
            )
        except httpx.HTTPStatusError as e:
            status = getattr(e.response, "status_code", None)
            # Retry only on transient-ish statuses:
            if status in (408, 425, 429, 500, 502, 503, 504) and attempt <= max_retries:
                sleep_s = base_sleep_s * (2 ** (attempt - 1))
                # cap so it doesn't explode
                sleep_s = min(sleep_s, 30.0)
                print(f"[retry] HTTP {status} attempt {attempt}/{max_retries}; sleeping {sleep_s:.1f}s")
                time.sleep(sleep_s)
                continue
            raise
        except Exception:
            # Unknown error: don't loop forever
            if attempt <= 2:
                time.sleep(base_sleep_s)
                continue
            raise


def main():
    load_dotenv()

    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=PROVIDERS.keys(), required=True)
    ap.add_argument("--model", required=True, help="Provider model id")
    ap.add_argument("--data", default="data/benchmark.jsonl")
    ap.add_argument("--out", default=None, help="Output file path (default: runs/<provider>_<model>_<ts>.jsonl)")
    ap.add_argument("--limit", type=int, default=None, help="Only run first N items")
    ap.add_argument("--system", default="You are a helpful assistant.")
    ap.add_argument("--temperature", type=float, default=0.2)
    ap.add_argument("--top_p", type=float, default=1.0)
    ap.add_argument("--max_tokens", type=int, default=400)
    ap.add_argument("--sleep_s", type=float, default=0.0, help="Client-side throttle between requests")
    ap.add_argument("--list_models", action="store_true", help="List models for providers that support it and exit")
    args = ap.parse_args()

    provider = PROVIDERS[args.provider]()

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

    items = load_jsonl(Path(args.data))
    if args.limit is not None:
        items = items[: args.limit]

    ts = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
    safe_model = args.model.replace("/", "_").replace(":", "_")
    out_path = Path(args.out) if args.out else Path("runs") / f"{args.provider}_{safe_model}_{ts}.jsonl"

    results = []
    for item in tqdm(items, desc=f"Running {args.provider}:{args.model}"):
        prompt = build_prompt(item)

        t0 = time.time()
        resp = chat_with_retries(
            provider,
            model=args.model,
            system=cfg.system,
            user=prompt,
            temperature=cfg.temperature,
            top_p=cfg.top_p,
            max_tokens=cfg.max_tokens,
        )
        dt = time.time() - t0

        raw = extract_raw_text(resp)

        # IMPORTANT: scorer expects id/category/raw
        row = {
            "id": item.get("id"),
            "category": item.get("category", "unknown"),
            "hard": item.get("hard", False),
            "prompt": prompt,
            "raw": raw,
            "provider": args.provider,
            "model": args.model,
            "run_utc": ts,
            "request": {
                "system": cfg.system,
                "temperature": cfg.temperature,
                "top_p": cfg.top_p,
                "max_tokens": cfg.max_tokens,
            },
            "latency_s": dt,
            "response_meta": resp if isinstance(resp, dict) else None,
        }
        results.append(row)

        if args.sleep_s > 0:
            time.sleep(args.sleep_s)

    write_jsonl(out_path, results)
    print(f"\nWrote: {out_path.resolve()}")


if __name__ == "__main__":
    main()
