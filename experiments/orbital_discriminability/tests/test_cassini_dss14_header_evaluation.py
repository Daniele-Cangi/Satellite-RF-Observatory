"""Offline boundary tests for the DSS-14 header-only evaluation."""

from io import BytesIO
import json
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability.cassini_dss14_header_evaluation import (
    CassiniDss14EvaluationError,
    RSR_HEADER_BYTES,
    _difference_metrics,
    _fit_affine,
    _parse_multipart_ranges,
    _read_exact_range_response,
    evaluation_manifest,
    evaluation_manifest_sha256,
)


class _Response:
    def __init__(self, status: int, headers: dict[str, str], body: bytes) -> None:
        self._status = status
        self.headers = headers
        self._body = BytesIO(body)
        self.read_called = False

    def getcode(self) -> int:
        return self._status

    def read(self, size: int = -1) -> bytes:
        self.read_called = True
        return self._body.read(size)


def test_non_range_response_is_rejected_before_body_read() -> None:
    response = _Response(200, {"Content-Length": "18658800"}, b"not read")
    with pytest.raises(CassiniDss14EvaluationError, match="BODY_NOT_READ"):
        _read_exact_range_response(response, ((0, 259),), 18_658_800)
    assert response.read_called is False


def test_exact_single_header_range_is_admitted() -> None:
    body = bytes([7]) * RSR_HEADER_BYTES
    response = _Response(206, {
        "Content-Length": str(RSR_HEADER_BYTES),
        "Content-Range": "bytes 0-259/18658800",
        "Content-Type": "application/octet-stream",
    }, body)
    assert _read_exact_range_response(response, ((0, 259),), 18_658_800) == {(0, 259): body}


def test_exact_multipart_headers_are_admitted_and_extra_range_is_rejected() -> None:
    boundary = "bounded"
    ranges = ((0, 259), (4260, 4519))
    body = b"".join(
        (f"--{boundary}\r\nContent-Type: application/octet-stream\r\n"
         f"Content-Range: bytes {start}-{end}/18658800\r\n\r\n").encode("ascii")
        + bytes([index + 1]) * RSR_HEADER_BYTES + b"\r\n"
        for index, (start, end) in enumerate(ranges)
    ) + f"--{boundary}--\r\n".encode("ascii")
    response = _Response(206, {
        "Content-Type": f"multipart/byteranges; boundary={boundary}",
        "Content-Length": str(len(body)),
    }, body)
    result = _read_exact_range_response(response, ranges, 18_658_800)
    assert set(result) == set(ranges)
    assert all(len(value) == RSR_HEADER_BYTES for value in result.values())
    with pytest.raises(CassiniDss14EvaluationError, match="outside"):
        _parse_multipart_ranges(body, boundary, (ranges[0],), 18_658_800)

    chunked = _Response(206, {
        "Content-Type": f"multipart/byteranges; boundary={boundary}",
    }, body)
    assert set(_read_exact_range_response(chunked, ranges, 18_658_800)) == set(ranges)


def test_affine_null_uses_prefix_only_and_preserves_suffix_curvature() -> None:
    x = np.arange(10, dtype=np.float64)
    orbital = 3.0 + 0.2 * x + 0.01 * x * x
    offset, slope = _fit_affine(x[:2], orbital[:2])
    metrics = _difference_metrics(orbital, offset + slope * x, slice(2, 10))
    assert metrics["peak_to_peak_hz"] > 0.0
    assert metrics["rms_hz"] > 0.0


def test_manifest_freezes_no_iq_and_the_controlling_null() -> None:
    manifest = evaluation_manifest()
    assert manifest["controlling_null"] == "CALIBRATION_PREFIX_AFFINE_RECORDED_BASEBAND"
    assert "complete RSR materialization" in manifest["forbidden"]
    assert len(evaluation_manifest_sha256()) == 64


def test_frozen_receipt_is_strict_and_cannot_authorize_payload_access() -> None:
    path = Path(__file__).parents[1] / "CASSINI_DSS14_HEADER_EVALUATION_RECEIPT.json"
    receipt = json.loads(path.read_text(encoding="utf-8"), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    assert receipt["outcome"] == "CASSINI_DSS14_REAL_NCO_SIGNATURE_RANKED"
    assert receipt["access_boundary"]["data_chdo_bytes_read"] == 0
    assert receipt["access_boundary"]["raw_headers_persisted"] is False
    assert receipt["authority"]["evaluation_manifest_sha256"] == evaluation_manifest_sha256()
    assert receipt["claim_scope"]["iq_access_authorized"] is False
    assert receipt["claim_scope"]["physical_margin_admitted"] is False
