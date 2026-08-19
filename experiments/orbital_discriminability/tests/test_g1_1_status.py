"""Offline tests for the Gate G1.1 status-only boundary."""

from dataclasses import replace
from datetime import datetime, timezone
import json

import pytest

from experiments.orbital_discriminability import g1_1_status as g11


NOW = datetime(2026, 8, 19, 12, 0, 0, tzinfo=timezone.utc)


def _transmitters() -> list[dict[str, object]]:
    return [
        {
            "norad_cat_id": 7530,
            "sat_id": "AO7",
            "description": "Mode A TLM Beacon",
            "alive": True,
            "status": "active",
            "unconfirmed": False,
            "downlink_low": 29_502_000,
            "downlink_high": None,
            "mode": "CW",
            "updated": "2026-08-18T00:00:00Z",
        },
        {
            "norad_cat_id": 7530,
            "sat_id": "AO7",
            "description": "Mode A transponder",
            "alive": True,
            "status": "active",
            "unconfirmed": False,
            "downlink_low": 29_400_000,
            "downlink_high": 29_500_000,
            "mode": "USB",
            "updated": "2026-08-18T00:00:00Z",
        },
        {
            "norad_cat_id": 999,
            "sat_id": "OUT",
            "description": "UHF telemetry beacon",
            "alive": True,
            "status": "active",
            "unconfirmed": False,
            "downlink_low": 435_000_000,
            "downlink_high": None,
            "mode": "CW",
            "updated": "2026-08-18T00:00:00Z",
        },
    ]


def _omm(norad: int = 7530) -> list[dict[str, object]]:
    return [
        {
            "OBJECT_NAME": "OSCAR 7 (AO-7)",
            "NORAD_CAT_ID": norad,
            "EPOCH": "2026-08-19T10:00:00.000000",
        }
    ]


class FakeFetcher:
    def __init__(self, routes: dict[str, object]):
        self.routes = routes
        self.calls: list[str] = []

    def __call__(self, url: str, timeout_s: float, maximum_bytes: int) -> g11.HTTPResponse:
        self.calls.append(url)
        value = self.routes[url]
        if isinstance(value, Exception):
            raise value
        body = value if isinstance(value, bytes) else json.dumps(value).encode()
        return g11.HTTPResponse(200, url, body)


def _base_routes(directory: bytes) -> dict[str, object]:
    return {
        g11.TRANSMITTER_URL: _transmitters(),
        g11.CELESTRAK_TEMPLATE.format(norad=7530): _omm(),
        g11.DIRECTORY_URL: directory,
    }


def test_interactive_directory_stops_before_every_status_request() -> None:
    fetcher = FakeFetcher(
        _base_routes(
            b"<script>function play_button_click_cb(){}; x='x-kiwi-auth';</script>"
        )
    )
    result = g11.run_status_only(
        g11.G11StatusPlan(),
        fetcher=fetcher,
        evaluated_at=NOW,
    )

    assert result.outcome == g11.G11Outcome.CAPABILITY_DISCOVERY_UNAVAILABLE.value
    assert result.directory_interaction_required
    assert result.status_request_count == 0
    assert all(not url.endswith("/status") for url in fetcher.calls)
    assert all("/snd" not in url.lower() and "/wf" not in url.lower() for url in fetcher.calls)
    assert result.fetch_receipts[-1].state == g11.FetchState.INTERACTION_REQUIRED.value
    assert result.raw_rf_activity == "ZERO"


def test_direct_status_descriptions_do_not_invent_g1_fields() -> None:
    directory = b"http://alpha.invalid:8073 http://beta.invalid:8074"
    routes = _base_routes(directory)
    routes.update(
        {
            "http://alpha.invalid:8073/status": b"name=alpha gps=(52.1,13.2) bands=0-30MHz gps_good=1 ext_api=2",
            "http://beta.invalid:8074/status": b"name=beta gps=(51.4,5.4) bands=0-30MHz gps_good=1 ext_api=2",
        }
    )
    fetcher = FakeFetcher(routes)
    result = g11.run_status_only(
        g11.G11StatusPlan(),
        fetcher=fetcher,
        evaluated_at=NOW,
    )

    assert result.outcome == g11.G11Outcome.NO_CAPABILITY_ADMITTED.value
    assert result.endpoint_candidate_count == 2
    assert result.status_request_count == 2
    assert all(
        item.state == g11.DescriptionState.DESCRIPTION_INSUFFICIENT.value
        for item in result.status_assessments
    )
    assert all("sample_event_time_semantics_and_error" in item.missing_g1_fields for item in result.status_assessments)
    assert all(item.coordinates is not None for item in result.status_assessments)
    assert all(item.status_sha256 is not None for item in result.status_assessments)


def test_one_status_error_makes_qualification_incomplete_not_rejected() -> None:
    directory = b"http://alpha.invalid:8073 http://beta.invalid:8074"
    routes = _base_routes(directory)
    routes.update(
        {
            "http://alpha.invalid:8073/status": b"name=alpha gps=(52.1,13.2)",
            "http://beta.invalid:8074/status": TimeoutError("timed out"),
        }
    )
    result = g11.run_status_only(
        g11.G11StatusPlan(),
        fetcher=FakeFetcher(routes),
        evaluated_at=NOW,
    )

    assert result.outcome == g11.G11Outcome.CAPABILITY_QUALIFICATION_INCOMPLETE.value
    beta = next(
        item for item in result.status_assessments if item.endpoint == "http://beta.invalid:8074"
    )
    assert beta.state == g11.DescriptionState.QUALIFICATION_ERROR.value
    assert "no Internet RF capability exists" in result.unauthorized_claims


def test_transmitter_filter_is_bounded_exact_carrier_and_deterministic() -> None:
    plan = g11.G11StatusPlan()
    items = _transmitters() + [
        {
            **_transmitters()[0],
            "description": "newer telemetry beacon",
            "downlink_low": 29_501_000,
            "updated": "2026-08-19T00:00:00Z",
        }
    ]
    selected = g11.select_transmitter_candidates(items, plan)
    reversed_selected = g11.select_transmitter_candidates(tuple(reversed(items)), plan)

    assert selected == reversed_selected
    assert len(selected) == 1
    assert selected[0].norad_cat_id == 7530
    assert selected[0].carrier_hz == 29_501_000


def test_model_failure_does_not_cross_into_capability_absence() -> None:
    fetcher = FakeFetcher({g11.TRANSMITTER_URL: TimeoutError("offline")})
    result = g11.run_status_only(
        g11.G11StatusPlan(),
        fetcher=fetcher,
        evaluated_at=NOW,
    )

    assert result.outcome == g11.G11Outcome.MODEL_METADATA_UNAVAILABLE.value
    assert result.endpoint_candidate_count == 0
    assert result.status_request_count == 0


def test_valid_empty_directory_is_not_a_transport_failure() -> None:
    result = g11.run_status_only(
        g11.G11StatusPlan(),
        fetcher=FakeFetcher(_base_routes(b"<html>no endpoints</html>")),
        evaluated_at=NOW,
    )

    assert result.outcome == g11.G11Outcome.NO_CAPABILITY_DISCOVERED.value
    assert result.fetch_receipts[-1].state == g11.FetchState.SUCCESS.value


def test_receipt_is_strict_hash_bound_and_contains_no_response_body() -> None:
    result = g11.run_status_only(
        g11.G11StatusPlan(),
        fetcher=FakeFetcher(_base_routes(b"<html>no endpoints</html>")),
        evaluated_at=NOW,
    )
    encoded = result.strict_json()

    assert len(result.plan_hash) == 64
    assert all(
        receipt.body_sha256 is None or len(receipt.body_sha256) == 64
        for receipt in result.fetch_receipts
    )
    assert "OBJECT_NAME" not in encoded
    assert "NaN" not in encoded and "Infinity" not in encoded


def test_response_over_byte_limit_is_a_descriptive_failure() -> None:
    class OversizeFetcher:
        def __call__(self, url: str, timeout_s: float, maximum_bytes: int) -> g11.HTTPResponse:
            return g11.HTTPResponse(200, url, b"x" * (maximum_bytes + 1))

    result = g11.run_status_only(
        g11.G11StatusPlan(),
        fetcher=OversizeFetcher(),
        evaluated_at=NOW,
    )

    assert result.outcome == g11.G11Outcome.MODEL_METADATA_UNAVAILABLE.value
    assert result.fetch_receipts[0].state == g11.FetchState.DESCRIPTION_ERROR.value


@pytest.mark.parametrize(
    "mutation",
    (
        {"directory_url": "http://different.invalid"},
        {"retry_count": 1},
        {"maximum_model_candidates": 6},
        {"maximum_directory_endpoints": 21},
    ),
)
def test_plan_refuses_surface_expansion(mutation: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        replace(g11.G11StatusPlan(), **mutation).validate()
