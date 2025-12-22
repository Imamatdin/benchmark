import os
import httpx
from typing import Any, Dict, List

DEEPSEEK_BASE = "https://api.deepseek.com"


class DeepSeekProvider:
    def __init__(self):
        key = os.getenv("DEEPSEEK_API_KEY")
        if not key:
            raise RuntimeError("Missing DEEPSEEK_API_KEY in environment")
        self.key = key

    def list_models(self) -> List[Dict[str, Any]]:
        url = f"{DEEPSEEK_BASE}/models"
        headers = {"Authorization": f"Bearer {self.key}"}
        with httpx.Client(timeout=60) as client:
            r = client.get(url, headers=headers)
            r.raise_for_status()
            data = r.json()
            return data.get("data", data)

    def chat(self, model: str, system: str, user: str, temperature: float, top_p: float, max_tokens: int) -> Dict[str, Any]:
        url = f"{DEEPSEEK_BASE}/chat/completions"
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
            "top_p": top_p,
            "max_tokens": max_tokens,
            "stream": False,
        }
        with httpx.Client(timeout=90) as client:
            r = client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            return r.json()
