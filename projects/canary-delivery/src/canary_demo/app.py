"""A tiny HTTP service whose failure rate and latency are set by config.

That makes it easy to ship a "good" and a "bad" release and watch the canary
analysis promote one and roll back the other.

Endpoints:
    GET /         {"version": ..., "status": "ok"}, or HTTP 500 at ERROR_RATE
    GET /healthz  liveness
    GET /readyz   readiness
    GET /metrics  Prometheus metrics
"""

from __future__ import annotations

import json
import os
import random
import signal
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit

from canary_demo.metrics import Metrics

JSON = "application/json"
PROMETHEUS = "text/plain; version=0.0.4; charset=utf-8"


@dataclass(frozen=True)
class Config:
    version: str = "dev"
    error_rate: float = 0.0
    latency_ms: int = 0
    # Listen on all interfaces: the app runs in a container behind a Service.
    host: str = "0.0.0.0"  # noqa: S104  # nosec B104
    port: int = 8000

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> Config:
        """Read config from environment variables and reject bad values at startup."""
        error_rate = float(env.get("ERROR_RATE", "0"))
        if not 0.0 <= error_rate <= 1.0:
            raise ValueError(f"ERROR_RATE must be between 0 and 1, got {error_rate}")
        latency_ms = int(env.get("LATENCY_MS", "0"))
        if latency_ms < 0:
            raise ValueError(f"LATENCY_MS must be >= 0, got {latency_ms}")
        port = int(env.get("PORT", "8000"))
        if not 0 <= port <= 65535:
            raise ValueError(f"PORT must be between 0 and 65535, got {port}")
        return cls(
            version=env.get("VERSION", "dev"),
            error_rate=error_rate,
            latency_ms=latency_ms,
            host=env.get("HOST", cls.host),
            port=port,
        )


def make_handler(
    config: Config,
    metrics: Metrics,
    rng: Callable[[], float] = random.random,
    sleep: Callable[[float], None] = time.sleep,
) -> type[BaseHTTPRequestHandler]:
    """Build a request handler class. rng and sleep can be swapped out in tests."""

    class Handler(BaseHTTPRequestHandler):
        server_version = "canary-demo"
        sys_version = ""

        def do_GET(self) -> None:
            path = urlsplit(self.path).path
            if path == "/":
                self._serve_root()
            elif path in ("/healthz", "/readyz"):
                self._send(200, b'{"status": "ok"}', JSON)
            elif path == "/metrics":
                self._send(200, metrics.render().encode(), PROMETHEUS)
            else:
                self._send(404, b'{"error": "not found"}', JSON)

        def _serve_root(self) -> None:
            start = time.perf_counter()
            if config.latency_ms:
                sleep(config.latency_ms / 1000)
            failed = rng() < config.error_rate
            code = 500 if failed else 200
            body = {"version": config.version, "status": "error" if failed else "ok"}
            self._send(code, json.dumps(body).encode(), JSON)
            metrics.observe(code, time.perf_counter() - start)

        def _send(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            """Skip per-request access logs. Metrics cover request activity."""

    return Handler


def build_server(config: Config, **handler_kwargs: Any) -> ThreadingHTTPServer:
    metrics = Metrics(config.version)
    handler = make_handler(config, metrics, **handler_kwargs)
    server = ThreadingHTTPServer((config.host, config.port), handler)
    server.daemon_threads = True
    return server


def main() -> None:
    config = Config.from_env(os.environ)
    server = build_server(config)

    # Kubernetes sends SIGTERM before killing the pod. shutdown() blocks until
    # serve_forever() returns, so it must run on another thread.
    def stop(*_: object) -> None:
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    print(json.dumps({"event": "started", **vars(config)}), flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        print(json.dumps({"event": "stopped", "version": config.version}), flush=True)
