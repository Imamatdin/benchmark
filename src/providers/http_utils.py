import time
import random
from typing import Any, Dict, Optional

import httpx


RETRY_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}


def _sleep_backoff(attempt: int, base: float = 2.0, cap: float = 60.0) -> None:
    # exponential backoff + jitter
    sleep_s = min(cap, base * (2 ** attempt)) * (0.5 + random.random() * 0.5)
    time.sleep(sleep_s)


def post_json_with_retry(
    client: httpx.Client,
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    max_retries: int = 6,
    timeout: Optional[float] = None,
) -> httpx.Response:
    last_exc: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        try:
            r = client.post(url, headers=headers, json=payload, timeout=timeout)
            if r.status_code < 400:
                return r

            # retry on transient errors / throttling
            if r.status_code in RETRY_STATUS and attempt < max_retries:
                # Log the error details for debugging
                try:
                    error_body = r.json()
                    print(f"\n[Retry {attempt+1}/{max_retries}] HTTP {r.status_code}: {error_body}")
                except:
                    print(f"\n[Retry {attempt+1}/{max_retries}] HTTP {r.status_code}: {r.text[:200]}")
                _sleep_backoff(attempt)
                continue

            # non-retryable or out of retries
            print(f"\n[FAILED after {attempt+1} attempts] HTTP {r.status_code}")
            try:
                print(f"Error details: {r.json()}")
            except:
                print(f"Error text: {r.text[:500]}")
            r.raise_for_status()
            return r  # unreachable

        except (httpx.TimeoutException, httpx.NetworkError) as e:
            last_exc = e
            if attempt >= max_retries:
                raise
            _sleep_backoff(attempt)

    # should never hit
    if last_exc:
        raise last_exc
    raise RuntimeError("post_json_with_retry: unknown failure")
