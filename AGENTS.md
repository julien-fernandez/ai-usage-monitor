# AGENTS.md

Instructions for a coding agent working on this repository. Run every command from the repository root.

## Rules

- Python 3.11+, standard library only at runtime. `pytest` is the only development dependency.
- No code comments. A docstring only where the intent is not obvious. Design reasons go in
  `docs/decisions/` (ADRs, in French, format Contexte / Décision / Conséquences).
- Use only official, documented provider APIs authenticated by an API key. Never add a probe that
  reads a web console, a session cookie or an undocumented endpoint (ADR 0001).
- Never compute a percentage without a ceiling published by the provider or declared by the user (ADR 0002).
- Tests must pass offline. Never call a real API in a test; use fixtures in `tests/fixtures/`.
- Never write an API key to disk, to the database, to `latest.json` or to the report.

## 1. Install

```bash
python3 -m venv .venv || uv venv --seed --clear .venv
. .venv/bin/activate
pip install -e '.[test]'
```

Expected: `Successfully installed ai-usage-monitor-0.1.0` (plus pytest). If `python3 -m venv` fails
with « ensurepip is not available » (Debian/Ubuntu without `python3-venv`), the `uv venv --seed --clear` fallback (it also replaces the partial `.venv` left by the failed attempt)
above creates the same environment.

## 2. Run the tests

```bash
python -m pytest -q
```

Expected: a last line `N passed`, no failure, no network access.

## 3. Run the demo locally

```bash
AI_USAGE_DATA=/tmp/aum-data python -m ai_usage_monitor demo --out /tmp/aum-out
```

Expected: `seeded ... fictional readings`, then one line per metric for `elevenlabs`, `openrouter`,
`deepgram`, `groq` and `claude_code`, then a `report written to` line naming `/tmp/aum-out/index.html` and `report.json`.
Check: `grep -c 'class="card' /tmp/aum-out/index.html` prints `5`.

## 4. Run the demo in Docker

```bash
docker build -t ai-usage-monitor .
mkdir -p out && docker run --rm -v "$PWD/out:/out" ai-usage-monitor
ls out
```

Expected: `index.html  report.json`. The container runs as uid 1000 (`app`); if `out/` belongs to
another user, run `chmod 777 out` or pass `--user "$(id -u)"`.
With Compose: `docker compose run --rm demo` (demo) and `docker compose run --rm monitor` (real
collect + report, reads `.env`).

## 5. Configure real collection

```bash
cp .env.example .env
```

Fill only the keys you have. Then:

```bash
set -a && . ./.env && set +a
python -m ai_usage_monitor collect
python -m ai_usage_monitor report --out out
```

Expected from `collect`: one `ok`, `skip` or `error` line for each of the 7 providers (the demo
shows only 5 of them) and a summary
`N reading(s) stored in data/history.db, N skipped, N failed`. Exit code 0, or 1 if a configured
provider failed. A missing key is a `skip`, never an error. `claude_code` is opt-in: it reads local
Claude Code transcripts only when `CLAUDE_PROJECTS_DIR` is set (nothing leaves the machine).

## 6. Add a provider

1. Create `ai_usage_monitor/providers/<name>.py` with:
   - `parse(payload) -> list[Reading]`: pure, no I/O. Choose the kind: `quota` (value consumed, `limit`
     set from the provider's response), `balance` (value remaining, no limit), `volume` (count, no limit)
     or `rate` (short rate-limit window). Set `reset_at` (ISO UTC) when the provider gives it. Raise
     `ProbeError` with a short message when the payload lacks the expected fields.
   - `probe(env, http) -> list[Reading]`: reads the key from `env`, calls `http.get_json`,
     `http.post_json` or `http.request`, returns `parse(...)`.
   - `PROVIDER = Provider("<name>", "<Title>", "<ENV_VAR>", probe)`.
2. Register `PROVIDER` in `ai_usage_monitor/providers/__init__.py` (`PROVIDERS` list).
3. Save a real response, with every identifier and amount replaced by fictional values, as
   `tests/fixtures/<name>_*.json`.
4. Add tests in `tests/test_providers.py`: the parse result (kind, value, limit, pct, reset_at), the
   probe with `FakeHttp` (URL and auth header), and one malformed payload raising `ProbeError`.
5. Add the variable with a comment line to `.env.example`, and a row to the providers table in `README.md`.
6. Run `python -m pytest -q`; all tests pass. `test_no_key_means_every_probe_is_skipped` checks the new
   provider is skipped without its key.

## Layout

- `ai_usage_monitor/models.py`: `Reading`, `ProbeError`, formatting helpers.
- `ai_usage_monitor/net.py`: `HttpClient` on `urllib`.
- `ai_usage_monitor/providers/`: one module per provider.
- `ai_usage_monitor/collect.py`: runs the probes, stores readings, writes `latest.json`.
- `ai_usage_monitor/store.py`: SQLite `readings` table.
- `ai_usage_monitor/trends.py`: increments, hourly and weekday profiles, forecast and baseline.
- `ai_usage_monitor/report.py`: status, outlook text, `report.json` and static `index.html`.
- `ai_usage_monitor/demo.py`: deterministic fictional readings.
