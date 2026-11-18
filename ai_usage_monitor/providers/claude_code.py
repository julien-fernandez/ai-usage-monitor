from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime, timedelta
from pathlib import Path

from ..models import Reading, fmt_number, parse_iso, utcnow
from .base import Provider

TOKEN_FIELDS = ("input_tokens", "output_tokens")
CACHE_FIELDS = ("cache_creation_input_tokens", "cache_read_input_tokens")


def projects_dir(env) -> Path | None:
    raw = (env.get("CLAUDE_PROJECTS_DIR") or "").strip()
    return Path(raw).expanduser() if raw else None


def count_lines(lines: Iterable[str], since: datetime) -> tuple[int, int]:
    tokens = cache = 0
    for line in lines:
        if '"usage"' not in line:
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        stamp = parse_iso(entry.get("timestamp"))
        if stamp is None or stamp < since:
            continue
        usage = (entry.get("message") or {}).get("usage") or {}
        tokens += sum(int(usage.get(f) or 0) for f in TOKEN_FIELDS)
        cache += sum(int(usage.get(f) or 0) for f in CACHE_FIELDS)
    return tokens, cache


def scan(base: Path, now: datetime | None = None, hours: float = 24.0) -> Reading:
    now = now or utcnow()
    since = now - timedelta(hours=hours)
    tokens = cache = files = 0
    for path in base.rglob("*.jsonl"):
        try:
            if path.stat().st_mtime < since.timestamp():
                continue
            with path.open(encoding="utf-8", errors="ignore") as fh:
                t, c = count_lines(fh, since)
        except OSError:
            continue
        if t or c:
            files += 1
        tokens, cache = tokens + t, cache + c
    return Reading("claude_code", "Tokens, last 24 h", "volume", float(tokens), "tokens",
                   detail=f"{fmt_number(tokens)} input+output tokens, {fmt_number(cache)} cache tokens, "
                          f"{files} session file(s); a volume, not a quota")


def availability(env) -> str | None:
    base = projects_dir(env)
    if base is None:
        return "CLAUDE_PROJECTS_DIR not set (opt-in: reads local transcripts)"
    return None if base.is_dir() else f"transcripts directory {base} not found"


def probe(env, http) -> list[Reading]:
    return [scan(projects_dir(env))]


PROVIDER = Provider("claude_code", "Claude Code (local volume)", "CLAUDE_PROJECTS_DIR", probe,
                    availability=availability)
