import os
import httpx
from typing import Any, Dict, List
from .http_utils import post_json_with_retry

ANTHROPIC_BASE = "https://api.anthropic.com"

class AnthropicProvider:
    def __init__(self):
        key = os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("Missing ANTHROPIC_API_KEY in environment")
        self.key = key

    def list_models(self) -> List[Dict[str, Any]]:
        return []

    def chat(self, model: str, system: str, user: str, temperature: float, top_p: float, max_tokens: int) -> Dict[str, Any]:
        url = f"{ANTHROPIC_BASE}/v1/messages"
        headers = {
            "x-api-key": self.key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        with httpx.Client(timeout=90) as client:
            r = post_json_with_retry(client, url, headers=headers, payload=payload, max_retries=2)
            return r.json()
