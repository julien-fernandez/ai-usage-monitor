from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .models import Reading, iso, parse_iso

RESET_DROP_PCT = 2.0
MAX_GAP_H = 3.0
MIN_COVERAGE_H = 12.0
PROFILE_DAYS = 14
WEEKDAY_DAMPING = 0.5
STEP = timedelta(minutes=15)
QUOTA_HORIZON = timedelta(days=31)
BALANCE_HORIZON = timedelta(days=90)
METHOD = "hourly-profile"
BASELINE = "constant-rate"

Point = tuple[datetime, float]


@dataclass
class Increment:
    start: datetime
    end: datetime
    delta: float

    @property
    def hours(self) -> float:
        return (self.end - self.start).total_seconds() / 3600


@dataclass
class Forecast:
    method: str
    target_at: datetime
    now_value: float
    projected: float
    exhaust_at: datetime | None
    coverage_h: float
    rate_per_day: float
    baseline_projected: float
    baseline_exhaust_at: datetime | None
    curve: list[Point] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "method": self.method,
            "target_at": iso(self.target_at),
            "now_value": round(self.now_value, 3),
            "projected": round(self.projected, 3),
            "exhaust_at": iso(self.exhaust_at),
            "coverage_h": round(self.coverage_h, 1),
            "rate_per_day": round(self.rate_per_day, 4),
            "baseline": {"method": BASELINE, "projected": round(self.baseline_projected, 3),
                         "exhaust_at": iso(self.baseline_exhaust_at)},
            "curve": [[iso(t), round(v, 3)] for t, v in self.curve],
        }


def to_level(reading: Reading) -> float | None:
    """Map a reading to a level that rises toward a ceiling: quota pct to 100, balance to 0."""
    if reading.kind == "quota":
        if reading.value is None or not reading.limit:
            return None
        return 100.0 * reading.value / reading.limit
    if reading.kind == "balance" and reading.value is not None:
        return -reading.value
    return None


def from_level(kind: str, level: float) -> float:
    return -level if kind == "balance" else level


def ceiling(kind: str) -> float:
    return 100.0 if kind == "quota" else 0.0


def reset_threshold(kind: str, points: list[Point]) -> float:
    if kind == "quota":
        return RESET_DROP_PCT
    scale = max((abs(v) for _, v in points), default=1.0)
    return max(0.01 * scale, 0.01)


def level_points(readings: list[Reading]) -> list[Point]:
    out = []
    for r in readings:
        level, at = to_level(r), parse_iso(r.at)
        if level is not None and at is not None:
            out.append((at, level))
    return out


def current_cycle(points: list[Point], drop: float) -> list[Point]:
    start = 0
    for i in range(1, len(points)):
        if points[i][1] < points[i - 1][1] - drop:
            start = i
    return points[start:]


def increments(points: list[Point], drop: float, max_gap_h: float = MAX_GAP_H) -> list[Increment]:
    out = []
    for (t0, v0), (t1, v1) in zip(points, points[1:]):
        hours = (t1 - t0).total_seconds() / 3600
        if hours <= 0 or hours > max_gap_h or v1 < v0 - drop:
            continue
        out.append(Increment(t0, t1, max(0.0, v1 - v0)))
    return out


def _slices(inc: Increment):
    t = inc.start
    while t < inc.end:
        nxt = min(t.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1), inc.end)
        yield t, (nxt - t).total_seconds() / 3600
        t = nxt


def hourly_profile(incs: list[Increment]) -> tuple[list[float | None], float, float]:
    """Mean consumption rate per local hour of day, the overall mean rate, and hours covered."""
    used, covered = [0.0] * 24, [0.0] * 24
    for inc in incs:
        if inc.hours <= 0:
            continue
        rate = inc.delta / inc.hours
        for t, h in _slices(inc):
            hour = t.astimezone().hour
            used[hour] += rate * h
            covered[hour] += h
    total_c = sum(covered)
    mean = sum(used) / total_c if total_c else 0.0
    profile = [used[h] / covered[h] if covered[h] >= 0.25 else None for h in range(24)]
    return profile, mean, total_c


def weekday_profile(incs: list[Increment]) -> list[float | None]:
    used, covered = [0.0] * 7, [0.0] * 7
    for inc in incs:
        day = inc.end.astimezone().weekday()
        used[day] += inc.delta
        covered[day] += inc.hours
    return [used[d] / covered[d] if covered[d] >= 0.5 else None for d in range(7)]


def project(level: float, now: datetime, until: datetime, top: float,
            profile: list[float | None], mean: float, weekdays: list[float | None]) -> list[Point]:
    known = [w for w in weekdays if w is not None]
    week_mean = statistics.fmean(known) if known else 0.0
    curve, t = [(now, level)], now
    while t < until:
        local = t.astimezone()
        rate = profile[local.hour]
        rate = mean if rate is None else rate
        wd = weekdays[local.weekday()]
        if wd is not None and week_mean > 0:
            rate *= 1 + WEEKDAY_DAMPING * (wd / week_mean - 1)
        t = min(t + STEP, until)
        level = min(top, level + max(0.0, rate) * STEP.total_seconds() / 3600)
        curve.append((t, level))
        if level >= top:
            break
    return curve


def project_constant(level: float, now: datetime, until: datetime, top: float,
                     rate: float) -> tuple[float, datetime | None]:
    hours = max(0.0, (until - now).total_seconds() / 3600)
    end = level + rate * hours
    if rate > 0 and end >= top:
        return top, now + timedelta(hours=(top - level) / rate)
    return min(top, end), None


def exhaustion(curve: list[Point], top: float) -> datetime | None:
    return next((t for t, v in curve if v >= top - 1e-6), None)


def forecast(readings: list[Reading], now: datetime | None = None) -> tuple[Forecast | None, str]:
    """Project a quota or balance series to its reset (or a fixed horizon). Returns (forecast, why)."""
    if not readings:
        return None, "no data"
    kind = readings[-1].kind
    if kind not in ("quota", "balance"):
        return None, f"no forecast for a {kind}"
    points = level_points(readings)
    if not points:
        return None, "no known ceiling, so no forecast"
    drop = reset_threshold(kind, points)
    last_t, level = points[-1]
    now = now or last_t
    recent = [p for p in points if p[0] >= last_t - timedelta(days=PROFILE_DAYS)]
    incs = increments(recent, drop)
    profile, mean, coverage = hourly_profile(incs)
    if coverage < MIN_COVERAGE_H:
        return None, f"history too short ({coverage:.0f} h observed, {MIN_COVERAGE_H:.0f} h needed)"
    reset_at = parse_iso(readings[-1].reset_at)
    if kind == "quota" and reset_at and reset_at > now:
        target = reset_at
    else:
        target = now + (QUOTA_HORIZON if kind == "quota" else BALANCE_HORIZON)
    top = ceiling(kind)
    curve = project(level, now, target, top, profile, mean, weekday_profile(incs))
    base_end, base_exhaust = project_constant(level, now, target, top, mean)
    display = [(t, from_level(kind, v)) for t, v in curve]
    return Forecast(
        method=METHOD, target_at=target, now_value=from_level(kind, level),
        projected=from_level(kind, curve[-1][1]), exhaust_at=exhaustion(curve, top),
        coverage_h=coverage, rate_per_day=mean * 24,
        baseline_projected=from_level(kind, base_end), baseline_exhaust_at=base_exhaust,
        curve=_thin(display),
    ), ""


def _thin(curve: list[Point], max_points: int = 200) -> list[Point]:
    if len(curve) <= max_points:
        return curve
    step = len(curve) / (max_points - 1)
    return [curve[int(i * step)] for i in range(max_points - 1)] + [curve[-1]]
