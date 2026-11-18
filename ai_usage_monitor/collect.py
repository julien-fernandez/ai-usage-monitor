from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from .models import ProbeError, Reading, iso, utcnow
from .net import HttpClient
from .providers import PROVIDERS, Provider
from .store import Store


@dataclass
class CollectResult:
    readings: list[Reading] = field(default_factory=list)
    skipped: dict[str, str] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"at": iso(utcnow()), "readings": [r.as_dict() for r in self.readings],
                "skipped": self.skipped, "errors": self.errors}


def run_probes(env: Mapping[str, str], http: HttpClient,
               providers: list[Provider] | None = None) -> CollectResult:
    result = CollectResult()
    for provider in providers if providers is not None else PROVIDERS:
        reason = provider.skip_reason(env)
        if reason:
            result.skipped[provider.name] = reason
            continue
        try:
            result.readings.extend(provider.probe(env, http))
        except ProbeError as exc:
            result.errors[provider.name] = str(exc)
        except Exception as exc:
            result.errors[provider.name] = f"{type(exc).__name__}: {exc}"[:200]
    return result


def describe(reading: Reading) -> str:
    pct = f"{reading.pct:5.1f} %" if reading.pct is not None else "      -"
    return f"  ok     {reading.provider:<12} {reading.metric:<22} {pct}  {reading.detail}"


def collect(env: Mapping[str, str], store: Store, latest: Path, http: HttpClient | None = None,
            echo: Callable[[str], None] = print) -> CollectResult:
    result = run_probes(env, http or HttpClient())
    store.add(result.readings)
    latest.parent.mkdir(parents=True, exist_ok=True)
    latest.write_text(json.dumps(result.as_dict(), indent=1), encoding="utf-8")
    for reading in result.readings:
        echo(describe(reading))
    for name, reason in result.skipped.items():
        echo(f"  skip   {name:<12} {reason}")
    for name, message in result.errors.items():
        echo(f"  error  {name:<12} {message}")
    echo(f"  {len(result.readings)} reading(s) stored in {store.path}, "
         f"{len(result.skipped)} skipped, {len(result.errors)} failed")
    return result
