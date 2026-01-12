import os
import httpx
from typing import Any, Dict, List

GROQ_BASE = "https://api.groq.com/openai/v1"

class GroqProvider:
    def __init__(self):
        key = os.getenv("GROQ_API_KEY")
        if not key:
            raise RuntimeError("Missing GROQ_API_KEY in environment")
        self.key = key

    def list_models(self) -> List[Dict[str, Any]]:
        return []

    def chat(self, model: str, system: str, user: str, temperature: float, top_p: float, max_tokens: int) -> Dict[str, Any]:
        url = f"{GROQ_BASE}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        with httpx.Client(timeout=60) as client:
            r = client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            return r.json()