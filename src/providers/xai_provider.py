import os
import httpx
from typing import Any, Dict, List

XAI_BASE = "https://api.x.ai"

class XAIProvider:
    def __init__(self):
        key = os.getenv("XAI_API_KEY")
        if not key:
            raise RuntimeError("Missing XAI_API_KEY in environment")
        self.key = key

    def list_models(self) -> List[Dict[str, Any]]:
        url = f"{XAI_BASE}/v1/models"
        headers = {"Authorization": f"Bearer {self.key}"}
        with httpx.Client(timeout=60) as client:
            r = client.get(url, headers=headers)
            if r.status_code >= 400:
                raise RuntimeError(f"HTTP {r.status_code} for {url}\n{r.text}")
            data = r.json()
            return data.get("data", data)

    def chat(self, model: str, system: str, user: str, temperature: float, top_p: float, max_tokens: int) -> Dict[str, Any]:
        url = f"{XAI_BASE}/v1/chat/completions"
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
        }
        with httpx.Client(timeout=90) as client:
            r = client.post(url, headers=headers, json=payload)
            if r.status_code >= 400:
                raise RuntimeError(f"HTTP {r.status_code} for {url}\n{r.text}")
            return r.json()
