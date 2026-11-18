from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ai_usage_monitor.models import ProbeError
from ai_usage_monitor.net import Response
from ai_usage_monitor.providers import claude_code, deepgram, elevenlabs, fireflies, gladia, groq, openrouter

from .conftest import FIXTURES, FakeHttp, load, ok

NOW = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)


def test_elevenlabs_quota_with_reset():
    http = FakeHttp({("GET", elevenlabs.URL): ok("elevenlabs_subscription.json")})
    [r] = elevenlabs.probe({"ELEVENLABS_API_KEY": "your-key-here"}, http)
    assert (r.kind, r.value, r.limit, r.pct) == ("quota", 41250, 100000, 41.2)
    assert r.reset_at == "2026-11-23T00:00:00+00:00"
    assert http.calls[0][2]["xi-api-key"] == "your-key-here"


def test_elevenlabs_rejects_payload_without_limit():
    with pytest.raises(ProbeError):
        elevenlabs.parse({"character_count": 3})


def test_openrouter_credits():
    [r] = openrouter.parse(load("openrouter_credits.json"))
    assert (r.kind, r.value, r.limit, r.pct, r.unit) == ("quota", 7.5, 20.0, 37.5, "USD")
    assert "12.50 USD left" in r.detail


def test_deepgram_discovers_projects_and_sums_balances():
    http = FakeHttp({
        ("GET", f"{deepgram.API}/projects"): ok("deepgram_projects.json"),
        ("GET", f"{deepgram.API}/projects/project-a/balances"): ok("deepgram_balances_a.json"),
        ("GET", f"{deepgram.API}/projects/project-b/balances"): ok("deepgram_balances_b.json"),
    })
    [r] = deepgram.probe({"DEEPGRAM_API_KEY": "your-key-here"}, http)
    assert (r.kind, r.value, r.unit, r.pct) == ("balance", 129.75, "USD", None)
    assert http.calls[0][2]["Authorization"] == "Token your-key-here"


def test_deepgram_without_projects_is_an_error():
    http = FakeHttp({("GET", f"{deepgram.API}/projects"): Response(200, {}, b'{"projects": []}')})
    with pytest.raises(ProbeError, match="no project"):
        deepgram.probe({"DEEPGRAM_API_KEY": "your-key-here"}, http)


def test_gladia_sums_both_channels():
    http = FakeHttp({
        ("POST", gladia.URL.format(channel="pre-recorded")): ok("gladia_prerecorded.json"),
        ("POST", gladia.URL.format(channel="live")): ok("gladia_live.json"),
    })
    [r] = gladia.probe({"GLADIA_API_KEY": "your-key-here"}, http)
    assert (r.kind, r.value, r.unit) == ("volume", 4.25, "h")
    assert "50 requests" in r.detail


def test_groq_reads_rate_limit_headers():
    readings = groq.parse(load("groq_headers.json"), now=NOW)
    tokens = next(r for r in readings if r.unit == "tokens")
    assert (tokens.kind, tokens.value, tokens.limit, tokens.pct) == ("rate", 1500, 6000, 25.0)
    assert tokens.reset_at == "2026-11-18T12:01:30+00:00"
    assert len(readings) == 2


def test_groq_rate_limited_response_still_parses():
    headers = load("groq_headers.json")
    http = FakeHttp({("POST", groq.URL): Response(429, headers, b"{}")})
    readings = groq.probe({"GROQ_API_KEY": "your-key-here"}, http)
    assert readings[0].limit == 6000


def test_groq_bad_key_is_an_error():
    http = FakeHttp({("POST", groq.URL): Response(401, {}, b"{}")})
    with pytest.raises(ProbeError, match="401"):
        groq.probe({"GROQ_API_KEY": "your-key-here"}, http)


@pytest.mark.parametrize("text,seconds", [("6s", 6), ("1m30.5s", 90.5), ("2h0m1s", 7201), ("250ms", 0.25), ("", None)])
def test_groq_durations(text, seconds):
    assert groq.parse_duration(text) == seconds


def test_fireflies_is_a_volume_without_declared_limit():
    [r] = fireflies.parse(load("fireflies_user.json"))
    assert (r.kind, r.value, r.pct) == ("volume", 812.4, None)


def test_fireflies_is_a_quota_with_declared_limit():
    http = FakeHttp({("POST", fireflies.URL): ok("fireflies_user.json")})
    [r] = fireflies.probe({"FIREFLIES_API_KEY": "your-key-here", "FIREFLIES_MONTHLY_MINUTES": "1200"}, http)
    assert (r.kind, r.limit, r.pct) == ("quota", 1200.0, 67.7)


def test_fireflies_graphql_error():
    with pytest.raises(ProbeError, match="denied"):
        fireflies.parse({"errors": [{"message": "denied"}]})


def test_claude_code_counts_last_24h_only(tmp_path):
    project = tmp_path / "some-project"
    project.mkdir()
    (project / "session.jsonl").write_bytes((FIXTURES / "claude_transcript.jsonl").read_bytes())
    r = claude_code.scan(tmp_path, now=NOW)
    assert (r.kind, r.value, r.pct) == ("volume", 3000, None)
    assert "5,100 cache tokens" in r.detail
    assert "not a quota" in r.detail


def test_claude_code_skipped_when_directory_missing(tmp_path):
    reason = claude_code.PROVIDER.skip_reason({"CLAUDE_PROJECTS_DIR": str(tmp_path / "missing")})
    assert reason and "not found" in reason


def test_claude_code_is_opt_in():
    assert claude_code.PROVIDER.skip_reason({}) is not None
