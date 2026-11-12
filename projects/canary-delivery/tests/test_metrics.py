from canary_demo.metrics import Metrics


def test_counters_start_at_zero_for_200_and_500() -> None:
    text = Metrics("v1").render()
    assert 'http_requests_total{code="200",version="v1"} 0' in text
    assert 'http_requests_total{code="500",version="v1"} 0' in text
    assert 'canary_demo_build_info{version="v1"} 1' in text


def test_observe_counts_codes_and_cumulative_buckets() -> None:
    m = Metrics("v2", buckets=(0.1, 0.5))
    m.observe(200, 0.05)
    m.observe(200, 0.3)
    m.observe(500, 0.9)
    m.observe(404, 0.01)
    text = m.render()

    assert 'http_requests_total{code="200",version="v2"} 2' in text
    assert 'http_requests_total{code="500",version="v2"} 1' in text
    assert 'http_requests_total{code="404",version="v2"} 1' in text
    # Buckets are cumulative: every observation <= the bound is counted.
    assert 'http_request_duration_seconds_bucket{version="v2",le="0.1"} 2' in text
    assert 'http_request_duration_seconds_bucket{version="v2",le="0.5"} 3' in text
    assert 'http_request_duration_seconds_bucket{version="v2",le="+Inf"} 4' in text
    assert 'http_request_duration_seconds_count{version="v2"} 4' in text


def test_label_values_are_escaped() -> None:
    text = Metrics('a"b\\c\nd').render()
    assert 'version="a\\"b\\\\c\\nd"' in text


def test_output_ends_with_newline_and_declares_types() -> None:
    text = Metrics("v1").render()
    assert text.endswith("\n")
    assert "# TYPE http_requests_total counter" in text
    assert "# TYPE http_request_duration_seconds histogram" in text
