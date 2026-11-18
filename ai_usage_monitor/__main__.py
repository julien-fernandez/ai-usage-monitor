"""Command line: collect readings, render the report, or run the offline demo."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import __version__, config, demo, report
from .collect import collect
from .store import Store


def _report(store: Store, out: Path, is_demo: bool) -> Path:
    doc = report.build(store, demo=is_demo)
    page = report.write(doc, out)
    for m in doc["metrics"]:
        print(f"  {m['status']:<5} {m['provider']:<12} {m['metric']:<22} {m['headline']:<18} {m['outlook']}")
    print(f"  report written to {page} and {page.with_name('report.json')}")
    return page


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ai_usage_monitor", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("collect", help="query every configured provider and store the readings")
    rep = sub.add_parser("report", help="render the HTML and JSON report from stored readings")
    rep.add_argument("--out", type=Path, default=Path("out"))
    dem = sub.add_parser("demo", help="seed fictional readings and render the report, offline")
    dem.add_argument("--out", type=Path, default=Path("out"))
    args = parser.parse_args(argv)
    env = dict(os.environ)

    if args.command == "collect":
        result = collect(env, Store(config.history_db(env)), config.data_dir(env) / "latest.json")
        return 1 if result.errors else 0
    if args.command == "report":
        _report(Store(config.history_db(env)), args.out, is_demo=False)
        return 0
    path = config.demo_db(env)
    path.unlink(missing_ok=True)
    store = Store(path)
    print(f"  seeded {demo.seed(store)} fictional readings in {path}")
    _report(store, args.out, is_demo=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
