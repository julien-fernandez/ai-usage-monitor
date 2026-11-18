from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from pathlib import Path

from .models import Reading

SCHEMA = """
CREATE TABLE IF NOT EXISTS readings (
    at        TEXT NOT NULL,
    provider  TEXT NOT NULL,
    metric    TEXT NOT NULL,
    kind      TEXT NOT NULL,
    value     REAL,
    unit      TEXT NOT NULL,
    limit_val REAL,
    reset_at  TEXT,
    detail    TEXT,
    PRIMARY KEY (provider, metric, at)
);
"""


class Store:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as cx:
            cx.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        cx = sqlite3.connect(self.path)
        cx.row_factory = sqlite3.Row
        return cx

    def add(self, readings: Iterable[Reading]) -> int:
        rows = [(r.at, r.provider, r.metric, r.kind, r.value, r.unit, r.limit, r.reset_at, r.detail)
                for r in readings]
        with self._connect() as cx:
            cur = cx.executemany(
                "INSERT OR REPLACE INTO readings VALUES (?,?,?,?,?,?,?,?,?)", rows)
            return cur.rowcount

    def metrics(self) -> list[tuple[str, str]]:
        with self._connect() as cx:
            return [(r["provider"], r["metric"]) for r in cx.execute(
                "SELECT DISTINCT provider, metric FROM readings ORDER BY provider, metric")]

    def series(self, provider: str, metric: str, since: str | None = None) -> list[Reading]:
        sql = "SELECT * FROM readings WHERE provider=? AND metric=?"
        args: list = [provider, metric]
        if since:
            sql += " AND at>=?"
            args.append(since)
        with self._connect() as cx:
            return [Reading(r["provider"], r["metric"], r["kind"], r["value"], r["unit"],
                            limit=r["limit_val"], reset_at=r["reset_at"], detail=r["detail"] or "",
                            at=r["at"])
                    for r in cx.execute(sql + " ORDER BY at", args)]
