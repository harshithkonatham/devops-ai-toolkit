from __future__ import annotations

import json
import socket
import struct
import threading
from collections import Counter
from collections.abc import Iterator

import pytest

from canary_demo import loadgen
from canary_demo.app import Config, build_server


@pytest.fixture
def base_url() -> Iterator[str]:
    server = build_server(Config(version="v5", host="127.0.0.1", port=0))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def test_fetch_reads_version(base_url: str) -> None:
    assert loadgen.fetch(base_url + "/") == (200, "v5")


def test_fetch_handles_http_errors(base_url: str) -> None:
    assert loadgen.fetch(base_url + "/nope") == (404, "-")


def test_fetch_handles_connection_errors() -> None:
    assert loadgen.fetch("http://127.0.0.1:9/", timeout=0.5) == (0, "-")


@pytest.fixture
def resetting_url() -> Iterator[str]:
    """A server that resets each connection mid-request, like a pod being terminated."""
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen()

    def serve() -> None:
        while True:
            try:
                conn, _ = listener.accept()
            except OSError:
                return
            conn.recv(1024)
            # SO_LINGER with a zero timeout makes close() send a TCP reset.
            conn.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
            conn.close()

    threading.Thread(target=serve, daemon=True).start()
    yield f"http://127.0.0.1:{listener.getsockname()[1]}/"
    listener.close()


def test_fetch_survives_a_connection_reset(resetting_url: str) -> None:
    # Regression: a reset used to escape fetch() and crash the load generator during rollouts.
    assert loadgen.fetch(resetting_url) == (0, "-")


def test_fetch_rejects_non_http_urls() -> None:
    with pytest.raises(ValueError, match="http"):
        loadgen.fetch("file:///etc/passwd")


def test_version_parsing_is_defensive() -> None:
    assert loadgen._version(b"not json") == "-"
    assert loadgen._version(b"[1, 2]") == "-"
    assert loadgen._version(b'{"version": 3}') == "3"


def test_sample_counts_versions() -> None:
    responses = iter([(200, "v1"), (200, "v2"), (500, "v2")])
    assert loadgen.sample("http://x/", 3, get=lambda _: next(responses)) == Counter(v1=1, v2=2)


def test_run_paces_and_reports(capsys: pytest.CaptureFixture[str]) -> None:
    now = [0.0]
    sleeps: list[float] = []

    def get(_: str) -> tuple[int, str]:
        now[0] += 0.02  # each request takes 20 ms
        return 200, "v1"

    def sleep(s: float) -> None:
        sleeps.append(s)
        now[0] += s

    totals = loadgen.run(
        "http://x/",
        rps=10,
        duration=1.0,
        get=get,
        sleep=sleep,
        clock=lambda: now[0],
        report_every=0.5,
    )

    # 10 requests in 1 s at 10 rps (11 if float rounding lets one more start).
    assert set(totals) == {"v1 200"}
    assert totals["v1 200"] in (10, 11)
    assert all(s == pytest.approx(0.08) for s in sleeps)
    reports = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert reports
    assert all(r["event"] == "traffic" for r in reports)


def test_run_rejects_bad_rps() -> None:
    with pytest.raises(ValueError, match="rps"):
        loadgen.run("http://x/", rps=0)


def test_main_sample(base_url: str, capsys: pytest.CaptureFixture[str]) -> None:
    loadgen.main(["sample", "--url", base_url + "/", "--count", "4"])
    assert json.loads(capsys.readouterr().out) == {"v5": 4}


def test_main_run(base_url: str, capsys: pytest.CaptureFixture[str]) -> None:
    loadgen.main(["run", "--url", base_url + "/", "--rps", "50", "--duration", "0.1"])
    done = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert done["event"] == "done"
    assert sum(done["totals"].values()) >= 1
