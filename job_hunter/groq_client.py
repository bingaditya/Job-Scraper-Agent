from __future__ import annotations

import json

import requests

from job_hunter.config import GroqConfig


def chat_json(
    system_prompt: str,
    user_prompt: str,
    groq_config: GroqConfig,
    timeout: int = 60,
) -> dict | None:
    """Call Groq's chat-completions endpoint expecting a strict JSON object back.

    Returns None on any failure (missing key, rate limit, network error, malformed
    response) so callers can fall back to deterministic behavior. A 429 (rate limit)
    is treated as an expected outcome, not an exception.
    """
    if not groq_config.api_key:
        return None

    try:
        response = requests.post(
            f"{groq_config.base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {groq_config.api_key}"},
            json={
                "model": groq_config.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.2,
            },
            timeout=timeout,
        )
        if response.status_code == 429:
            return None
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return json.loads(content)
    except (requests.RequestException, KeyError, IndexError, TypeError, json.JSONDecodeError):
        return None
