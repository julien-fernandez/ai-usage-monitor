from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from . import __version__
from .models import ProbeError

USER_AGENT = f"ai-usage-monitor/{__version__}"


@dataclass
class Response:
    status: int
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""

    def json(self) -> dict:
        try:
            return json.loads(self.body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise ProbeError("response is not valid JSON") from exc


class HttpClient:
    def __init__(self, timeout: float = 20.0) -> None:
        self.timeout = timeout

    def request(self, method: str, url: str, headers: dict | None = None,
                payload: dict | None = None) -> Response:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        all_headers = {"User-Agent": USER_AGENT, "Accept": "application/json", **(headers or {})}
        if data is not None:
            all_headers.setdefault("Content-Type", "application/json")
        req = urllib.request.Request(url, data=data, headers=all_headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return Response(resp.status, _lower(resp.headers.items()), resp.read())
        except urllib.error.HTTPError as exc:
            return Response(exc.code, _lower(exc.headers.items()), exc.read())
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ProbeError(f"network error: {getattr(exc, 'reason', exc)}") from exc

    def get_json(self, url: str, headers: dict | None = None) -> dict:
        return _checked(self.request("GET", url, headers))

    def post_json(self, url: str, headers: dict | None = None, payload: dict | None = None) -> dict:
        return _checked(self.request("POST", url, headers, payload))


def _lower(items) -> dict[str, str]:
    return {k.lower(): v for k, v in items}


def _checked(resp: Response) -> dict:
    if resp.status >= 400:
        raise ProbeError(f"HTTP {resp.status}")
    return resp.json()
