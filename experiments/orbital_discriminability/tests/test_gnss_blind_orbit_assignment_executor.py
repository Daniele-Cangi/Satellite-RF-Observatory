from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Mapping

import numpy as np
import pytest

from experiments.orbital_discriminability import (
    gnss_blind_orbit_assignment_executor as executor,
)
from experiments.orbital_discriminability import (
    gnss_blind_orbit_assignment_plan as plan,
)


ROOT = Path(__file__).resolve().parents[1]
EXECUTOR_SEAL = ROOT / executor.EXECUTOR_SEAL_NAME
EXECUTOR_SOURCE_COMMIT = "07f31033258fcee87071b128cad48f74b2d6f946"
EXECUTOR_SOURCE_SHA256 = (
    "70a1c0cc1af1aeed1b58fd52a02cfafd310652dd01eb3c2e140cb61231d247c4"
)
EXECUTOR_MANIFEST_SHA256 = (
    "d26bf3498d9e6c382e0ef9c57b5c5a6111d8540e089efee72dc6c5d8c539c4d9"
)
EXECUTOR_SEAL_SHA256 = (
    "2d385f73a0e6a5a8038fe875262b10022f95c04b4e9116f3ab0ecc87b95cd1be"
)


def header_line(data: str, label: str) -> str:
    return f"{data:<60}{label:<20}\n"


def field(value: float, lli: int = 0) -> str:
    return f"{value:14.3f}{' ' if lli == 0 else lli} "


def synthetic_transform() -> dict[str, object]:
    return {
        "marker_name": "AMC4",
        "receiver": {
            "serial": "3013929",
            "type": "SEPT POLARX5TR",
            "version_or_radome": "5.6.0",
        },
        "antenna": {
            "serial": "1364-10065",
            "type": "TPSCR.G5C NONE",
            "version_or_radome": "",
        },
        "receiver_clock_offset_applied": 0,
        "required_phase_shift_records": [],
        "applied_bias_records": [],
        "scale_factor_records": [],
    }


def fixture(
    *,
    nonzero_lli: tuple[int, str, str] | None = None,
    code_slew_m: float = 0.0,
) -> bytearray:
    observables = ("C1C", "L1C", "S1C", "C2W", "L2W", "S2W")
    lines = [
        header_line(
            "     3.04           OBSERVATION DATA    G", "RINEX VERSION / TYPE"
        ),
        header_line("AMC4", "MARKER NAME"),
        header_line(
            f"{'3013929':<20}{'SEPT POLARX5TR':<20}{'5.6.0':<20}",
            "REC # / TYPE / VERS",
        ),
        header_line(f"{'1364-10065':<20}{'TPSCR.G5C NONE':<20}", "ANT # / TYPE"),
        header_line(" -1640916.0 -5014782.0 3575448.0", "APPROX POSITION XYZ"),
        header_line(
            f"G  {len(observables):3d} "
            + "".join(f"{item:>3} " for item in observables),
            "SYS / # / OBS TYPES",
        ),
        header_line("      30.000", "INTERVAL"),
        header_line(
            "  2026     8    14     0     0    0.0000000     GPS",
            "TIME OF FIRST OBS",
        ),
        header_line(
            "  2026     8    14    23    59   30.0000000     GPS",
            "TIME OF LAST OBS",
        ),
        header_line("", "END OF HEADER"),
    ]
    for epoch_index, epoch in enumerate(executor.expected_raw_gps_epochs()):
        lines.append(
            f"> {epoch.year:4d} {epoch.month:02d} {epoch.day:02d} "
            f"{epoch.hour:02d} {epoch.minute:02d} {epoch.second:10.7f}  0  2\n"
        )
        for satellite_index, satellite in enumerate(executor.SATELLITES):
            phase_base = 115_000_000.0 + satellite_index * 2_000.0
            code_base = 22_000_000.0 + satellite_index * 100.0
            values: dict[str, tuple[float, int]] = {
                "C1C": (code_base + epoch_index * code_slew_m, 0),
                "L1C": (phase_base + epoch_index * 0.020, 0),
                "S1C": (45.0, 0),
                "C2W": (code_base + 10.0 + epoch_index * code_slew_m, 0),
                "L2W": (
                    89_000_000.0 + satellite_index * 1_500.0 + epoch_index * 0.015,
                    0,
                ),
                "S2W": (43.0, 0),
            }
            if nonzero_lli and nonzero_lli[:2] == (epoch_index, satellite):
                value, _ = values[nonzero_lli[2]]
                values[nonzero_lli[2]] = (value, 1)
            lines.append(
                satellite + "".join(field(*values[item]) for item in observables) + "\n"
            )
    return bytearray("".join(lines).encode("ascii"))


def opaque_receipt(
    best: str = "H_72E7F21DC8244653",
    *,
    opaque_outcome: str = "OPAQUE_HYPOTHESIS_PREFERRED",
) -> dict[str, object]:
    identifiers = (
        "H_0F7B423DEE4445EB",
        "H_113EA69083E0450B",
        "H_5A7421B20092455F",
        "H_72E7F21DC8244653",
        "H_970DD1C2274548B5",
        "H_B7DAF98094A64E7E",
    )
    runner = next(item for item in identifiers if item != best)
    return {
        "schema": "gnss-opaque-orbit-score-receipt-v1",
        "scorer_version": "gnss-opaque-orbit-scorer-v1",
        "bundle_canonical_sha256": executor.scorer.BUNDLE_CANONICAL_SHA256,
        "bundle_manifest_sha256": executor.scorer.BUNDLE_MANIFEST_SHA256,
        "observed_coordinate_sha256": "a" * 64,
        "observed_values_persisted": 0,
        "prefix_indices_inclusive": [0, 78],
        "heldout_indices_inclusive": [79, 138],
        "scores": [],
        "best_opaque_id": best,
        "runner_up_opaque_id": runner,
        "preference_margin_m": 9000.0,
        "pairwise_guard_m": 7339.701234647398,
        "opaque_outcome": opaque_outcome,
        "identity_reveal_performed": False,
        "same_loop_parameter_count": 2,
        "heldout_refit": False,
        "free_time_phase": False,
    }


def test_manifest_binds_one_unqueried_product_and_zero_access() -> None:
    manifest = executor.executor_manifest(ROOT)
    encoded = executor.strict_json(manifest)

    assert manifest["product"] == {
        "station": "AMC400USA",
        "logical_product": "AMC400USA_R_20262260000_01D_30S_MO.crx.gz",
        "directory": "/gnss/data/daily/2026/226",
        "product_existence": "UNKNOWN_UNQUERIED",
        "fallback": False,
    }
    assert not any(manifest["access_at_freeze"].values())
    assert manifest["measurement_packager"]["output_to_scorer"] == (
        "ONE_FINITE_UNLABELLED_COORDINATE_ARRAY"
    )
    assert manifest["live_execution_authorized"] is False
    assert executor.AUTHORITY_TOKEN not in encoded


def test_executor_seal_binds_source_manifest_and_zero_access() -> None:
    assert executor.canonical_sha256(EXECUTOR_SEAL) == EXECUTOR_SEAL_SHA256
    assert executor.source_sha256() == EXECUTOR_SOURCE_SHA256
    assert executor.manifest_sha256(ROOT) == EXECUTOR_MANIFEST_SHA256

    seal, bundle, transform = executor.validate_executor_seal(
        ROOT, EXECUTOR_SEAL, EXECUTOR_SEAL_SHA256
    )
    assert seal["source_commit"] == EXECUTOR_SOURCE_COMMIT
    assert seal["source_sha256"] == EXECUTOR_SOURCE_SHA256
    assert seal["manifest_sha256"] == EXECUTOR_MANIFEST_SHA256
    assert not any(seal["access_at_seal"].values())
    assert seal["authority"]["live_execution_authorized_by_seal"] is False
    assert len(bundle["opaque_ids"]) == 6
    assert transform["receiver"]["serial"] == "3013929"


def test_frozen_validation_hashes_but_does_not_parse_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = executor._read_strict_object

    def guarded(path: Path) -> dict[str, object]:
        assert Path(path).name != plan.MAPPING_NAME
        return original(path)

    monkeypatch.setattr(executor, "_read_strict_object", guarded)
    bundle, transform = executor.validate_frozen_inputs(ROOT)

    assert len(bundle["opaque_ids"]) == 6
    assert transform["receiver"]["serial"] == "3013929"


def test_parser_coordinate_and_witness_use_exact_frozen_grid() -> None:
    scan = executor.scan_decoded(fixture(), synthetic_transform())
    try:
        coordinate, admission = executor.measurement_coordinate(scan)
        assert coordinate.shape == (139,)
        assert np.all(np.isfinite(coordinate))
        coordinate.fill(0.0)
    finally:
        scan.erase()

    assert admission["event_time"]["maximum_absolute_deviation_s"] == 0.0
    assert admission["geometry_free_phase_health"]["state"] == "SATISFIED"
    assert admission["same_path_code_phase_witness"]["state"] == "SATISFIED"


def test_nonzero_lli_is_measurement_invalid() -> None:
    with pytest.raises(executor.PrimaryMeasurementInvalid, match="NONZERO"):
        executor.scan_decoded(
            fixture(nonzero_lli=(79, "G22", "L1C")), synthetic_transform()
        )


def test_finite_code_phase_over_limit_is_not_detectable() -> None:
    scan = executor.scan_decoded(fixture(code_slew_m=20.0), synthetic_transform())
    try:
        with pytest.raises(executor.PrimaryNotDetectable, match="WITNESS_OVER_LIMIT"):
            executor.measurement_coordinate(scan)
    finally:
        scan.erase()


@pytest.mark.parametrize(
    ("best", "opaque_state", "expected"),
    (
        (
            "H_72E7F21DC8244653",
            "OPAQUE_HYPOTHESIS_PREFERRED",
            "BOUNDED_TRUE_ORBIT_PREFERRED",
        ),
        (
            "H_970DD1C2274548B5",
            "OPAQUE_HYPOTHESIS_PREFERRED",
            "BOUNDED_ALTERNATIVE_ORBIT_PREFERRED",
        ),
        (
            "H_0F7B423DEE4445EB",
            "OPAQUE_HYPOTHESIS_PREFERRED",
            "FROZEN_AFFINE_NULL_PREFERRED",
        ),
        ("H_72E7F21DC8244653", "AMBIGUOUS", "AMBIGUOUS"),
    ),
)
def test_mapping_reveal_has_exact_terminal_semantics(
    best: str, opaque_state: str, expected: str
) -> None:
    receipt = opaque_receipt(best, opaque_outcome=opaque_state)
    with TemporaryDirectory() as directory:
        output = Path(directory)
        score_path, digest, hash_path = executor._persist_opaque_score(output, receipt)
        result = executor.reveal_mapping(ROOT, receipt, score_path, hash_path, digest)

    assert result["outcome"] == expected
    if expected == "AMBIGUOUS":
        assert result["revealed_model"] is None
    elif expected == "BOUNDED_ALTERNATIVE_ORBIT_PREFERRED":
        assert result["revealed_model"] == "G06_RELATIVE_TO_G30"


def test_mapping_is_read_only_after_score_and_hash_receipts_exist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seal = {"source_commit": "frozen", "source_sha256": "b" * 64}
    compressed = bytearray(b"compressed")
    decoded = fixture()
    scans: list[executor.StationMeasurement] = []
    coordinates: list[np.ndarray] = []

    monkeypatch.setattr(
        executor,
        "validate_executor_seal",
        lambda *_args: (seal, {}, synthetic_transform()),
    )
    monkeypatch.setattr(executor, "decompress_in_memory", lambda _payload: decoded)
    original_scan = executor.scan_decoded
    original_coordinate = executor.measurement_coordinate

    def scan(payload: bytearray, transform: Mapping[str, object]):
        value = original_scan(payload, transform)
        scans.append(value)
        return value

    def coordinate(scan_value: executor.StationMeasurement):
        value, admission = original_coordinate(scan_value)
        coordinates.append(value)
        return value, admission

    monkeypatch.setattr(executor, "scan_decoded", scan)
    monkeypatch.setattr(executor, "measurement_coordinate", coordinate)
    monkeypatch.setattr(
        executor.scorer, "score", lambda _coordinate, _bundle: opaque_receipt()
    )
    original_reveal = executor.reveal_mapping

    def ordered_reveal(
        root: Path,
        receipt: Mapping[str, object],
        score_path: Path,
        score_hash_path: Path,
        digest: str,
    ) -> dict[str, object]:
        assert score_path.is_file()
        assert score_hash_path.is_file()
        assert executor.canonical_sha256(score_path) == digest
        return original_reveal(root, receipt, score_path, score_hash_path, digest)

    monkeypatch.setattr(executor, "reveal_mapping", ordered_reveal)

    def materialize():
        assert marker_path.is_file()
        return compressed, {
            "station": "AMC400USA",
            "product": plan.PRIMARY_PRODUCT,
            "attempts": 1,
            "complete_file_bytes": len(compressed),
            "complete_file_sha256": sha256(compressed).hexdigest(),
        }

    with TemporaryDirectory() as directory:
        output = Path(directory)
        marker_path = output / executor.AUTHORITY_MARKER_NAME
        outcome = executor.run_once(
            output,
            executor.AUTHORITY_TOKEN,
            "f" * 64,
            output / "seal.json",
            materializer=materialize,
        )
        persisted = (output / executor.OUTCOME_NAME).read_text(encoding="ascii")
        score_persisted = (output / executor.OPAQUE_SCORE_NAME).read_text(
            encoding="ascii"
        )
        with pytest.raises(PermissionError, match="ALREADY_CONSUMED"):
            executor.run_once(
                output,
                executor.AUTHORITY_TOKEN,
                "f" * 64,
                output / "seal.json",
                materializer=materialize,
            )

    assert outcome["outcome"] == "BOUNDED_TRUE_ORBIT_PREFERRED"
    assert (
        outcome["identity_reveal"]["performed_after_opaque_score_receipt_hash"] is True
    )
    assert outcome["persistence"]["observation_values"] == 0
    assert "G22_RELATIVE_TO_G30" in persisted
    assert "G22" not in score_persisted and "G30" not in score_persisted
    assert not any(compressed) and not any(decoded)
    assert all(not np.any(scan_value.phase_cycles) for scan_value in scans)
    assert all(not np.any(value) for value in coordinates)


def test_authority_refuses_before_seal_marker_or_network() -> None:
    called = False

    def forbidden():
        nonlocal called
        called = True
        raise AssertionError("network reached")

    with TemporaryDirectory() as directory:
        output = Path(directory)
        with pytest.raises(PermissionError, match="AUTHORITY_REQUIRED"):
            executor.run_once(
                output,
                "",
                "0" * 64,
                output / "missing.json",
                materializer=forbidden,
            )
        assert not (output / executor.AUTHORITY_MARKER_NAME).exists()
    assert called is False


def test_complete_hash_is_recomputed_before_decode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        executor,
        "validate_executor_seal",
        lambda *_args: (
            {"source_commit": "frozen", "source_sha256": "b" * 64},
            {},
            synthetic_transform(),
        ),
    )
    decode_reached = False

    def forbidden_decode(_payload: bytearray):
        nonlocal decode_reached
        decode_reached = True
        raise AssertionError("decode reached")

    monkeypatch.setattr(executor, "decompress_in_memory", forbidden_decode)
    payload = bytearray(b"complete")

    def dishonest_materializer():
        return payload, {
            "station": "AMC400USA",
            "product": plan.PRIMARY_PRODUCT,
            "attempts": 1,
            "complete_file_bytes": len(payload),
            "complete_file_sha256": "0" * 64,
        }

    with TemporaryDirectory() as directory:
        outcome = executor.run_once(
            Path(directory),
            executor.AUTHORITY_TOKEN,
            "f" * 64,
            Path(directory) / "seal.json",
            materializer=dishonest_materializer,
        )

    assert outcome["outcome"] == "PRIMARY_DESCRIPTION_ERROR"
    assert outcome["reason"].endswith("PRIMARY_COMPLETE_SHA256_CHANGED")
    assert decode_reached is False
    assert not any(payload)


def test_description_failure_is_not_a_measurement_rejection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        executor,
        "validate_executor_seal",
        lambda *_args: (
            {"source_commit": "frozen", "source_sha256": "b" * 64},
            {},
            synthetic_transform(),
        ),
    )

    def describe_failure():
        raise executor.PrimaryDescriptionError("DIRECTORY_DESCRIPTION_FAILED")

    with TemporaryDirectory() as directory:
        outcome = executor.run_once(
            Path(directory),
            executor.AUTHORITY_TOKEN,
            "f" * 64,
            Path(directory) / "seal.json",
            materializer=describe_failure,
        )

    assert outcome["outcome"] == "PRIMARY_DESCRIPTION_ERROR"
    assert outcome["physical_outcome"] is None
    assert outcome["heldout_comparison"] == "NOT_EVALUATED"


def test_transport_budget_is_exactly_two_pre_hash_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0

    def interrupted():
        nonlocal attempts
        attempts += 1
        raise executor.TransportInterruption("TIMEOUT")

    monkeypatch.setattr(executor, "_new_gssc_session", interrupted)
    with pytest.raises(executor.PrimaryMaterializationError) as failure:
        executor.materialize_gssc()

    assert attempts == 2
    assert failure.value.receipt["complete_file_sha256"] is None
    assert failure.value.receipt["retry_after_hash_or_decode"] is False


def test_size_limit_erases_partial_primary_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    buffers: list[bytearray] = []

    class TrackingBytearray(bytearray):
        def __init__(self, *args: object) -> None:
            super().__init__(*args)
            buffers.append(self)

    class Response:
        @staticmethod
        def raise_for_status() -> None:
            return None

        @staticmethod
        def iter_content(*, chunk_size: int):
            assert chunk_size == 1024 * 1024
            yield b"x" * (executor.MAX_COMPRESSED_BYTES + 1)

    class Session:
        @staticmethod
        def get(*_args: object, **_kwargs: object) -> Response:
            return Response()

    monkeypatch.setattr(executor, "bytearray", TrackingBytearray, raising=False)
    with pytest.raises(
        executor.PrimaryDescriptionError, match="PRIMARY_COMPRESSED_SIZE_LIMIT"
    ):
        executor._download_gssc(
            Session(),
            {"bytes": executor.MAX_COMPRESSED_BYTES + 1, "md5": ""},
        )

    assert len(buffers) == 1
    assert buffers[0]
    assert not any(buffers[0])


def test_decoder_distinguishes_invalid_data_from_software_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[bytes, bool]] = []

    def valid(content: bytes, *, strict: bool) -> bytes:
        calls.append((content, strict))
        return b"RINEX"

    monkeypatch.setattr(executor.hatanaka, "decompress", valid)
    assert executor.decompress_in_memory(bytearray(b"compressed")) == b"RINEX"
    assert calls == [(b"compressed", True)]

    def invalid(_content: bytes, *, strict: bool) -> bytes:
        assert strict is True
        raise executor.hatanaka.HatanakaException("invalid compressed RINEX")

    monkeypatch.setattr(executor.hatanaka, "decompress", invalid)
    with pytest.raises(
        executor.PrimaryMeasurementInvalid, match="HATANAKA_DECOMPRESSION_FAILED"
    ):
        executor.decompress_in_memory(bytearray(b"invalid"))

    def software_fault(_content: bytes, *, strict: bool) -> bytes:
        assert strict is True
        raise TypeError("decoder API mismatch")

    monkeypatch.setattr(executor.hatanaka, "decompress", software_fault)
    with pytest.raises(
        executor.PrimaryDescriptionError, match="HATANAKA_DECODER_SOFTWARE_FAILURE"
    ):
        executor.decompress_in_memory(bytearray(b"valid-looking"))


def test_json_boundaries_are_strict() -> None:
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            executor.strict_json({"value": value})

    with pytest.raises(TypeError):
        executor.strict_json({"value": np.bool_(True)})
