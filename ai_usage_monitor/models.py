from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

KINDS = ("quota", "balance", "volume", "rate")


class ProbeError(RuntimeError):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@dataclass
class Reading:
    """One normalised measurement.

    kind is one of: quota (value consumed out of a known limit), balance (value remaining,
    no ceiling), volume (a count with no limit) and rate (short rate-limit window headroom).
    """

    provider: str
    metric: str
    kind: str
    value: float | None
    unit: str
    limit: float | None = None
    reset_at: str | None = None
    detail: str = ""
    at: str = field(default_factory=lambda: iso(utcnow()) or "")

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"unknown kind {self.kind!r}")

    @property
    def pct(self) -> float | None:
        if self.value is None or not self.limit:
            return None
        return round(100.0 * self.value / self.limit, 1)

    def as_dict(self) -> dict:
        return {**asdict(self), "pct": self.pct}


def fmt_number(value: float | None, unit: str = "") -> str:
    if value is None:
        return "n/a"
    if unit in ("USD", "EUR"):
        return f"{value:,.2f} {unit}"
    if abs(value) >= 1_000_000:
        text = f"{value / 1_000_000:.2f} M"
    elif abs(value) >= 10_000:
        text = f"{value:,.0f}"
    elif float(value).is_integer():
        text = f"{value:,.0f}"
    else:
        text = f"{value:,.1f}"
    return f"{text} {unit}".strip()


def fmt_delay(target: datetime | None, now: datetime) -> str:
    if target is None:
        return ""
    seconds = (target - now).total_seconds()
    if seconds < 0:
        return "overdue"
    if seconds < 3600:
        return f"in {round(seconds / 60)} min"
    if seconds < 86400:
        return f"in {seconds / 3600:.0f} h"
    return f"in {seconds / 86400:.1f} d"


def fmt_when(target: datetime | None, now: datetime) -> str:
    if target is None:
        return ""
    return f"{fmt_delay(target, now)} ({target.astimezone(timezone.utc):%Y-%m-%d %H:%M} UTC)"
