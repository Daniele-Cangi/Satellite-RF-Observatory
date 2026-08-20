"""Offline guard tests for the bounded DSS-45 header spike."""

from pathlib import Path

import pytest

from experiments.orbital_discriminability.maven_dss45_header_spike import (
    HEADER_INDICES,
    HeaderSpikeError,
    fetch_header,
)
from experiments.orbital_discriminability.maven_rsr_header import (
    parser_manifest_sha256,
)


def test_header_plan_is_bounded_and_science_interval_only() -> None:
    assert len(HEADER_INDICES) == 75
    assert HEADER_INDICES[0] == 0
    assert HEADER_INDICES[-1] == 736
    assert all(right > left for left, right in zip(HEADER_INDICES, HEADER_INDICES[1:]))


def test_unplanned_header_index_is_refused_before_network(monkeypatch) -> None:
    called = False

    def forbidden(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("network must not be reached")

    monkeypatch.setattr("urllib.request.urlopen", forbidden)
    with pytest.raises(HeaderSpikeError, match="outside the frozen"):
        fetch_header(1)
    assert not called


def test_non_range_response_is_refused_before_body_read(monkeypatch) -> None:
    class Response:
        headers = {"Content-Length": "4600800"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def getcode(self):
            return 200

        def read(self, *args):
            raise AssertionError("body must not be read")

    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: Response())
    with pytest.raises(HeaderSpikeError, match="exact authorized header range"):
        fetch_header(0)


def test_sources_and_result_do_not_name_sealed_products() -> None:
    directory = Path(__file__).parents[1]
    texts = [
        (directory / "maven_rsr_header.py").read_text(encoding="utf-8"),
        (directory / "maven_dss45_header_spike.py").read_text(encoding="utf-8"),
        (directory / "MAVEN_DSS45_METADATA_RESULT.json").read_text(encoding="utf-8"),
    ]
    joined = "\n".join(texts).lower()
    for sealed_marker in (
        "20160226t200001",
        "20160705t213501",
        "dss-35",
        "dss-55",
        "dss35",
        "dss55",
    ):
        assert sealed_marker not in joined


def test_persisted_result_has_zero_sample_access_and_strict_manifest() -> None:
    import json

    result_path = (
        Path(__file__).parents[1] / "MAVEN_DSS45_METADATA_RESULT.json"
    )
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["header_access"]["sample_chdo_bytes_read"] == 0
    assert result["header_access"]["raw_headers_retained"] == 0
    assert result["header_access"]["request_count"] == 75
    assert result["parser_manifest_sha256"] == parser_manifest_sha256()
    assert result["claim_scope"] == "DEVELOPMENT_ONLY_FOR_TWO_WAY_RSR_COMPILER"
    assert not result["spk_independence"]["independent_orbital_prediction_authorized"]
