from __future__ import annotations

from ..models import ProbeError, Reading, fmt_number
from .base import Provider

URL = "https://api.fireflies.ai/graphql"
QUERY = "query { user { minutes_consumed num_transcripts } }"


def parse(payload: dict, monthly_limit: float | None = None) -> list[Reading]:
    if payload.get("errors"):
        raise ProbeError(str(payload["errors"][0].get("message", "GraphQL error"))[:120])
    user = (payload.get("data") or {}).get("user") or {}
    minutes = user.get("minutes_consumed")
    if minutes is None:
        raise ProbeError("GraphQL payload has no user.minutes_consumed")
    transcripts = user.get("num_transcripts") or 0
    detail = f"{fmt_number(float(minutes))} min, {transcripts} transcripts"
    if monthly_limit:
        return [Reading("fireflies", "Minutes", "quota", float(minutes), "min",
                        limit=monthly_limit, detail=f"{detail}, plan limit {fmt_number(monthly_limit)} min")]
    return [Reading("fireflies", "Minutes", "volume", float(minutes), "min", detail=detail)]


def _limit(env) -> float | None:
    raw = (env.get("FIREFLIES_MONTHLY_MINUTES") or "").strip()
    try:
        return float(raw) if raw else None
    except ValueError as exc:
        raise ProbeError("FIREFLIES_MONTHLY_MINUTES is not a number") from exc


def probe(env, http) -> list[Reading]:
    key = env["FIREFLIES_API_KEY"].strip()
    payload = http.post_json(URL, {"Authorization": f"Bearer {key}"}, {"query": QUERY})
    return parse(payload, _limit(env))


PROVIDER = Provider("fireflies", "Fireflies", "FIREFLIES_API_KEY", probe)
