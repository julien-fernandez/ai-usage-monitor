from __future__ import annotations

import json
from pathlib import Path

from ai_usage_monitor.models import ProbeError
from ai_usage_monitor.net import Response

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FakeHttp:
    def __init__(self, routes: dict[tuple[str, str], Response]) -> None:
        self.routes = routes
        self.calls: list[tuple[str, str, dict, dict | None]] = []

    def request(self, method, url, headers=None, payload=None) -> Response:
        self.calls.append((method, url, headers or {}, payload))
        if (method, url) not in self.routes:
            raise AssertionError(f"unexpected call {method} {url}")
        return self.routes[(method, url)]

    def get_json(self, url, headers=None):
        return self._json(self.request("GET", url, headers))

    def post_json(self, url, headers=None, payload=None):
        return self._json(self.request("POST", url, headers, payload))

    @staticmethod
    def _json(resp: Response):
        if resp.status >= 400:
            raise ProbeError(f"HTTP {resp.status}")
        return resp.json()


def ok(name: str) -> Response:
    return Response(200, {}, (FIXTURES / name).read_bytes())

