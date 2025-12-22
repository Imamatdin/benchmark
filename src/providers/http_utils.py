from __future__ import annotations

import time
from typing import Any, Dict, Optional

import httpx


TRANSIENT_STATUSES = {408, 425, 429, 500, 502, 503, 504}


def _retry_after_seconds(resp: httpx.Response) -> Optional[float]:
    ra = resp.headers.get("retry-after")
    if not ra:
        return None
    try:
        return float(ra)
    except Exception:
        return None


def post_json_with_retry(
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    *,
    timeout_s: float = 60.0,
    max_retries: int = 6,
    base_sleep_s: float = 1.0,
) -> httpx.Response:
    """
    Shared helper for provider wrappers.
    Retries on rate limits + transient upstream errors.
    """
    with httpx.Client(timeout=timeout_s) as client:
        last_exc: Optional[Exception] = None

        for attempt in range(1, max_retries + 2):  # first try + retries
            try:
                resp = client.post(url, headers=headers, json=payload)

                if resp.status_code in TRANSIENT_STATUSES:
                    if attempt <= max_retries:
                        sleep_s = _retry_after_seconds(resp)
                        if sleep_s is None:
                            sleep_s = min(30.0, base_sleep_s * (2 ** (attempt - 1)))
                        time.sleep(sleep_s)
                        continue

                # Non-transient or out of retries -> raise if error
                resp.raise_for_status()
                return resp

            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as e:
                last_exc = e
                # Retry on timeouts / transport errors
                if attempt <= max_retries:
                    time.sleep(min(30.0, base_sleep_s * (2 ** (attempt - 1))))
                    continue
                raise

        # should never reach
        if last_exc:
            raise last_exc
        raise RuntimeError("post_json_with_retry failed without exception")
