from __future__ import annotations

from ..models import ProbeError, Reading, fmt_number
from .base import Provider

API = "https://api.deepgram.com/v1"


def project_ids(payload: dict) -> list[str]:
    return [p["project_id"] for p in payload.get("projects") or [] if p.get("project_id")]


def parse_balances(payloads: list[dict]) -> list[Reading]:
    total, unit, count = 0.0, "USD", 0
    for payload in payloads:
        for balance in payload.get("balances") or []:
            total += float(balance.get("amount") or 0)
            unit = (balance.get("units") or unit).upper()
            count += 1
    if count == 0:
        raise ProbeError("no balance returned for any project")
    return [Reading("deepgram", "Project balance", "balance", round(total, 2), unit,
                    detail=f"{fmt_number(total, unit)} remaining across {len(payloads)} project(s)")]


def probe(env, http) -> list[Reading]:
    headers = {"Authorization": f"Token {env['DEEPGRAM_API_KEY'].strip()}"}
    ids = project_ids(http.get_json(f"{API}/projects", headers))
    if not ids:
        raise ProbeError("the key sees no project")
    return parse_balances([http.get_json(f"{API}/projects/{pid}/balances", headers) for pid in ids])


PROVIDER = Provider("deepgram", "Deepgram (STT)", "DEEPGRAM_API_KEY", probe)
