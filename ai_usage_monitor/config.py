from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path


def data_dir(env: Mapping[str, str] | None = None) -> Path:
    env = os.environ if env is None else env
    return Path(env.get("AI_USAGE_DATA") or "data")


def history_db(env: Mapping[str, str] | None = None) -> Path:
    return data_dir(env) / "history.db"


def demo_db(env: Mapping[str, str] | None = None) -> Path:
    return data_dir(env) / "demo.db"
