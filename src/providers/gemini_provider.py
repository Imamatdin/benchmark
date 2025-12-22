import os
import httpx
from typing import Any, Dict, List
from .http_utils import post_json_with_retry

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"

class GeminiProvider:
    def __init__(self):
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("Missing GEMINI_API_KEY in environment")
        self.key = key

    def list_models(self) -> List[Dict[str, Any]]:
        url = f"{GEMINI_BASE}/models?key={self.key}"
        with httpx.Client(timeout=60) as client:
            r = client.get(url)
            if r.status_code >= 400:
                raise RuntimeError(f"HTTP {r.status_code} for {GEMINI_BASE}/models\n{r.text}")
            data = r.json()
            return data.get("models", data)

    def chat(self, model: str, system: str, user: str, temperature: float, top_p: float, max_tokens: int) -> Dict[str, Any]:
        url = f"{GEMINI_BASE}/models/{model}:generateContent?key={self.key}"
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": temperature,
                "topP": top_p,
                "maxOutputTokens": max_tokens,
            },
        }
        with httpx.Client(timeout=90) as client:
            r = post_json_with_retry(client, url, headers={}, payload=payload, max_retries=6)
            return r.json()
