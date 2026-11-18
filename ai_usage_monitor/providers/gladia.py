from __future__ import annotations

from ..models import Reading
from .base import Provider

CHANNELS = ("pre-recorded", "live")
URL = "https://api.gladia.io/v2/{channel}/get-usage"


def parse(payloads: list[dict]) -> list[Reading]:
    hours = sum(float((p.get("usage") or {}).get("hours_transcribed") or 0) for p in payloads)
    requests = sum(int((p.get("usage") or {}).get("api_requests") or 0) for p in payloads)
    return [Reading("gladia", "Hours this month", "volume", round(hours, 2), "h",
                    detail=f"{hours:.2f} h transcribed, {requests} requests this month")]


def probe(env, http) -> list[Reading]:
    key = env["GLADIA_API_KEY"].strip()
    body = {"api_keys": [key], "date_range": {"type": "this_month"}, "view": "daily"}
    return parse([http.post_json(URL.format(channel=c), {"x-gladia-key": key}, body)
                  for c in CHANNELS])


PROVIDER = Provider("gladia", "Gladia (STT)", "GLADIA_API_KEY", probe)
