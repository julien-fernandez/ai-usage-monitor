from __future__ import annotations

from ..models import ProbeError, Reading, fmt_number
from .base import Provider

URL = "https://openrouter.ai/api/v1/credits"


def parse(payload: dict) -> list[Reading]:
    data = payload.get("data") or {}
    total, used = data.get("total_credits"), data.get("total_usage")
    if total is None or used is None:
        raise ProbeError("credits payload has no total_credits/total_usage")
    total, used = float(total), float(used)
    return [Reading("openrouter", "Credits", "quota", round(used, 4), "USD",
                    limit=total if total > 0 else None,
                    detail=f"spent {fmt_number(used, 'USD')}, "
                           f"{fmt_number(total - used, 'USD')} left of {fmt_number(total, 'USD')}")]


def probe(env, http) -> list[Reading]:
    key = env["OPENROUTER_API_KEY"].strip()
    return parse(http.get_json(URL, {"Authorization": f"Bearer {key}"}))


PROVIDER = Provider("openrouter", "OpenRouter", "OPENROUTER_API_KEY", probe)
