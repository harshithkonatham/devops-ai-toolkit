"""Prometheus metrics in the text exposition format.

Written by hand so the service has no runtime dependencies. It only needs one
counter and one histogram.
"""

from __future__ import annotations

import threading
from collections.abc import Sequence

DEFAULT_BUCKETS: tuple[float, ...] = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5)


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _fmt(bound: float) -> str:
    return f"{bound:g}"


class Metrics:
    """Request count by status code, and request duration, for one app version."""

    def __init__(self, version: str, buckets: Sequence[float] = DEFAULT_BUCKETS) -> None:
        self._version = _escape(version)
        self._buckets = tuple(sorted(buckets))
        self._lock = threading.Lock()
        # Both codes start at zero, so error-rate queries have a series to work
        # with from the first scrape, before any error has happened.
        self._requests: dict[int, int] = {200: 0, 500: 0}
        self._bucket_counts = [0] * len(self._buckets)
        self._sum = 0.0
        self._count = 0

    def observe(self, code: int, seconds: float) -> None:
        with self._lock:
            self._requests[code] = self._requests.get(code, 0) + 1
            for i, bound in enumerate(self._buckets):
                if seconds <= bound:
                    self._bucket_counts[i] += 1
            self._sum += seconds
            self._count += 1

    def render(self) -> str:
        v = self._version
        with self._lock:
            lines = [
                "# HELP canary_demo_build_info Version of the running app.",
                "# TYPE canary_demo_build_info gauge",
                f'canary_demo_build_info{{version="{v}"}} 1',
                "# HELP http_requests_total Requests to / by HTTP status code.",
                "# TYPE http_requests_total counter",
            ]
            lines += [
                f'http_requests_total{{code="{code}",version="{v}"}} {n}'
                for code, n in sorted(self._requests.items())
            ]
            lines += [
                "# HELP http_request_duration_seconds Time to serve requests to /.",
                "# TYPE http_request_duration_seconds histogram",
            ]
            lines += [
                f'http_request_duration_seconds_bucket{{version="{v}",le="{_fmt(b)}"}} {n}'
                for b, n in zip(self._buckets, self._bucket_counts, strict=True)
            ]
            lines += [
                f'http_request_duration_seconds_bucket{{version="{v}",le="+Inf"}} {self._count}',
                f'http_request_duration_seconds_sum{{version="{v}"}} {self._sum}',
                f'http_request_duration_seconds_count{{version="{v}"}} {self._count}',
            ]
        return "\n".join(lines) + "\n"
