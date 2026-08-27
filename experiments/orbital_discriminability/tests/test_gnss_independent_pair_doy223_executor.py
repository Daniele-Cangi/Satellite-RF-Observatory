from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import Mapping
from urllib.request import Request

import numpy as np
import pytest

from experiments.orbital_discriminability import (
    gnss_independent_pair_doy223_executor as executor,
)
from experiments.orbital_discriminability import (
    gnss_independent_pair_doy223_primary_plan as frozen,
)
from experiments.orbital_discriminability import (
    gnss_phase_short_window_primary as primary,
)


ROOT = Path(__file__).resolve().parents[1]
EXECUTOR_SEAL = ROOT / executor.EXECUTOR_SEAL_NAME
EXECUTOR_SEAL_SHA256 = (
    "130378385487a337e82aa215c083c5b97099162c5361bdf6f9651ce4f84f45b5"
)


def header_line(data: str, label: str) -> str:
    return f"{data:<60}{label:<20}\n"


def field(value: float | None, lli: int = 0) -> str:
    if value is None:
        return " " * 16
    return f"{value:14.3f}{' ' if lli == 0 else lli} "


def synthetic_expected(product: executor.ProductPlan) -> dict[str, object]:
    config = executor.qualified.EXPECTED_CONFIGURATION[product.station]
    return {
        "receiver": {
            "serial": config["receiver_serial"],
            "type": config["receiver_type"],
            "version_or_radome": config["receiver_version"],
        },
        "antenna": {
            "serial": config["antenna_serial"],
            "type": config["antenna_type"],
            "version_or_radome": "",
        },
        "scale_factor_records": [],
        "phase_shift_records": [],
        "applied_bias_records": [],
        "receiver_clock_offset_applied": 0,
    }


def fixture(
    product: executor.ProductPlan,
    *,
    nonzero_lli: tuple[int, str, str] | None = None,
) -> bytearray:
    observables = ("C1C", "L1C", "S1C", "C2W", "L2W", "S2W")
    expected = synthetic_expected(product)
    receiver = expected["receiver"]
    antenna = expected["antenna"]
    lines = [
        header_line(
            "     3.04           OBSERVATION DATA    G",
            "RINEX VERSION / TYPE",
        ),
        header_line(product.station[:4], "MARKER NAME"),
        header_line(
            f"{receiver['serial']:<20}{receiver['type']:<20}"
            f"{receiver['version_or_radome']:<20}",
            "REC # / TYPE / VERS",
        ),
        header_line(
            f"{antenna['serial']:<20}{antenna['type']:<20}",
            "ANT # / TYPE",
        ),
        header_line(
            " -2350000.0 -4650000.0 3670000.0",
            "APPROX POSITION XYZ",
        ),
        header_line(
            f"G  {len(observables):3d} "
            + "".join(f"{item:>3} " for item in observables),
            "SYS / # / OBS TYPES",
        ),
        header_line("      30.000", "INTERVAL"),
        header_line(
            "  2026     8    11     0     0    0.0000000     GPS",
            "TIME OF FIRST OBS",
        ),
        header_line(
            "  2026     8    11    23    59   30.0000000     GPS",
            "TIME OF LAST OBS",
        ),
        header_line("", "END OF HEADER"),
    ]
    station_bias = 200.0 if product.station == "MDO100USA" else 0.0
    for epoch_index, epoch in enumerate(executor.expected_raw_gps_epochs()):
        lines.append(
            f"> {epoch.year:4d} {epoch.month:02d} {epoch.day:02d} "
            f"{epoch.hour:02d} {epoch.minute:02d} "
            f"{epoch.second:10.7f}  0  2\n"
        )
        for satellite_index, satellite in enumerate(executor.SATELLITES):
            values: dict[str, tuple[float | None, int]] = {
                "C1C": (22_000_000.0 + epoch_index + satellite_index, 0),
                "L1C": (
                    115_000_000.0
                    + station_bias
                    + epoch_index * 0.020
                    + satellite_index,
                    0,
                ),
                "S1C": (45.0, 0),
                "C2W": (22_000_010.0 + epoch_index + satellite_index, 0),
                "L2W": (
                    89_000_000.0
                    + station_bias
                    + epoch_index * 0.015
                    + satellite_index,
                    0,
                ),
                "S2W": (43.0, 0),
            }
            if nonzero_lli and nonzero_lli[:2] == (epoch_index, satellite):
                value, _ = values[nonzero_lli[2]]
                values[nonzero_lli[2]] = (value, 1)
            lines.append(
                satellite
                + "".join(field(*values[item]) for item in observables)
                + "\n"
            )
    return bytearray("".join(lines).encode("ascii"))


def synthetic_curves(second_best_margin_m: float) -> dict[str, np.ndarray]:
    prefix = np.zeros(frozen.CALIBRATION_EPOCHS, dtype=np.float64)

    def tail(scale: float) -> np.ndarray:
        return np.concatenate(
            (
                prefix,
                np.linspace(
                    0.0,
                    scale,
                    frozen.HELDOUT_EPOCHS,
                    dtype=np.float64,
                ),
            )
        )

    return {
        "ORBITAL_G22": tail(0.0),
        "PREFIX_AFFINE": tail(second_best_margin_m),
        "WRONG_ORBIT_G01": tail(10_000.0),
        "WRONG_ORBIT_G14": tail(20_000.0),
        "WRONG_ORBIT_G17": tail(30_000.0),
    }


class FakeResponse:
    def __init__(
        self,
        payload: bytes,
        *,
        status: int = 200,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.status = status
        self.headers = dict(headers or {})
        self._payload = payload
        self._read = False

    def read(self, _size: int = -1) -> bytes:
        if self._read:
            return b""
        self._read = True
        return self._payload

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_manifest_is_exact_and_grants_no_live_authority() -> None:
    manifest = executor.executor_manifest()
    encoded = executor.strict_json(manifest)

    assert [row["station"] for row in manifest["products"]] == [
        "ALGO00CAN",
        "MDO100USA",
    ]
    assert all("2026223" in row["name"] for row in manifest["products"])
    assert all(len(row["mirrors"]) == 2 for row in manifest["products"])
    assert executor.AUTHORITY_TOKEN not in encoded
    assert not any(manifest["access"].values())
    assert manifest["transport"]["max_attempts_per_mirror"] == 2
    assert manifest["transport"]["max_total_attempts_per_product"] == 4
    assert manifest["transport"]["complete_hashes_before_first_decode"] == 2
    assert manifest["transport"]["cross_mirror_partial_append"] is False


def test_frozen_inputs_bind_exact_curves_and_qualified_transforms() -> None:
    curves, qualified_headers = executor.validate_frozen_inputs(ROOT)
    try:
        assert set(curves) == set(executor.HYPOTHESES)
        assert all(curve.shape == (137,) for curve in curves.values())
        assert list(qualified_headers) == ["ALGO00CAN", "MDO100USA"]
    finally:
        for curve in curves.values():
            curve.fill(0.0)


def test_executor_seal_binds_post_commit_source_and_zero_access() -> None:
    assert executor.canonical_sha256(EXECUTOR_SEAL) == EXECUTOR_SEAL_SHA256
    seal = json.loads(EXECUTOR_SEAL.read_text(encoding="utf-8"))

    assert seal["state"] == "PRIMARY_EXECUTOR_FROZEN_OBSERVATION_UNOPENED"
    assert seal["source_commit"] == (
        "af293090436468b43737677bd0b0a12dfb84ee0a"
    )
    assert seal["source_sha256"] == (
        "4b7d032c414419c11844a974f97aa9239293557ffc704fa22c03f4525336bc08"
    )
    assert seal["manifest_sha256"] == (
        "6748fb3acd8eb65cd868d205420a00841006861f14e904a6bcbeb5318cf3bb87"
    )
    assert seal["qualified_header_transform_sha256"] == (
        "7f106a5486ddd05cad12e034b4b7a14c87fc97ad77e77f73f660755c344d09bf"
    )
    assert seal["authority"]["live_execution_authorized_by_seal"] is False
    assert not any(seal["access_at_seal"].values())
    _, curves, _ = executor.validate_executor_seal(
        ROOT,
        EXECUTOR_SEAL,
        EXECUTOR_SEAL_SHA256,
    )
    for curve in curves.values():
        curve.fill(0.0)


def test_separately_authorized_primary_outcome_is_frozen_and_value_free() -> None:
    raw = (ROOT / executor.OUTCOME_NAME).read_bytes()
    outcome = json.loads(
        raw,
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )

    assert len(raw) == 1_668
    assert sha256(raw).hexdigest() == (
        "2f8e7f0f4261e32c159d312995f69899f591696f0b0ea6141c40706ce6d9153b"
    )
    assert outcome["outcome"] == "MEASUREMENT_INVALID"
    assert outcome["reason"] == "HATANAKA_DECODE_FAILED:ALGO00CAN"
    assert outcome["heldout_comparison"] == "NOT_EVALUATED"
    assert outcome["observation_values_persisted"] == 0
    assert len(outcome["artifacts"]) == 2
    assert all(
        artifact["hash_before_any_decode"] is True
        for artifact in outcome["artifacts"]
    )


def test_same_mirror_resume_requires_and_uses_stable_validator() -> None:
    product = executor.ProductPlan("TEST", "product.gz", ("https://one",))
    requests = []
    responses = iter(
        (
            FakeResponse(
                b"abc",
                headers={"ETag": '"v1"', "Content-Length": "6"},
            ),
            FakeResponse(
                b"def",
                status=206,
                headers={
                    "ETag": '"v1"',
                    "Content-Length": "3",
                    "Content-Range": "bytes 3-5/6",
                },
            ),
        )
    )

    def opener(request, _timeout):
        requests.append(dict(request.header_items()))
        return next(responses)

    payload, receipt = executor.materialize_bounded(product, opener=opener)

    assert bytes(payload) == b"abcdef"
    assert receipt["resume_used"] is True
    assert receipt["attempts_total"] == 2
    assert receipt["complete_file_sha256"] == sha256(b"abcdef").hexdigest()
    assert requests[1]["Range"] == "bytes=3-"
    assert requests[1]["If-range"] == '"v1"'


def test_default_opener_separates_connect_and_idle_timeouts(monkeypatch) -> None:
    applied: list[float] = []
    socket_value = SimpleNamespace(settimeout=applied.append)
    response = SimpleNamespace(
        fp=SimpleNamespace(raw=SimpleNamespace(_sock=socket_value))
    )
    seen: list[float] = []

    def fake_urlopen(_request, timeout):
        seen.append(timeout)
        return response

    monkeypatch.setattr(executor, "urlopen", fake_urlopen)

    assert executor._open(Request("https://example.invalid"), 30.0) is response
    assert seen == [executor.CONNECT_TIMEOUT_S]
    assert applied == [executor.IDLE_TIMEOUT_S]


def test_mirror_change_discards_partial_bytes() -> None:
    product = executor.ProductPlan(
        "TEST",
        "product.gz",
        ("https://one", "https://two"),
    )
    first_attempts = 0

    def opener(request, _timeout):
        nonlocal first_attempts
        if request.full_url == "https://one":
            first_attempts += 1
            return FakeResponse(b"old", headers={"Content-Length": "6"})
        return FakeResponse(b"new", headers={"Content-Length": "3"})

    payload, receipt = executor.materialize_bounded(product, opener=opener)

    assert first_attempts == 2
    assert bytes(payload) == b"new"
    assert receipt["mirror_index"] == 1
    assert receipt["attempts_total"] == 3
    assert receipt["cross_mirror_partial_append"] is False


def test_parser_and_coordinate_use_only_doy223_grid() -> None:
    scans = [
        executor.scan_decoded(
            fixture(product),
            product,
            synthetic_expected(product),
        )
        for product in executor.PRODUCTS
    ]
    try:
        coordinate, admission = executor.measurement_coordinate(scans)
        coordinate.fill(0.0)
    finally:
        for scan in scans:
            scan.erase()

    assert executor.expected_raw_gps_epochs()[0] == frozen.RAW_START
    assert admission["core_phase_and_lli"] == "SATISFIED"
    assert admission["same_path_code_witness"]["state"] == "SATISFIED"
    assert admission["geometry_free_phase_health"]["state"] == "SATISFIED"
    assert admission["feature_epochs"] == 137


def test_nonzero_lli_is_measurement_invalid() -> None:
    product = executor.PRODUCTS[0]

    with pytest.raises(
        primary.PrimaryMeasurementInvalid,
        match="NONZERO_OR_INVALID_LLI",
    ):
        executor.scan_decoded(
            fixture(product, nonzero_lli=(77, "G22", "L1C")),
            product,
            synthetic_expected(product),
        )


def test_scoring_uses_frozen_doy223_pairwise_guard() -> None:
    observed = np.zeros(frozen.FEATURE_EPOCHS, dtype=np.float64)
    below = executor.score_coordinate(
        observed,
        synthetic_curves(frozen.SCREEN_PAIRWISE_GUARD_M),
    )
    above = executor.score_coordinate(
        observed,
        synthetic_curves(frozen.SCREEN_PAIRWISE_GUARD_M + 1.0),
    )

    assert below["outcome"] == "AMBIGUOUS"
    assert above["outcome"] == "ORBITAL_MODEL_PREDICTIVELY_PREFERRED"
    assert above["heldout_comparison"]["preference_guard_m"] == pytest.approx(
        3_142.1641485601226
    )
    assert above["calibration_admission"]["limit_m"] == pytest.approx(
        1_571.0820742800613
    )


def test_authority_refuses_before_seal_or_materializer() -> None:
    called = False

    def forbidden(_product: executor.ProductPlan):
        nonlocal called
        called = True
        raise AssertionError("network reached")

    with TemporaryDirectory(dir=ROOT) as directory:
        output = Path(directory)
        with pytest.raises(
            PermissionError,
            match="ALGO_MDO_DOY223_PRIMARY_AUTHORITY_REQUIRED",
        ):
            executor.run_once(
                output,
                "",
                "0" * 64,
                output / "missing.json",
                materializer=forbidden,
            )
    assert called is False


def test_both_complete_hashes_precede_decode_and_buffers_are_erased(
    monkeypatch,
) -> None:
    curves = synthetic_curves(frozen.SCREEN_PAIRWISE_GUARD_M + 1.0)
    expected_headers = {
        product.station: synthetic_expected(product)
        for product in executor.PRODUCTS
    }
    seal = {"source_commit": "frozen", "source_sha256": "a" * 64}
    events: list[str] = []
    compressed: list[bytearray] = []
    decoded: list[bytearray] = []
    scans: list[primary.StationMeasurement] = []
    coordinates: list[np.ndarray] = []

    def validate(*_args):
        return seal, curves, expected_headers

    def materialize(product: executor.ProductPlan):
        events.append(f"hash:{product.station}")
        payload = bytearray(product.station.encode("ascii"))
        compressed.append(payload)
        return payload, {
            "station": product.station,
            "attempts_total": 1,
            "complete_file_bytes": len(payload),
            "complete_file_sha256": sha256(payload).hexdigest(),
        }

    def decode(_payload: bytearray, station: str):
        assert events[:2] == ["hash:ALGO00CAN", "hash:MDO100USA"]
        events.append(f"decode:{station}")
        payload = bytearray(f"decoded:{station}".encode("ascii"))
        decoded.append(payload)
        return payload

    def scan(
        _payload: bytearray,
        product: executor.ProductPlan,
        _expected: object,
    ):
        measurement = primary.StationMeasurement(
            station=product.station,
            header={"station": product.station, "synthetic": True},
            phase_cycles=np.ones((frozen.RAW_EPOCHS, 2, 2)),
            core_valid=np.ones((frozen.RAW_EPOCHS, 2), dtype=np.bool_),
            code_present=np.ones((frozen.RAW_EPOCHS, 2, 2), dtype=np.bool_),
            structural_counts={"PRESENT": 1},
        )
        scans.append(measurement)
        return measurement

    def coordinate(_scans):
        value = np.zeros(frozen.FEATURE_EPOCHS, dtype=np.float64)
        coordinates.append(value)
        return value, {
            "core_phase_and_lli": "SATISFIED",
            "same_path_code_witness": {"state": "SATISFIED"},
            "geometry_free_phase_health": {"state": "SATISFIED"},
        }

    monkeypatch.setattr(executor, "validate_executor_seal", validate)
    monkeypatch.setattr(primary, "decode_in_memory", decode)
    monkeypatch.setattr(executor, "scan_decoded", scan)
    monkeypatch.setattr(executor, "measurement_coordinate", coordinate)

    with TemporaryDirectory(dir=ROOT) as directory:
        output = Path(directory)
        outcome = executor.run_once(
            output,
            executor.AUTHORITY_TOKEN,
            "f" * 64,
            output / "seal.json",
            materializer=materialize,
        )
        persisted = (output / executor.OUTCOME_NAME).read_text(
            encoding="utf-8"
        )

    assert outcome["outcome"] == "ORBITAL_MODEL_PREDICTIVELY_PREFERRED"
    assert events[:2] == ["hash:ALGO00CAN", "hash:MDO100USA"]
    assert "phase_cycles" not in persisted
    assert "observed_coordinate" not in persisted
    assert outcome["persistence"]["observation_values"] == 0
    assert all(not any(payload) for payload in compressed + decoded)
    assert all(np.count_nonzero(scan.phase_cycles) == 0 for scan in scans)
    assert all(np.count_nonzero(value) == 0 for value in coordinates)


def test_decode_failure_has_zero_transport_retry(monkeypatch) -> None:
    curves = synthetic_curves(frozen.SCREEN_PAIRWISE_GUARD_M + 1.0)
    expected_headers = {
        product.station: synthetic_expected(product)
        for product in executor.PRODUCTS
    }
    calls: list[str] = []

    def validate(*_args):
        return {
            "source_commit": "frozen",
            "source_sha256": "a" * 64,
        }, curves, expected_headers

    def materialize(product: executor.ProductPlan):
        calls.append(product.station)
        payload = bytearray(product.station.encode("ascii"))
        return payload, {
            "station": product.station,
            "attempts_total": 1,
            "complete_file_bytes": len(payload),
            "complete_file_sha256": sha256(payload).hexdigest(),
        }

    def decode(_payload: bytearray, station: str):
        raise primary.PrimaryMeasurementInvalid(f"DECODE_FAILED:{station}")

    monkeypatch.setattr(executor, "validate_executor_seal", validate)
    monkeypatch.setattr(primary, "decode_in_memory", decode)

    with TemporaryDirectory(dir=ROOT) as directory:
        output = Path(directory)
        outcome = executor.run_once(
            output,
            executor.AUTHORITY_TOKEN,
            "f" * 64,
            output / "seal.json",
            materializer=materialize,
        )

    assert outcome["outcome"] == "MEASUREMENT_INVALID"
    assert outcome["heldout_comparison"] == "NOT_EVALUATED"
    assert calls == ["ALGO00CAN", "MDO100USA"]


def test_strict_json_rejects_nonfinite_values() -> None:
    with pytest.raises(ValueError):
        executor.strict_json({"bad": float("nan")})
    assert json.loads(executor.strict_json(executor.executor_manifest())) == (
        executor.executor_manifest()
    )
