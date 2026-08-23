from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import (
    gnss_independent_primary_evaluator as evaluator,
)


def header_line(data: str, label: str) -> str:
    return f"{data:<60}{label:<20}\n"


def field(value: float | None, lli: int = 0) -> str:
    if value is None:
        return " " * 16
    return f"{value:14.3f}{' ' if lli == 0 else lli} "


def short_epochs(count: int = 5) -> tuple[datetime, ...]:
    start = datetime(2026, 8, 3, 16, 2, 30, tzinfo=timezone.utc)
    return tuple(
        start + timedelta(seconds=30 * index) for index in range(count)
    )


def fixture(
    epochs: tuple[datetime, ...],
    *,
    station: str = "KIRU00SWE",
    missing_snr: bool = False,
    lli_epoch: int | None = None,
    phase_jump_epoch: int | None = None,
    final_field_without_indicators: bool = False,
) -> bytearray:
    types = evaluator.OBSERVABLES
    time_system = " " * 48 + "GPS"
    lines = [
        header_line(
            "     3.04           OBSERVATION DATA    M",
            "RINEX VERSION / TYPE",
        ),
        header_line(station, "MARKER NAME"),
        header_line(f"{evaluator.STEP_S:10.3f}", "INTERVAL"),
        header_line(time_system, "TIME OF FIRST OBS"),
        header_line(
            f"G  {len(types):3d} "
            + "".join(f"{item:>3} " for item in types),
            "SYS / # / OBS TYPES",
        ),
        header_line("", "END OF HEADER"),
    ]
    for epoch_index, epoch in enumerate(epochs):
        lines.append(
            f"> {epoch.year:4d} {epoch.month:02d} {epoch.day:02d} "
            f"{epoch.hour:02d} {epoch.minute:02d} "
            f"{epoch.second:10.7f}  0  2\n"
        )
        for satellite_index, satellite in enumerate(evaluator.SATELLITES):
            jump = (
                1.0
                if phase_jump_epoch == epoch_index
                and satellite_index == 0
                else 0.0
            )
            values = (
                22_000_000.0 + epoch_index,
                115_000_000.0 + epoch_index * 0.02 + jump,
                (
                    None
                    if missing_snr
                    and epoch_index == 2
                    and satellite_index == 0
                    else 45.0
                ),
                22_000_010.0 + epoch_index,
                89_000_000.0 + epoch_index * 0.015,
                43.0,
            )
            record = satellite + "".join(
                field(
                    value,
                    (
                        1
                        if lli_epoch == epoch_index
                        and observation_index in (1, 4)
                        else 0
                    ),
                )
                for observation_index, value in enumerate(values)
            )
            if final_field_without_indicators:
                record = record[:-2]
            lines.append(record + "\n")
    return bytearray("".join(lines).encode("ascii"))


def test_frozen_epoch_grid_is_exact_numerical_regression() -> None:
    epochs = evaluator.frozen_epoch_grid()
    assert len(epochs) == 380
    assert epochs[0] == evaluator.RAW_START_GPS
    assert epochs[-1] == evaluator.RAW_STOP_GPS
    assert (epochs[1] - epochs[0]).total_seconds() == 30.0


def test_plain_parser_accepts_final_14_character_field() -> None:
    epochs = short_epochs()
    parsed = evaluator.parse_plain_rinex_window(
        fixture(epochs, final_field_without_indicators=True),
        "KIRU00SWE",
        epochs,
    )
    try:
        assert parsed.values.shape == (5, 2, 6)
        assert parsed.values[2, 0, 0] == 22_000_002.0
        assert np.all(parsed.lli == 0)
    finally:
        parsed.erase()
    assert np.all(parsed.values == 0.0)


def test_missing_same_path_witness_is_measurement_invalid() -> None:
    epochs = short_epochs()
    with pytest.raises(
        evaluator.MeasurementInvalid, match="MISSING_OR_NONFINITE"
    ):
        evaluator.parse_plain_rinex_window(
            fixture(epochs, missing_snr=True),
            "KIRU00SWE",
            epochs,
        )


def test_unknown_fixed_width_representation_is_description_error() -> None:
    payload = fixture(short_epochs())
    first_record = payload.index(b"G20")
    newline = payload.index(b"\n", first_record)
    del payload[newline - 1]
    with pytest.raises(
        evaluator.PrimaryEvaluationError,
        match="PARTIAL_FIXED_WIDTH",
    ):
        evaluator.parse_plain_rinex_window(
            payload, "KIRU00SWE", short_epochs()
        )


def test_header_clock_policy_and_marker_are_admission_clauses() -> None:
    payload = fixture(short_epochs(), station="WRONG")
    with pytest.raises(
        evaluator.MeasurementInvalid, match="STATION_MARKER"
    ):
        evaluator.parse_plain_rinex_window(
            payload, "KIRU00SWE", short_epochs()
        )


def test_nonzero_lli_is_refused() -> None:
    epochs = evaluator.frozen_epoch_grid()
    parsed = evaluator.parse_plain_rinex_window(
        fixture(epochs, lli_epoch=100), "KIRU00SWE", epochs
    )
    try:
        with pytest.raises(
            evaluator.MeasurementInvalid, match="NONZERO_LLI"
        ):
            evaluator.validate_station(parsed)
    finally:
        parsed.erase()


def test_geometry_free_second_difference_refuses_jump() -> None:
    epochs = evaluator.frozen_epoch_grid()
    parsed = evaluator.parse_plain_rinex_window(
        fixture(epochs, phase_jump_epoch=100),
        "KIRU00SWE",
        epochs,
    )
    try:
        with pytest.raises(
            evaluator.MeasurementInvalid, match="GEOMETRY_FREE"
        ):
            evaluator.validate_station(parsed)
    finally:
        parsed.erase()


def hypotheses_with_heldout_curvature(
    peak_hz: float = 4_000.0,
) -> dict[str, np.ndarray]:
    curve = np.zeros(evaluator.FEATURE_RECORDS, dtype=np.float64)
    curve[evaluator.CALIBRATION_RECORDS :] = np.linspace(
        0.0, peak_hz, evaluator.HELDOUT_RECORDS
    )
    return {
        "H_G20": curve.copy(),
        "H_AFFINE": np.zeros_like(curve),
        "H_G14": -curve.copy(),
    }


@pytest.mark.parametrize(
    ("winner", "expected"),
    (
        ("H_G20", "ORBITAL_MODEL_PREDICTIVELY_PREFERRED"),
        ("H_AFFINE", "PREFIX_AFFINE_NULL_PREFERRED"),
        ("H_G14", "WRONG_ORBIT_G14_PREFERRED"),
    ),
)
def test_prefix_only_scoring_can_prefer_each_frozen_hypothesis(
    winner: str, expected: str
) -> None:
    hypotheses = hypotheses_with_heldout_curvature()
    elapsed = (
        np.arange(evaluator.FEATURE_RECORDS, dtype=np.float64)
        * evaluator.STEP_S
    )
    observed = hypotheses[winner] + 12.0 - 0.01 * elapsed
    outcome, scores, margins, detectability = (
        evaluator.evaluate_observed(observed, hypotheses)
    )
    assert outcome == expected
    assert scores[winner]["heldout_peak_to_peak_hz"] < 1e-8
    assert margins[winner] > evaluator.PAIRWISE_DECISION_GUARD_HZ
    assert detectability["clause"] == "SATISFIED"


def test_large_prefix_residual_blocks_all_heldout_scoring(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed = np.zeros(evaluator.FEATURE_RECORDS, dtype=np.float64)
    observed[: evaluator.CALIBRATION_RECORDS] = (
        np.arange(evaluator.CALIBRATION_RECORDS) % 2
    ) * 1_000.0
    hypotheses = {
        name: np.zeros_like(observed) for name in evaluator.HYPOTHESES
    }

    def forbidden_score(*args: object, **kwargs: object) -> object:
        raise AssertionError("held-out scorer was called")

    monkeypatch.setattr(evaluator, "score_hypothesis", forbidden_score)
    outcome, scores, margins, detectability = (
        evaluator.evaluate_observed(observed, hypotheses)
    )
    assert outcome == "NOT_DETECTABLE"
    assert scores == {}
    assert margins == {}
    assert detectability["clause"] == "UNSATISFIED"


def test_pairwise_guard_equality_is_ambiguous() -> None:
    hypotheses = hypotheses_with_heldout_curvature(
        evaluator.PAIRWISE_DECISION_GUARD_HZ
    )
    observed = np.zeros(evaluator.FEATURE_RECORDS, dtype=np.float64)
    outcome, _, margins, _ = evaluator.evaluate_observed(
        observed, hypotheses
    )
    assert margins["H_AFFINE"] == pytest.approx(
        evaluator.PAIRWISE_DECISION_GUARD_HZ
    )
    assert outcome == "AMBIGUOUS"


def test_observed_coordinate_is_deterministic_and_erases_intermediates() -> None:
    epochs = evaluator.frozen_epoch_grid()
    shape = (evaluator.RAW_RECORDS, 2, len(evaluator.OBSERVABLES))
    left_values = np.zeros(shape, dtype=np.float64)
    right_values = np.zeros(shape, dtype=np.float64)
    left_lli = np.zeros(
        (
            evaluator.RAW_RECORDS,
            2,
            len(evaluator.PHASE_OBSERVABLES),
        ),
        dtype=np.int8,
    )
    right_lli = left_lli.copy()
    alpha, _ = evaluator.envelope.ionosphere_free_coefficients()
    wavelength = (
        evaluator.screen.SPEED_OF_LIGHT_M_S
        / evaluator.envelope.GPS_L1_HZ
    )
    index = np.arange(evaluator.RAW_RECORDS, dtype=np.float64)
    path_m = 0.01 * index * index
    left_values[:, 0, evaluator.OBSERVABLES.index("L1C")] = (
        path_m / (alpha * wavelength)
    )
    left = evaluator.StationWindow(
        "KIRU00SWE", epochs, left_values, left_lli
    )
    right = evaluator.StationWindow(
        "MAT100ITA", epochs, right_values, right_lli
    )
    coordinate = evaluator.observed_coordinate(left, right)
    expected = (
        -evaluator.envelope.GPS_L1_HZ
        / evaluator.screen.SPEED_OF_LIGHT_M_S
        * (0.04 * np.arange(1, evaluator.RAW_RECORDS - 1))
        / evaluator.DERIVATIVE_BASELINE_S
    )
    assert coordinate.shape == (evaluator.FEATURE_RECORDS,)
    assert np.allclose(coordinate, expected)


def test_strict_json_rejects_nonfinite_and_numpy_scalars() -> None:
    with pytest.raises(ValueError):
        evaluator.strict_json({"value": float("nan")})
    with pytest.raises(ValueError):
        evaluator.strict_json({"value": float("inf")})
    with pytest.raises(TypeError):
        evaluator.strict_json({"value": np.bool_(True)})
    with pytest.raises(TypeError):
        evaluator.strict_json({"value": np.float64(1.0)})


def seal_document(source_commit: str = "a" * 40) -> dict[str, object]:
    return {
        "schema": "gnss-independent-primary-evaluator-seal-v1",
        "source_commit": source_commit,
        "plan_sha256": evaluator.PLAN_SHA256,
        "evaluator_source_sha256": evaluator.file_sha256(
            Path(evaluator.__file__)
        ),
        "runtime_manifest_sha256": evaluator.runtime_manifest_sha256(),
    }


def authority_document(
    seal: dict[str, object], seal_sha256: str
) -> dict[str, object]:
    return {
        "schema": "gnss-independent-primary-access-authority-v1",
        "state": "PRIMARY_ACCESS_AUTHORIZED",
        "plan_sha256": evaluator.PLAN_SHA256,
        "prospective_markdown_sha256": evaluator.PLAN_SHA256,
        "evaluator_seal_sha256": seal_sha256,
        "evaluator_source_sha256": seal["evaluator_source_sha256"],
        "source_commit": seal["source_commit"],
        "single_run": True,
        "products": [
            item["name"] for item in evaluator.PRIMARY_PRODUCTS
        ],
    }


def write_json(path: Path, value: dict[str, object]) -> str:
    payload = evaluator.strict_json(value) + "\n"
    path.write_text(payload, encoding="ascii", newline="\n")
    return sha256(payload.encode("ascii")).hexdigest()


def test_seal_and_authority_are_bound_to_source_and_plan(
    tmp_path: Path,
) -> None:
    seal = seal_document()
    seal_path = tmp_path / "seal.json"
    seal_sha256 = write_json(seal_path, seal)
    loaded, actual_sha256 = evaluator.verify_seal(
        seal_path, Path(evaluator.__file__)
    )
    assert loaded == seal
    assert actual_sha256 == seal_sha256

    authority = authority_document(seal, seal_sha256)
    authority_path = tmp_path / "authority.json"
    authority_sha256 = write_json(authority_path, authority)
    loaded_authority, actual_authority_sha256 = (
        evaluator.verify_authority(
            authority_path, loaded, seal_sha256
        )
    )
    assert loaded_authority == authority
    assert actual_authority_sha256 == authority_sha256

    authority["plan_sha256"] = "0" * 64
    write_json(authority_path, authority)
    with pytest.raises(
        evaluator.PrimaryEvaluationError,
        match="AUTHORITY_BINDING_CHANGED:plan_sha256",
    ):
        evaluator.verify_authority(
            authority_path, loaded, seal_sha256
        )


def materialization_document() -> dict[str, object]:
    return {
        "schema": "gnss-independent-primary-materialization-v1",
        "state": "PRIMARY_ARTIFACTS_MATERIALIZED",
        "plan_sha256": evaluator.PLAN_SHA256,
        "hashes_completed_before_decompression": True,
        "artifacts": [
            {
                "station_id": item["station_id"],
                "name": item["name"],
                "bytes": item["bytes"],
                "sha256": "0" * 64,
            }
            for item in evaluator.PRIMARY_PRODUCTS
        ],
    }


def test_materialization_failure_is_premeasurement_and_does_not_decode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seal = seal_document()
    seal_path = tmp_path / "seal.json"
    seal_sha256 = write_json(seal_path, seal)
    authority_path = tmp_path / "authority.json"
    write_json(
        authority_path, authority_document(seal, seal_sha256)
    )
    materialization_path = tmp_path / "materialization.json"
    write_json(materialization_path, materialization_document())
    product_paths = [
        tmp_path / str(item["name"])
        for item in evaluator.PRIMARY_PRODUCTS
    ]

    def forbidden_decode(*args: object, **kwargs: object) -> object:
        raise AssertionError("decoder was called")

    monkeypatch.setattr(
        evaluator, "decode_exact_station", forbidden_decode
    )
    output = tmp_path / "outcome.jsonl"
    receipt = evaluator.run_once(
        product_paths[0],
        product_paths[1],
        tmp_path / "navigation.rnx",
        seal_path,
        authority_path,
        materialization_path,
        output,
    )
    assert receipt["outcome"] == "ARTIFACT_MATERIALIZATION_FAILED"
    assert receipt["physical_decision"] == "NOT_EVALUATED"
    assert receipt["decompression_started"] is False
    assert receipt["measurement_clauses"][
        "heldout_model_comparison"
    ] == "NOT_EVALUATED"
    assert output.is_file()


def test_description_error_after_start_cannot_become_physical_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seal = seal_document()
    seal_path = tmp_path / "seal.json"
    seal_sha256 = write_json(seal_path, seal)
    authority_path = tmp_path / "authority.json"
    write_json(
        authority_path, authority_document(seal, seal_sha256)
    )
    materialization_path = tmp_path / "materialization.json"
    write_json(materialization_path, materialization_document())
    authorities = tuple(
        evaluator.ProductAuthority(
            station_id=str(item["station_id"]),
            name=str(item["name"]),
            url="",
            bytes=int(item["bytes"]),
            sha256="0" * 64,
        )
        for item in evaluator.PRIMARY_PRODUCTS
    )
    monkeypatch.setattr(
        evaluator,
        "validate_materialization",
        lambda *args, **kwargs: (authorities, "1" * 64),
    )
    monkeypatch.setattr(
        evaluator.screen,
        "validate_navigation",
        lambda path: {"name": "synthetic-navigation"},
    )
    monkeypatch.setattr(
        evaluator,
        "prediction_curves",
        lambda path: hypotheses_with_heldout_curvature(),
    )

    def description_error(*args: object, **kwargs: object) -> object:
        raise evaluator.PrimaryEvaluationError(
            "UNSUPPORTED_SYNTHETIC_DESCRIPTION"
        )

    monkeypatch.setattr(
        evaluator, "decode_exact_station", description_error
    )
    receipt = evaluator.run_once(
        tmp_path / str(evaluator.PRIMARY_PRODUCTS[0]["name"]),
        tmp_path / str(evaluator.PRIMARY_PRODUCTS[1]["name"]),
        tmp_path / "navigation.rnx",
        seal_path,
        authority_path,
        materialization_path,
        tmp_path / "outcome.jsonl",
    )
    assert receipt["outcome"] == "PRIMARY_EVALUATION_ERROR"
    assert receipt["physical_decision"] == "NOT_EVALUATED"
    assert receipt["clauses"]["heldout_model_comparison"] == (
        "NOT_EVALUATED"
    )
    assert receipt["decompression_started"] is True


def test_decompressed_bytearray_is_overwritten(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, bytearray] = {}
    synthetic = bytes(fixture(short_epochs()))

    monkeypatch.setattr(
        evaluator.hatanaka,
        "decompress",
        lambda path, strict: synthetic,
    )

    def capture(
        decoded: bytearray,
        station_id: str,
        expected_epochs: tuple[datetime, ...],
    ) -> evaluator.StationWindow:
        captured["decoded"] = decoded
        return evaluator.StationWindow(
            station_id,
            evaluator.frozen_epoch_grid(),
            np.zeros(
                (
                    evaluator.RAW_RECORDS,
                    2,
                    len(evaluator.OBSERVABLES),
                ),
                dtype=np.float64,
            ),
            np.zeros(
                (
                    evaluator.RAW_RECORDS,
                    2,
                    len(evaluator.PHASE_OBSERVABLES),
                ),
                dtype=np.int8,
            ),
        )

    monkeypatch.setattr(
        evaluator, "parse_plain_rinex_window", capture
    )
    authority = evaluator.ProductAuthority(
        "KIRU00SWE", "synthetic.crx.gz", "", 1, "0" * 64
    )
    window = evaluator.decode_exact_station(
        Path("synthetic.crx.gz"), authority
    )
    try:
        assert captured["decoded"]
        assert not any(captured["decoded"])
    finally:
        window.erase()


def test_repository_manifest_seals_exact_committed_source() -> None:
    manifest_path = Path(evaluator.__file__).with_name(
        "GNSS_INDEPENDENT_PRIMARY_EVALUATOR_MANIFEST.json"
    )
    manifest, manifest_sha256 = evaluator.verify_seal(
        manifest_path, Path(evaluator.__file__)
    )
    assert manifest_sha256 == (
        "b2e09192345db050d61ae843ba01095f50b1deef5f2d9603c9365634519d8807"
    )
    assert manifest["source_commit"] == (
        "770d255eae80a1929eb12102b166dc915fe43908"
    )
    assert manifest["state"] == "EVALUATOR_FROZEN_PRIMARY_BLOCKED"
    assert manifest["access_state"]["primary_artifact_bytes_opened"] == 0
