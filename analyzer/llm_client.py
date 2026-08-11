"""Agent Platform REST client — shared by batch and interactive analyzers."""

from __future__ import annotations

import json
import time
import urllib.request
import warnings

from credentials import CredentialsError, get_access_token

MAX_RETRIES = 5
INITIAL_BACKOFF_SEC = 2.0


def _is_rate_limit_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(
        token in msg
        for token in ("429", "rate", "quota", "resource exhausted", "too many requests")
    )


def generate_content(
    prompt: str,
    project: str,
    location: str,
    model_name: str,
    *,
    json_mode: bool = True,
    temperature: float = 0.2,
    timeout: int = 120,
) -> str:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        token = get_access_token()
    if not token:
        raise RuntimeError("ADC_NOT_CONFIGURED")

    url = (
        f"https://aiplatform.googleapis.com/v1/projects/{project}"
        f"/locations/{location}/publishers/google/models/{model_name}:generateContent"
    )

    generation_config: dict = {"temperature": temperature}
    if json_mode:
        generation_config["responseMimeType"] = "application/json"

    body = json.dumps(
        {
            "contents": {"role": "user", "parts": [{"text": prompt}]},
            "generationConfig": generation_config,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    candidates = payload.get("candidates") or []
    if not candidates:
        raise RuntimeError("Empty response from Agent Platform")

    parts = candidates[0].get("content", {}).get("parts") or []
    texts = [p.get("text", "") for p in parts if p.get("text")]
    if not texts:
        raise RuntimeError("No text in Agent Platform response")
    return "\n".join(texts)


def generate_content_with_retries(
    prompt: str,
    project: str,
    location: str,
    model_name: str,
    **kwargs,
) -> str:
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return generate_content(prompt, project, location, model_name, **kwargs)
        except RuntimeError as exc:
            if str(exc) == "ADC_NOT_CONFIGURED":
                raise
            last_error = exc
            if _is_rate_limit_error(exc) and attempt < MAX_RETRIES:
                time.sleep(INITIAL_BACKOFF_SEC * (2 ** (attempt - 1)))
                continue
            break
        except Exception as exc:
            last_error = exc
            if _is_rate_limit_error(exc) and attempt < MAX_RETRIES:
                time.sleep(INITIAL_BACKOFF_SEC * (2 ** (attempt - 1)))
                continue
            break
    raise RuntimeError(str(last_error or "Agent Platform call failed"))
