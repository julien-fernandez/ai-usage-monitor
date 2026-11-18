from __future__ import annotations

import math
import random
from datetime import datetime, timedelta

from .models import Reading, fmt_number, iso, utcnow
from .store import Store

DAYS = 30
STEP = timedelta(hours=2)


def activity(t: datetime) -> float:
    """Relative activity of a fictional small team: office hours, quieter evenings and weekends."""
    hour = t.hour
    day = 1.0 if 8 <= hour < 19 else 0.45 if 19 <= hour < 23 else 0.08
    return day * (0.35 if t.weekday() >= 5 else 1.0)


def _timeline(now: datetime) -> list[datetime]:
    start = now - timedelta(days=DAYS)
    steps = int((now - start) / STEP)
    return [start + STEP * i for i in range(steps + 1)]


def _cumulative(times: list[datetime], rng: random.Random,
                bursts: dict[int, float] | None = None) -> list[float]:
    total, out = 0.0, []
    for i, t in enumerate(times):
        total += activity(t) * rng.uniform(0.6, 1.4) + (bursts or {}).get(i, 0.0)
        out.append(total)
    return out


def elevenlabs(times, now, rng) -> list[Reading]:
    limit = 100_000.0
    reset_prev = now - timedelta(days=21)
    reset_next = now + timedelta(days=9)
    burst_at = len(times) - 6 * 12
    raw = _cumulative(times, rng, {burst_at + k: 2.5 for k in range(3)})
    cut = next(i for i, t in enumerate(times) if t >= reset_prev)
    scale = 76_000.0 / (raw[-1] - raw[cut - 1])
    early = 64_000.0 / raw[cut - 1]
    out = []
    for i, t in enumerate(times):
        used = round(raw[i] * early) if i < cut else round((raw[i] - raw[cut - 1]) * scale)
        reset = reset_prev if i < cut else reset_next
        out.append(Reading("elevenlabs", "Monthly characters", "quota", float(used), "chars",
                           limit=limit, reset_at=iso(reset), at=iso(t) or "",
                           detail=f"{fmt_number(used)} / {fmt_number(limit)} characters, creator"))
    return out


def openrouter(times, now, rng) -> list[Reading]:
    total = 25.0
    raw = _cumulative(times, rng)
    out = []
    for t, r in zip(times, raw):
        used = round(10.4 + 7.1 * r / raw[-1], 4)
        out.append(Reading("openrouter", "Credits", "quota", used, "USD", limit=total, at=iso(t) or "",
                           detail=f"spent {fmt_number(used, 'USD')}, {fmt_number(total - used, 'USD')} "
                                  f"left of {fmt_number(total, 'USD')}"))
    return out


def deepgram(times, now, rng) -> list[Reading]:
    raw = _cumulative(times, rng)
    topup_at = next(i for i, t in enumerate(times) if t >= now - timedelta(days=12))
    per_unit = 132.0 / raw[-1]
    out = []
    for i, t in enumerate(times):
        balance = 140.0 - raw[i] * per_unit + (40.0 if i >= topup_at else 0.0)
        balance = round(balance, 2)
        out.append(Reading("deepgram", "Project balance", "balance", balance, "USD", at=iso(t) or "",
                           detail=f"{fmt_number(balance, 'USD')} remaining across 1 project(s)"))
    return out


def groq(times, now, rng) -> list[Reading]:
    limit = 6000.0
    out = []
    for t in times:
        used = round(limit * min(0.95, activity(t) * rng.uniform(0.05, 0.55)))
        out.append(Reading("groq", "Rate limit (tokens)", "rate", float(used), "tokens", limit=limit,
                           reset_at=iso(t + timedelta(seconds=40)), at=iso(t) or "",
                           detail=f"{fmt_number(limit - used)} of {fmt_number(limit)} tokens left in window"))
    return out


def claude_code(times, now, rng) -> list[Reading]:
    out = []
    for t in times:
        window = [t - timedelta(hours=h) for h in range(24)]
        tokens = round(sum(activity(w) for w in window) * 260_000 * rng.uniform(0.7, 1.3)
                       * (1.0 + 0.3 * math.sin(t.timetuple().tm_yday / 3)))
        out.append(Reading("claude_code", "Tokens, last 24 h", "volume", float(tokens), "tokens",
                           at=iso(t) or "",
                           detail=f"{fmt_number(tokens)} input+output tokens; a volume, not a quota"))
    return out


GENERATORS = (elevenlabs, openrouter, deepgram, groq, claude_code)


def seed(store: Store, now: datetime | None = None, seed_value: int = 7) -> int:
    now = (now or utcnow()).replace(minute=0, second=0, microsecond=0)
    times = _timeline(now)
    rng = random.Random(seed_value)
    return sum(store.add(gen(times, now, rng)) for gen in GENERATORS)
