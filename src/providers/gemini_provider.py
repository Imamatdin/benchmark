import os
import json
import httpx
from typing import Any, Dict, List
from .http_utils import post_json_with_retry

# Correct Gemini Developer API base (AI Studio key works here)
DEFAULT_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"

class GeminiProvider:
    def __init__(self):
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("Missing GEMINI_API_KEY in environment (.env)")

        base = os.getenv("GEMINI_BASE", DEFAULT_GEMINI_BASE).rstrip("/")
        # Guardrail: people keep pasting the AI Studio *website* URL here.
        if "aistudio.google.com" in base:
            raise RuntimeError(
                f"GEMINI_BASE is wrong ({base}). Use {DEFAULT_GEMINI_BASE} (API endpoint), "
                "not the AI Studio api-keys webpage."
            )

        self.key = key
        self.base = base

    def list_models(self) -> List[Dict[str, Any]]:
        url = f"{self.base}/models?key={self.key}"
        with httpx.Client(timeout=60) as client:
            r = client.get(url)
            r.raise_for_status()
            data = r.json()
            return data.get("models", data)

    def chat(
        self,
        model: str,
        system: str,
        user: str,
        temperature: float,
        top_p: float,
        max_tokens: int,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        url = f"{self.base}/models/{model}:generateContent?key={self.key}"

        payload: Dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": temperature,
                "topP": top_p,
                "maxOutputTokens": max_tokens,
            },
        }

        # If you later add flags like gemini_thinking_budget / gemini_force_json,
        # handle them here via kwargs.
        with httpx.Client(timeout=120) as client:
            r = post_json_with_retry(
                client=client,
                url=url,
                headers={},
                payload=payload,
                max_retries=10,
                timeout=120
            )
            return r.json()
