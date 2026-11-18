from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from ai_usage_monitor import trends
from ai_usage_monitor.models import Reading, iso

T0 = datetime(2026, 11, 1, 0, 0, tzinfo=timezone.utc)


def quota_series(rate_pct_per_h: float, hours: int, start_pct: float = 0.0, reset_at=None, every_h=1):
    return [Reading("p", "m", "quota", start_pct + rate_pct_per_h * h, "u", limit=100.0,
                    reset_at=iso(reset_at) if reset_at else None, at=iso(T0 + timedelta(hours=h)) or "")
            for h in range(0, hours + 1, every_h)]


def test_increments_skip_resets_and_long_gaps():
    pts = [(T0, 10.0), (T0 + timedelta(hours=1), 12.0), (T0 + timedelta(hours=2), 1.0),
           (T0 + timedelta(hours=3), 3.0), (T0 + timedelta(hours=9), 5.0)]
    incs = trends.increments(pts, drop=2.0, max_gap_h=3.0)
    assert [(i.delta, i.hours) for i in incs] == [(2.0, 1.0), (2.0, 1.0)]


def test_current_cycle_starts_after_last_reset():
    pts = [(T0 + timedelta(hours=h), v) for h, v in enumerate([50, 70, 90, 3, 8, 12])]
    assert [v for _, v in trends.current_cycle(pts, 2.0)] == [3, 8, 12]


def test_hourly_profile_spreads_increments_over_clock_hours():
    inc = trends.Increment(T0, T0 + timedelta(hours=2), 4.0)
    profile, mean, coverage = trends.hourly_profile([inc])
    assert mean == pytest.approx(2.0)
    assert coverage == pytest.approx(2.0)
    assert sum(1 for p in profile if p is not None) in (2, 3)


def test_constant_quota_forecast_hits_ceiling_at_expected_time():
    readings = quota_series(0.5, 48)
    now = T0 + timedelta(hours=48)
    fc, why = trends.forecast(readings, now=now)
    assert why == "" and fc is not None
    assert fc.now_value == pytest.approx(24.0)
    assert fc.rate_per_day == pytest.approx(12.0)
    assert fc.exhaust_at is not None
    assert abs((fc.exhaust_at - (now + timedelta(hours=152))).total_seconds()) <= 15 * 60
    assert fc.baseline_exhaust_at == now + timedelta(hours=152)


def test_quota_forecast_stops_at_reset_when_quota_holds():
    reset = T0 + timedelta(hours=72)
    readings = quota_series(0.25, 48, reset_at=reset)
    fc, _ = trends.forecast(readings, now=T0 + timedelta(hours=48))
    assert fc.target_at == reset
    assert fc.exhaust_at is None
    assert fc.projected == pytest.approx(18.0, abs=0.01)


def test_balance_forecast_projects_time_to_zero():
    readings = [Reading("p", "b", "balance", 100.0 - 2.0 * h, "USD", at=iso(T0 + timedelta(hours=h)) or "")
                for h in range(0, 25)]
    fc, _ = trends.forecast(readings, now=T0 + timedelta(hours=24))
    assert fc.now_value == pytest.approx(52.0)
    assert fc.exhaust_at is not None
    assert abs((fc.exhaust_at - (T0 + timedelta(hours=50))).total_seconds()) <= 15 * 60
    assert fc.curve[-1][1] == pytest.approx(0.0)


def test_balance_top_up_is_treated_as_a_new_cycle():
    values = [50, 48, 46, 96, 94, 92]
    pts = [(T0 + timedelta(hours=h), -v) for h, v in enumerate(values)]
    incs = trends.increments(pts, trends.reset_threshold("balance", pts))
    assert len(incs) == 4 and all(i.delta == pytest.approx(2.0) for i in incs)


def test_short_history_gives_no_forecast():
    fc, why = trends.forecast(quota_series(1.0, 6))
    assert fc is None and "too short" in why


def test_volume_and_quota_without_ceiling_get_no_forecast():
    vol = [Reading("p", "v", "volume", 5.0, "h", at=iso(T0) or "")]
    assert trends.forecast(vol)[0] is None
    no_limit = [Reading("p", "q", "quota", 5.0, "u", limit=None, at=iso(T0) or "")]
    fc, why = trends.forecast(no_limit)
    assert fc is None and "no known ceiling" in why
