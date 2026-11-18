from __future__ import annotations

from datetime import datetime, timezone

from ..models import ProbeError, Reading, fmt_number, iso
from .base import Provider

URL = "https://api.elevenlabs.io/v1/user/subscription"


def parse(payload: dict) -> list[Reading]:
    used, limit = payload.get("character_count"), payload.get("character_limit")
    if used is None or not limit:
        raise ProbeError("subscription payload has no character_count/character_limit")
    reset = payload.get("next_character_count_reset_unix")
    reset_at = iso(datetime.fromtimestamp(float(reset), tz=timezone.utc)) if reset else None
    tier = payload.get("tier") or "unknown tier"
    return [Reading("elevenlabs", "Monthly characters", "quota", float(used), "chars",
                    limit=float(limit), reset_at=reset_at,
                    detail=f"{fmt_number(used)} / {fmt_number(limit)} characters, {tier}")]


def probe(env, http) -> list[Reading]:
    return parse(http.get_json(URL, {"xi-api-key": env["ELEVENLABS_API_KEY"].strip()}))


PROVIDER = Provider("elevenlabs", "ElevenLabs (TTS)", "ELEVENLABS_API_KEY", probe)
