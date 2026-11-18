from __future__ import annotations

import json

from ai_usage_monitor.__main__ import main


def test_demo_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_USAGE_DATA", str(tmp_path / "data"))
    out = tmp_path / "out"
    assert main(["demo", "--out", str(out)]) == 0
    page = (out / "index.html").read_text(encoding="utf-8")
    doc = json.loads((out / "report.json").read_text(encoding="utf-8"))
    providers = {m["provider"] for m in doc["metrics"]}
    assert providers == {"elevenlabs", "openrouter", "deepgram", "groq", "claude_code"}
    for title in ("ElevenLabs", "OpenRouter", "Deepgram", "Groq", "Claude Code"):
        assert title in page
    assert "fictional" in page
    by = {m["provider"]: m for m in doc["metrics"]}
    assert by["elevenlabs"]["forecast"]["exhaust_at"] is not None
    assert by["deepgram"]["forecast"]["exhaust_at"] is not None
    assert by["claude_code"]["forecast"] is None
    assert by["claude_code"]["latest"]["pct"] is None
    assert not (tmp_path / "data" / "history.db").exists()


def test_report_with_empty_history(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_USAGE_DATA", str(tmp_path / "data"))
    assert main(["report", "--out", str(tmp_path / "out")]) == 0
    assert "No readings yet" in (tmp_path / "out" / "index.html").read_text(encoding="utf-8")


def test_collect_without_keys_exits_zero(tmp_path, monkeypatch, capsys):
    for var in ("ELEVENLABS_API_KEY", "OPENROUTER_API_KEY", "DEEPGRAM_API_KEY", "GLADIA_API_KEY",
                "GROQ_API_KEY", "FIREFLIES_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("AI_USAGE_DATA", str(tmp_path / "data"))
    monkeypatch.setenv("CLAUDE_PROJECTS_DIR", str(tmp_path / "missing"))
    assert main(["collect"]) == 0
    out = capsys.readouterr().out
    assert "skip   groq         GROQ_API_KEY not set" in out
    assert "0 reading(s) stored" in out
