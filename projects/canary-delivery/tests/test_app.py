from __future__ import annotations

import json
import os
import signal
import threading
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from typing import Any

import pytest

from canary_demo import app
from canary_demo.app import Config, build_server


def get(base: str, path: str) -> tuple[int, str, str]:
    try:
        with urllib.request.urlopen(base + path, timeout=5) as resp:
            return resp.status, resp.headers["Content-Type"], resp.read().decode()
    except urllib.error.HTTPError as err:
        return err.code, err.headers["Content-Type"], err.read().decode()


@pytest.fixture
def serve() -> Iterator[Callable[..., str]]:
    """Start a server on a free port and return its base URL."""
    servers = []

    def start(config: Config, **kwargs: Any) -> str:
        server = build_server(config, **kwargs)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return f"http://127.0.0.1:{server.server_address[1]}"

    yield start
    for s in servers:
        s.shutdown()
        s.server_close()


LOCAL = {"host": "127.0.0.1", "port": 0}


# --- Config -----------------------------------------------------------------


def test_config_defaults() -> None:
    c = Config.from_env({})
    assert (c.version, c.error_rate, c.latency_ms, c.port) == ("dev", 0.0, 0, 8000)


def test_config_reads_env() -> None:
    env = {"VERSION": "v3", "ERROR_RATE": "0.5", "LATENCY_MS": "20", "PORT": "9000", "HOST": "::"}
    c = Config.from_env(env)
    assert (c.version, c.error_rate, c.latency_ms, c.port, c.host) == ("v3", 0.5, 20, 9000, "::")


@pytest.mark.parametrize(
    ("env", "message"),
    [
        ({"ERROR_RATE": "1.5"}, "ERROR_RATE"),
        ({"ERROR_RATE": "-0.1"}, "ERROR_RATE"),
        ({"LATENCY_MS": "-1"}, "LATENCY_MS"),
        ({"PORT": "70000"}, "PORT"),
    ],
)
def test_config_rejects_bad_values(env: dict[str, str], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        Config.from_env(env)


# --- HTTP endpoints -----------------------------------------------------------


def test_root_returns_version(serve: Callable[..., str]) -> None:
    base = serve(Config(version="v1", **LOCAL))
    code, ctype, body = get(base, "/")
    assert code == 200
    assert ctype == "application/json"
    assert json.loads(body) == {"version": "v1", "status": "ok"}


def test_root_fails_when_rng_is_below_error_rate(serve: Callable[..., str]) -> None:
    base = serve(Config(version="bad", error_rate=0.5, **LOCAL), rng=lambda: 0.1)
    code, _, body = get(base, "/")
    assert code == 500
    assert json.loads(body) == {"version": "bad", "status": "error"}


def test_root_succeeds_when_rng_is_above_error_rate(serve: Callable[..., str]) -> None:
    base = serve(Config(version="ok", error_rate=0.5, **LOCAL), rng=lambda: 0.9)
    assert get(base, "/")[0] == 200


def test_latency_is_applied(serve: Callable[..., str]) -> None:
    slept: list[float] = []
    base = serve(Config(latency_ms=250, **LOCAL), sleep=slept.append)
    get(base, "/")
    assert slept == [0.25]


@pytest.mark.parametrize("path", ["/healthz", "/readyz"])
def test_probes(serve: Callable[..., str], path: str) -> None:
    base = serve(Config(error_rate=1.0, **LOCAL))
    # Probes stay healthy even for a bad release: the analysis, not Kubernetes,
    # is what should catch a high error rate.
    assert get(base, path)[0] == 200


def test_unknown_path_is_404(serve: Callable[..., str]) -> None:
    assert get(serve(Config(**LOCAL)), "/nope")[0] == 404


def test_metrics_count_only_user_traffic(serve: Callable[..., str]) -> None:
    calls = iter([0.1, 0.9, 0.9, 0.9])
    base = serve(Config(version="v9", error_rate=0.5, **LOCAL), rng=lambda: next(calls))
    for _ in range(3):
        get(base, "/")
    get(base, "/healthz")
    get(base, "/?ignored=query")  # query strings still count as "/"

    code, ctype, text = get(base, "/metrics")
    assert code == 200
    assert ctype.startswith("text/plain; version=0.0.4")
    assert 'http_requests_total{code="500",version="v9"} 1' in text
    assert 'http_requests_total{code="200",version="v9"} 3' in text


# --- main() -------------------------------------------------------------------


def test_main_starts_and_stops_on_sigterm(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(os, "environ", {"VERSION": "v7", "HOST": "127.0.0.1", "PORT": "0"})
    handlers: dict[int, Callable[..., None]] = {}
    monkeypatch.setattr(signal, "signal", lambda sig, fn: handlers.setdefault(sig, fn))

    t = threading.Thread(target=app.main)
    t.start()
    # Wait for the "started" line, then deliver SIGTERM through the handler.
    for _ in range(100):
        if signal.SIGTERM in handlers:
            break
        threading.Event().wait(0.02)
    threading.Event().wait(0.1)
    handlers[signal.SIGTERM]()
    t.join(timeout=5)

    assert not t.is_alive()
    out = capsys.readouterr().out.splitlines()
    assert json.loads(out[0])["event"] == "started"
    assert json.loads(out[-1]) == {"event": "stopped", "version": "v7"}
