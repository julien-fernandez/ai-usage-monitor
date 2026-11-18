from __future__ import annotations

import json

from ai_usage_monitor.collect import collect, run_probes
from ai_usage_monitor.models import ProbeError, Reading
from ai_usage_monitor.providers import PROVIDERS, elevenlabs
from ai_usage_monitor.providers.base import Provider
from ai_usage_monitor.store import Store

from .conftest import FakeHttp, ok


def test_no_key_means_every_probe_is_skipped(tmp_path):
    env = {"CLAUDE_PROJECTS_DIR": str(tmp_path / "missing")}
    result = run_probes(env, FakeHttp({}))
    assert result.readings == [] and result.errors == {}
    assert set(result.skipped) == {p.name for p in PROVIDERS}
    assert result.skipped["elevenlabs"] == "ELEVENLABS_API_KEY not set"


def test_blank_key_counts_as_missing():
    assert elevenlabs.PROVIDER.skip_reason({"ELEVENLABS_API_KEY": "   "}) == "ELEVENLABS_API_KEY not set"


def test_failing_probe_does_not_stop_others(tmp_path):
    def boom(env, http):
        raise ProbeError("HTTP 500")

    def crash(env, http):
        raise KeyError("surprise")

    providers = [Provider("broken", "Broken", "BROKEN_KEY", boom),
                 Provider("crashy", "Crashy", "CRASHY_KEY", crash),
                 elevenlabs.PROVIDER]
    env = {"BROKEN_KEY": "x", "CRASHY_KEY": "x", "ELEVENLABS_API_KEY": "your-key-here"}
    http = FakeHttp({("GET", elevenlabs.URL): ok("elevenlabs_subscription.json")})
    result = run_probes(env, http, providers)
    assert result.errors["broken"] == "HTTP 500"
    assert result.errors["crashy"].startswith("KeyError")
    assert [r.provider for r in result.readings] == ["elevenlabs"]


def test_collect_stores_and_writes_latest(tmp_path):
    env = {"ELEVENLABS_API_KEY": "your-key-here", "CLAUDE_PROJECTS_DIR": str(tmp_path / "missing")}
    http = FakeHttp({("GET", elevenlabs.URL): ok("elevenlabs_subscription.json")})
    lines: list[str] = []
    store = Store(tmp_path / "history.db")
    result = collect(env, store, tmp_path / "latest.json", http=http, echo=lines.append)
    assert not result.errors
    assert store.series("elevenlabs", "Monthly characters")[0].value == 41250
    latest = json.loads((tmp_path / "latest.json").read_text())
    assert latest["readings"][0]["pct"] == 41.2
    assert "your-key-here" not in (tmp_path / "latest.json").read_text()
    assert any(line.strip().startswith("skip   openrouter") for line in lines)


def test_reading_rejects_unknown_kind():
    import pytest
    with pytest.raises(ValueError):
        Reading("x", "y", "percentage", 1.0, "u")
