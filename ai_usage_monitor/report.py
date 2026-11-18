from __future__ import annotations

import html
import json
from datetime import datetime, timedelta
from pathlib import Path

from . import __version__
from .models import Reading, fmt_number, fmt_when, iso, parse_iso, utcnow
from .providers import PROVIDERS
from .store import Store
from .trends import Forecast, forecast

HISTORY_DAYS = 14
STALE_AFTER = timedelta(hours=6)
WARN_PCT, CRIT_PCT = 70.0, 90.0
CRIT_SOON, WARN_SOON = timedelta(days=2), timedelta(days=14)
BALANCE_CRIT, BALANCE_WARN = timedelta(days=3), timedelta(days=14)
SEVERITY = {"crit": 0, "warn": 1, "ok": 2, "info": 3}
TITLES = {p.name: p.title for p in PROVIDERS}


def display_value(r: Reading) -> float | None:
    return r.pct if r.kind in ("quota", "rate") else r.value


def assess(latest: Reading, fc: Forecast | None, now: datetime) -> str:
    if latest.kind == "volume":
        return "info"
    status = "ok"
    if latest.kind in ("quota", "rate") and latest.pct is not None:
        status = "crit" if latest.pct >= CRIT_PCT else "warn" if latest.pct >= WARN_PCT else "ok"
    if fc and fc.exhaust_at:
        left = fc.exhaust_at - now
        if latest.kind == "balance":
            soon = "crit" if left <= BALANCE_CRIT else "warn" if left <= BALANCE_WARN else "ok"
        else:
            soon = "crit" if left <= CRIT_SOON else "warn"
        status = min(status, soon, key=SEVERITY.get)
    return status


def headline(latest: Reading) -> str:
    if latest.kind in ("quota", "rate") and latest.pct is not None:
        return f"{latest.pct:.0f} % used"
    if latest.kind == "balance":
        return f"{fmt_number(latest.value, latest.unit)} left"
    return fmt_number(latest.value, latest.unit)


def outlook(latest: Reading, fc: Forecast | None, why: str, now: datetime) -> str:
    if latest.kind == "volume":
        return "Volume only: no published ceiling, so no percentage and no forecast."
    if latest.kind == "rate":
        return "Short rate-limit window: shown as headroom, not forecast."
    if fc is None:
        return f"No forecast: {why}."
    if latest.kind == "balance":
        if fc.exhaust_at:
            return f"At the current pace the balance runs out {fmt_when(fc.exhaust_at, now)}."
        return f"Lasts beyond {fc.target_at:%Y-%m-%d} at the current pace."
    if latest.reset_at:
        reset = f"the reset {fmt_when(fc.target_at, now)}"
    else:
        reset = f"{fc.target_at:%Y-%m-%d} (no reset date published)"
    if fc.exhaust_at:
        return f"Projected to run out {fmt_when(fc.exhaust_at, now)}, before {reset}."
    return f"Projected {fc.projected:.0f} % by {reset}."


def build(store: Store, now: datetime | None = None, demo: bool = False) -> dict:
    now = now or utcnow()
    since = iso(now - timedelta(days=HISTORY_DAYS))
    metrics = []
    for provider, metric in store.metrics():
        readings = store.series(provider, metric)
        if not readings:
            continue
        latest = readings[-1]
        fc, why = forecast(readings, now=now)
        last_at = parse_iso(latest.at)
        recent = [r for r in readings if r.at >= (since or "")]
        metrics.append({
            "provider": provider,
            "provider_title": TITLES.get(provider, provider),
            "metric": metric,
            "kind": latest.kind,
            "unit": latest.unit,
            "status": assess(latest, fc, now),
            "stale": bool(last_at and now - last_at > STALE_AFTER),
            "headline": headline(latest),
            "outlook": outlook(latest, fc, why, now),
            "latest": latest.as_dict(),
            "history": [[r.at, display_value(r)] for r in recent],
            "forecast": fc.as_dict() if fc else None,
        })
    metrics.sort(key=lambda m: (SEVERITY[m["status"]], m["provider"], m["metric"]))
    return {"generated_at": iso(now), "demo": demo, "version": __version__,
            "history_days": HISTORY_DAYS, "metrics": metrics}


def _sparkline(m: dict, now: datetime) -> str:
    w, h, pad = 320, 84, 4
    hist = [(parse_iso(t), v) for t, v in m["history"] if v is not None]
    fc = m["forecast"] or {}
    pct_scale = m["kind"] in ("quota", "rate")
    curve = [(parse_iso(t), v) for t, v in fc.get("curve") or []]
    if not hist:
        return ""
    t0 = now - timedelta(days=HISTORY_DAYS)
    t1 = now + min(timedelta(days=HISTORY_DAYS), (curve[-1][0] - now) if curve else timedelta(0))
    t1 = max(t1, hist[-1][0] + timedelta(minutes=1))
    curve = [(t, v) for t, v in curve if t <= t1]
    values = [v for _, v in hist + curve]
    lo, hi = (0.0, 100.0) if pct_scale else (min(0.0, min(values)), max(values) or 1.0)
    span_t = (t1 - t0).total_seconds() or 1.0
    span_v = (hi - lo) or 1.0

    def xy(t: datetime, v: float) -> str:
        x = pad + (w - 2 * pad) * max(0.0, (t - t0).total_seconds()) / span_t
        y = h - pad - (h - 2 * pad) * (v - lo) / span_v
        return f"{x:.1f},{y:.1f}"

    parts = [f'<svg class="spark" viewBox="0 0 {w} {h}" role="img" '
             f'aria-label="{html.escape(m["metric"])}: last {HISTORY_DAYS} days'
             f'{" and forecast" if curve else ""}">']
    if pct_scale:
        y100 = xy(t0, 100.0).split(",")[1]
        parts.append(f'<line class="limit" x1="{pad}" x2="{w - pad}" y1="{y100}" y2="{y100}"/>')
    xnow = xy(now, lo).split(",")[0]
    parts.append(f'<line class="now" x1="{xnow}" x2="{xnow}" y1="{pad}" y2="{h - pad}"/>')
    parts.append(f'<polyline class="hist" points="{" ".join(xy(t, v) for t, v in hist)}"/>')
    if curve:
        parts.append(f'<polyline class="fc" points="{" ".join(xy(t, v) for t, v in curve)}"/>')
    parts.append("</svg>")
    return "".join(parts)


def _card(m: dict, now: datetime) -> str:
    e = html.escape
    pct = m["latest"]["pct"]
    bar = ""
    if pct is not None and m["kind"] in ("quota", "rate"):
        bar = (f'<div class="bar" role="meter" aria-valuemin="0" aria-valuemax="100" '
               f'aria-valuenow="{pct:.0f}"><span style="width:{min(100.0, pct):.1f}%"></span></div>')
    stale = '<span class="tag stale">stale</span>' if m["stale"] else ""
    reading_at = parse_iso(m["latest"]["at"])
    return f"""
<article class="card {m['status']}">
  <header><span class="provider">{e(m['provider_title'])}</span>
  <span class="tag {m['status']}">{m['status']}</span>{stale}</header>
  <h2>{e(m['metric'])}</h2>
  <p class="headline">{e(m['headline'])}</p>
  {bar}
  {_sparkline(m, now)}
  <p class="outlook">{e(m['outlook'])}</p>
  <p class="detail">{e(m['latest']['detail'])}</p>
  <p class="meta">Last reading {e(f"{reading_at:%Y-%m-%d %H:%M} UTC" if reading_at else "unknown")}</p>
</article>"""


CSS = """
:root{--bg:#f6f7f9;--card:#fff;--text:#1b1f24;--muted:#5b6470;--line:#d9dde3;
--hist:#2a6fdb;--fc:#c2581c;--ok:#1f8a5b;--warn:#b7791f;--crit:#c53030;--info:#5b6470;--track:#e8ebef}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#111418;--card:#1b2026;
--text:#e7eaee;--muted:#9aa4b1;--line:#2c333c;--hist:#5b9bf0;--fc:#ec8a4f;--ok:#3fbf86;
--warn:#e0a53e;--crit:#f06565;--info:#9aa4b1;--track:#2c333c}}
:root[data-theme="dark"]{--bg:#111418;--card:#1b2026;--text:#e7eaee;--muted:#9aa4b1;--line:#2c333c;
--hist:#5b9bf0;--fc:#ec8a4f;--ok:#3fbf86;--warn:#e0a53e;--crit:#f06565;--info:#9aa4b1;--track:#2c333c}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:15px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px 48px}
h1{font-size:1.5rem;margin:0 0 4px}
.sub{color:var(--muted);margin:0 0 16px}
.banner{border:1px dashed var(--warn);border-radius:8px;padding:8px 12px;margin:0 0 16px}
.summary{display:flex;gap:12px;flex-wrap:wrap;margin:0 0 20px;padding:0;list-style:none}
.summary li{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px 14px}
.summary b{font-size:1.2rem;margin-right:6px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px}
.card{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--info);border-radius:10px;padding:14px 16px}
.card.ok{border-left-color:var(--ok)}.card.warn{border-left-color:var(--warn)}.card.crit{border-left-color:var(--crit)}
.card header{display:flex;gap:8px;align-items:center}
.provider{color:var(--muted);font-size:.85rem;flex:1}
.tag{font-size:.75rem;text-transform:uppercase;letter-spacing:.04em;padding:1px 8px;border-radius:99px;border:1px solid currentColor}
.tag.ok{color:var(--ok)}.tag.warn{color:var(--warn)}.tag.crit{color:var(--crit)}.tag.info,.tag.stale{color:var(--muted)}
h2{font-size:1rem;margin:6px 0 0}
.headline{font-size:1.6rem;font-weight:650;margin:2px 0 8px}
.bar{height:8px;background:var(--track);border-radius:99px;overflow:hidden;margin-bottom:8px}
.bar span{display:block;height:100%;background:var(--hist)}
.crit .bar span{background:var(--crit)}.warn .bar span{background:var(--warn)}
.spark{width:100%;height:auto;display:block}
.spark .hist{fill:none;stroke:var(--hist);stroke-width:1.6}
.spark .fc{fill:none;stroke:var(--fc);stroke-width:1.6;stroke-dasharray:4 3}
.spark .limit{stroke:var(--line);stroke-dasharray:2 3}
.spark .now{stroke:var(--line)}
.outlook{margin:8px 0 4px}
.detail,.meta{color:var(--muted);font-size:.85rem;margin:2px 0}
.legend{color:var(--muted);font-size:.85rem;margin:20px 0 0}
.legend i{display:inline-block;width:18px;height:0;border-top:2px solid var(--hist);vertical-align:middle;margin:0 4px}
.legend i.fc{border-top:2px dashed var(--fc)}
footer{color:var(--muted);font-size:.8rem;margin-top:28px}
"""


def render_html(doc: dict) -> str:
    now = parse_iso(doc["generated_at"]) or utcnow()
    counts = {s: sum(1 for m in doc["metrics"] if m["status"] == s) for s in SEVERITY}
    cards = "".join(_card(m, now) for m in doc["metrics"]) or \
        "<p>No readings yet. Run <code>python -m ai_usage_monitor collect</code> first.</p>"
    banner = ('<p class="banner">Demo data: every value on this page is fictional and was '
              'generated locally, without any network call.</p>' if doc["demo"] else "")
    summary = "".join(f"<li><b>{counts[s]}</b>{label}</li>" for s, label in
                      (("crit", "critical"), ("warn", "warning"), ("ok", "fine"), ("info", "volume only")))
    providers = len({m["provider"] for m in doc["metrics"]})
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI Usage Monitor</title><style>{CSS}</style></head>
<body><main>
<h1>AI Usage Monitor</h1>
<p class="sub">{providers} provider(s), {len(doc['metrics'])} metric(s). Generated {now:%Y-%m-%d %H:%M} UTC.</p>
{banner}
<ul class="summary">{summary}</ul>
<section class="grid">{cards}</section>
<p class="legend"><i></i>last {doc['history_days']} days <i class="fc"></i>forecast (hourly usage profile)</p>
<footer>ai-usage-monitor {doc['version']}. Percentages appear only where the provider publishes a ceiling.
Raw data: <a href="report.json">report.json</a>.</footer>
</main></body></html>
"""


def write(doc: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(json.dumps(doc, indent=1), encoding="utf-8")
    page = out_dir / "index.html"
    page.write_text(render_html(doc), encoding="utf-8")
    return page
