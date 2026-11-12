"""Load generator and traffic sampler for the canary demo.

python -m canary_demo.loadgen run --url http://canary-demo/ --rps 20
    Sends steady traffic, so the canary analysis has data to judge.

python -m canary_demo.loadgen sample --url http://canary-demo/ --count 50
    Sends N requests and prints how many each version served, as JSON.
    CI uses this to check that users are only reaching the stable version.
"""

from __future__ import annotations

import argparse
import http.client
import json
import time
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Callable, Sequence
from urllib.parse import urlsplit

Fetch = Callable[[str], tuple[int, str]]


def fetch(url: str, timeout: float = 2.0) -> tuple[int, str]:
    """GET url and return (status code, version). Version is "-" if unknown."""
    if urlsplit(url).scheme not in ("http", "https"):
        raise ValueError(f"only http(s) URLs are allowed, got {url!r}")
    try:
        # The scheme is checked above, so file:// and custom schemes are refused.
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310  # nosec B310
            return resp.status, _version(resp.read())
    except urllib.error.HTTPError as err:
        return err.code, _version(err.read())
    except (urllib.error.URLError, ConnectionError, TimeoutError, http.client.HTTPException):
        # Pods are terminated mid-request during a rollout (connection reset, closed early).
        # Count that as a failed request instead of crashing the load generator.
        return 0, "-"


def _version(body: bytes) -> str:
    try:
        value = json.loads(body).get("version", "-")
    except (ValueError, AttributeError):
        return "-"
    return str(value)


def sample(url: str, count: int, get: Fetch = fetch) -> Counter[str]:
    """Count which version served each of `count` requests."""
    return Counter(get(url)[1] for _ in range(count))


def run(
    url: str,
    rps: float,
    duration: float | None = None,
    get: Fetch = fetch,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    report_every: float = 10.0,
) -> Counter[str]:
    """Send about `rps` requests per second, forever or for `duration` seconds.

    Prints a JSON summary every `report_every` seconds and returns the totals,
    keyed by "<version> <status code>".
    """
    if rps <= 0:
        raise ValueError("rps must be > 0")
    interval = 1.0 / rps
    totals: Counter[str] = Counter()
    window: Counter[str] = Counter()
    start = last_report = clock()
    while duration is None or clock() - start < duration:
        tick = clock()
        code, version = get(url)
        totals[f"{version} {code}"] += 1
        window[f"{version} {code}"] += 1
        if clock() - last_report >= report_every:
            print(json.dumps({"event": "traffic", "last_window": dict(window)}), flush=True)
            window.clear()
            last_report = clock()
        sleep(max(0.0, interval - (clock() - tick)))
    return totals


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="canary_demo.loadgen")
    sub = parser.add_subparsers(dest="command", required=True)
    p_run = sub.add_parser("run", help="send steady traffic")
    p_run.add_argument("--url", required=True)
    p_run.add_argument("--rps", type=float, default=20.0)
    p_run.add_argument("--duration", type=float, default=None, help="seconds; default forever")
    p_sample = sub.add_parser("sample", help="count which versions serve traffic")
    p_sample.add_argument("--url", required=True)
    p_sample.add_argument("--count", type=int, default=50)
    args = parser.parse_args(argv)

    if args.command == "run":
        totals = run(args.url, args.rps, args.duration)
        print(json.dumps({"event": "done", "totals": dict(totals)}), flush=True)
    else:
        print(json.dumps(dict(sample(args.url, args.count))), flush=True)


if __name__ == "__main__":
    main()
