from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from ..models import Reading
from ..net import HttpClient

ProbeFn = Callable[[Mapping[str, str], HttpClient], list[Reading]]


@dataclass(frozen=True)
class Provider:
    name: str
    title: str
    env_var: str | None
    probe: ProbeFn
    availability: Callable[[Mapping[str, str]], str | None] | None = None

    def skip_reason(self, env: Mapping[str, str]) -> str | None:
        if self.availability is not None:
            return self.availability(env)
        if self.env_var and not env.get(self.env_var, "").strip():
            return f"{self.env_var} not set"
        return None

    def key(self, env: Mapping[str, str]) -> str:
        return env.get(self.env_var or "", "").strip()
