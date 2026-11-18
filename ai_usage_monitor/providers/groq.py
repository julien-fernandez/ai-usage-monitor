from __future__ import annotations

import re
from datetime import timedelta

from ..models import ProbeError, Reading, fmt_number, iso, utcnow
from .base import Provider

URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.1-8b-instant"


def parse_duration(text: str | None) -> float | None:
    if not text:
        return None
    parts = re.findall(r"([\d.]+)(ms|h|m|s)", text)
    if not parts:
        return None
    factor = {"h": 3600.0, "m": 60.0, "s": 1.0, "ms": 0.001}
    return sum(float(n) * factor[u] for n, u in parts)


def _int(headers: dict, name: str) -> int | None:
    try:
        return int(headers[name])
    except (KeyError, ValueError):
        return None


def parse(headers: dict, now=None) -> list[Reading]:
    headers = {k.lower(): v for k, v in headers.items()}
    now = now or utcnow()
    out = []
    for what, unit in (("tokens", "tokens"), ("requests", "requests")):
        limit = _int(headers, f"x-ratelimit-limit-{what}")
        remaining = _int(headers, f"x-ratelimit-remaining-{what}")
        if not limit or remaining is None:
            continue
        wait = parse_duration(headers.get(f"x-ratelimit-reset-{what}"))
        reset_at = iso(now + timedelta(seconds=wait)) if wait is not None else None
        out.append(Reading("groq", f"Rate limit ({what})", "rate", float(limit - remaining), unit,
                           limit=float(limit), reset_at=reset_at,
                           detail=f"{fmt_number(remaining)} of {fmt_number(limit)} {unit} left in window"))
    if not out:
        raise ProbeError("no x-ratelimit-* headers in response")
    return out


def probe(env, http) -> list[Reading]:
    body = {"model": env.get("GROQ_PROBE_MODEL") or DEFAULT_MODEL,
            "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1}
    resp = http.request("POST", URL, {"Authorization": f"Bearer {env['GROQ_API_KEY'].strip()}"}, body)
    if resp.status in (401, 403):
        raise ProbeError(f"HTTP {resp.status}")
    return parse(resp.headers)


PROVIDER = Provider("groq", "Groq", "GROQ_API_KEY", probe)
