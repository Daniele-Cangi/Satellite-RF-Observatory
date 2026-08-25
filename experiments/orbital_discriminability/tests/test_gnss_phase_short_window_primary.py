from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import (
    gnss_phase_short_window_primary as primary,
)
from experiments.orbital_discriminability import (
    gnss_phase_short_window_plan as frozen,
)


ROOT = Path(__file__).resolve().parents[1]


def header_line(data: str, label: str) -> str:
    return f"{data:<60}{label:<20}\n"


def field(value: float | None, lli: int = 0) -> str:
    if value is None:
        return " " * 16
    return f"{value:14.3f}{' ' if lli == 0 else lli} "


def fixture(
    locator: primary.ProductLocator,
    *,
    blank: tuple[int, str, str] | None = None,
    nonzero_lli: tuple[int, str, str] | None = None,
) -> bytearray:
    observables = ("C1C", "L1C", "S1C", "C2W", "L2W", "S2W")
    config = primary.EXPECTED_CONFIGURATION[locator.station]
    lines = [
        header_line(
            "     3.04           OBSERVATION DATA    G",
            "RINEX VERSION / TYPE",
        ),
        header_line(locator.station[:4], "MARKER NAME"),
        header_line(
            f"SERIAL              {config['receiver_type']:<20}"
            f"{config['receiver_version']:<20}",
            "REC # / TYPE / VERS",
        ),
        header_line(
            f"ANTENNA             {config['antenna_type']:<20}",
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
            "  2026     8     8     0     0    0.0000000     GPS",
            "TIME OF FIRST OBS",
        ),
        header_line(
            "  2026     8     8    23    59   30.0000000     GPS",
            "TIME OF LAST OBS",
        ),
        header_line("", "END OF HEADER"),
    ]
    station_bias = 200.0 if locator.station == "NLIB00USA" else 0.0
    for epoch_index, epoch in enumerate(primary.expected_raw_gps_epochs()):
        lines.append(
            f"> {epoch.year:4d} {epoch.month:02d} {epoch.day:02d} "
            f"{epoch.hour:02d} {epoch.minute:02d} "
            f"{epoch.second:10.7f}  0  2\n"
        )
        for sat_index, satellite in enumerate(primary.SATELLITES):
            values: dict[str, tuple[float | None, int]] = {
                "C1C": (22_000_000.0 + epoch_index + sat_index, 0),
                "L1C": (
                    115_000_000.0
                    + station_bias
                    + epoch_index * 0.020
                    + sat_index,
                    0,
                ),
                "S1C": (45.0, 0),
                "C2W": (22_000_010.0 + epoch_index + sat_index, 0),
                "L2W": (
                    89_000_000.0
                    + station_bias
                    + epoch_index * 0.015
                    + sat_index,
                    0,
                ),
                "S2W": (43.0, 0),
            }
            if blank and blank[:2] == (epoch_index, satellite):
                values[blank[2]] = (None, 0)
            if nonzero_lli and nonzero_lli[:2] == (
                epoch_index,
                satellite,
            ):
                value, _ = values[nonzero_lli[2]]
                values[nonzero_lli[2]] = (value, 1)
            lines.append(
                satellite
                + "".join(field(*values[item]) for item in observables)
                + "\n"
            )
    return bytearray("".join(lines).encode("ascii"))


def synthetic_curves() -> dict[str, np.ndarray]:
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
        "ORBITAL_G22": tail(10_000.0),
        "PREFIX_AFFINE": tail(0.0),
        "WRONG_ORBIT_G01": tail(-10_000.0),
        "WRONG_ORBIT_G14": tail(20_000.0),
        "WRONG_ORBIT_G17": tail(-20_000.0),
    }


@pytest.mark.parametrize(
    ("hypothesis", "outcome"),
    (
        ("ORBITAL_G22", "ORBITAL_MODEL_PREDICTIVELY_PREFERRED"),
        ("PREFIX_AFFINE", "PREFIX_AFFINE_NULL_PREFERRED"),
        ("WRONG_ORBIT_G01", "WRONG_ORBIT_G01_PREFERRED"),
    ),
)
def test_frozen_hypothesis_can_win_without_suffix_refit(
    hypothesis: str, outcome: str
) -> None:
    curves = synthetic_curves()
    elapsed = np.arange(frozen.FEATURE_EPOCHS) * frozen.STEP_S
    observed = curves[hypothesis] + 12.5 + 0.002 * elapsed
    result = primary.score_coordinate(observed, curves)

    assert result["outcome"] == outcome
    assert result["calibration_admission"]["state"] == "SATISFIED"
    assert (
        result["heldout_comparison"]["preference_margin_m"]
        > frozen.PRIMARY_PAIRWISE_DECISION_GUARD_M
    )


def test_ambiguous_when_two_models_are_inside_pairwise_guard() -> None:
    curves = synthetic_curves()
    observed = 0.5 * curves["ORBITAL_G22"]
    result = primary.score_coordinate(observed, curves)

    assert result["outcome"] == "AMBIGUOUS"
    assert result["heldout_comparison"]["preference_margin_m"] == pytest.approx(
        0.0
    )


def test_calibration_failure_blocks_heldout_comparison() -> None:
    curves = synthetic_curves()
    observed = curves["ORBITAL_G22"].copy()
    observed[: frozen.CALIBRATION_EPOCHS] += (
        np.arange(frozen.CALIBRATION_EPOCHS) % 2
    ) * 2_000.0
    result = primary.score_coordinate(observed, curves)

    assert result["outcome"] == "NOT_DETECTABLE"
    assert result["calibration_admission"]["state"] == "UNSATISFIED"
    assert result["heldout_comparison"] == "NOT_EVALUATED"


def test_linear_suffix_is_not_refit() -> None:
    curves = synthetic_curves()
    observed = curves["ORBITAL_G22"].copy()
    observed[frozen.CALIBRATION_EPOCHS :] += np.linspace(
        0.0, 5_000.0, frozen.HELDOUT_EPOCHS
    )
    result = primary.score_coordinate(observed, curves)
    orbital = next(
        row
        for row in result["heldout_comparison"]["scores"]
        if row["hypothesis"] == "ORBITAL_G22"
    )

    assert orbital["heldout_peak_to_peak_m"] == pytest.approx(5_000.0)


def test_primary_parser_and_health_use_only_frozen_window() -> None:
    scans = [
        primary.scan_decoded(fixture(locator), locator)
        for locator in primary.PRODUCTS
    ]
    try:
        coordinate, admission = primary.measurement_coordinate(scans)
        coordinate.fill(0.0)
    finally:
        for scan in scans:
            scan.erase()

    assert admission["core_phase_and_lli"] == "SATISFIED"
    assert admission["same_path_code_witness"]["state"] == "SATISFIED"
    assert admission["geometry_free_phase_health"]["state"] == "SATISFIED"
    assert admission["feature_epochs"] == 137
    assert all(np.count_nonzero(scan.phase_cycles) == 0 for scan in scans)


def test_nonzero_lli_is_measurement_invalid() -> None:
    payload = fixture(
        primary.PRODUCTS[0],
        nonzero_lli=(77, "G22", "L1C"),
    )
    with pytest.raises(
        primary.PrimaryMeasurementInvalid,
        match="NONZERO_OR_INVALID_LLI",
    ):
        primary.scan_decoded(payload, primary.PRODUCTS[0])


def test_unexpected_header_error_is_descriptive_not_measurement(
    monkeypatch,
) -> None:
    payload = fixture(primary.PRODUCTS[0])
    monkeypatch.setattr(
        primary.headers,
        "parse_header_lines",
        lambda _lines: (_ for _ in ()).throw(RuntimeError("software")),
    )
    with pytest.raises(
        primary.PrimaryDescriptionError,
        match="HEADER_DESCRIPTION_ERROR",
    ):
        primary.scan_decoded(payload, primary.PRODUCTS[0])


def test_code_witness_boundary_is_not_a_phase_value() -> None:
    scans = [
        primary.scan_decoded(
            fixture(
                locator,
                blank=(
                    (77, "G22", "C1C")
                    if locator.station == "GOLD00USA"
                    else None
                ),
            ),
            locator,
        )
        for locator in primary.PRODUCTS
    ]
    try:
        with pytest.raises(
            primary.PrimaryMeasurementInvalid,
            match="SAME_PATH_CODE_WITNESS_FAILED",
        ):
            primary.measurement_coordinate(scans)
    finally:
        for scan in scans:
            scan.erase()


def test_manifest_keeps_primary_sealed_and_retry_zero() -> None:
    manifest = primary.manifest()
    encoded = primary.strict_json(manifest)

    assert all("2026220" in row["name"] for row in manifest["products"])
    assert "2026217" not in encoded
    assert manifest["transport"]["attempts_per_locator"] == 1
    assert manifest["transport"]["retry_after_freeze"] is False
    assert not any(manifest["access_boundary"].values())
    assert manifest["scoring"]["free_time_phase"] is False
    assert manifest["scoring"]["suffix_refit"] is False


def test_qualification_closure_is_exact_and_primary_unopened() -> None:
    outcome = primary.validate_qualification_closure(ROOT)

    assert outcome["outcome"] == "GNSS_SHORT_WINDOW_QUALIFICATION_PASSED"
    assert all(value == 0 for value in outcome["primary_doy220_access"].values())


def test_materialization_hashes_once_before_decode(monkeypatch) -> None:
    payload = b"complete-primary-compressed-fixture"
    calls = 0

    class Response:
        def __init__(self):
            self.blocks = [payload, b""]

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self, _size):
            return self.blocks.pop(0)

    def open_once(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return Response()

    monkeypatch.setattr(primary, "urlopen", open_once)
    materialized, receipt = primary.materialize(primary.PRODUCTS[0])
    try:
        assert bytes(materialized) == payload
        assert receipt["attempts"] == 1
        assert receipt["complete_file_sha256"] == sha256(payload).hexdigest()
        assert receipt["hash_before_any_decode"] is True
        assert calls == 1
    finally:
        materialized[:] = b"\x00" * len(materialized)


def test_strict_json_and_invalid_prediction_values() -> None:
    with pytest.raises(ValueError):
        primary.strict_json({"bad": float("nan")})
    curves = synthetic_curves()
    curves["ORBITAL_G22"][4] = np.inf
    with pytest.raises(
        primary.PrimaryDescriptionError,
        match="FROZEN_HYPOTHESIS_CURVES_INVALID",
    ):
        primary.score_coordinate(np.zeros(137), curves)
    assert json.loads(primary.strict_json(primary.manifest())) == (
        primary.manifest()
    )


def test_cli_requires_explicit_live_authority() -> None:
    assert primary.AUTHORITY_TOKEN not in primary.manifest()["access_boundary"]
    assert primary.MAX_TRANSPORT_ATTEMPTS == 1
    assert (
        primary.manifest()["access_boundary"][
            "live_execution_authorized_by_manifest"
        ]
        is False
    )


def test_frozen_prediction_artifact_reproduces_geometry() -> None:
    path = ROOT / primary.PREDICTIONS_NAME
    assert primary.canonical_sha256(path) == (
        "1500fa3d6ddc5b3e1681631fca10df2f24a80bdfa5933f725e006cd07d7a81b3"
    )
    value = json.loads(path.read_text(encoding="utf-8"))
    curves = primary.validate_predictions(value)
    try:
        assert value["compiler_source_commit"] == (
            "548b7a28f3bc36904142ed2ceef259b121657429"
        )
        assert value["compiler_source_sha256"] == primary.source_sha256()
        assert value["curve_set_sha256"] == (
            "816e259786a70f47b1b6d8063e79a3a14bda3a0b630d3c161982e46c6957ddb6"
        )
        regression = value["numerical_regression"]
        assert regression[
            "prefix_affine_heldout_peak_to_peak_m"
        ] == pytest.approx(11401.473007275607, abs=1.0e-6)
        assert regression[
            "wrong_orbit_heldout_peak_to_peak_m"
        ] == pytest.approx(
            {
                "G01": 8857.431880665245,
                "G14": 60003.29156747623,
                "G17": 122006.60516244936,
            },
            abs=1.0e-6,
        )
        assert value["observation_access"] == {
            "products_discovered": 0,
            "headers": 0,
            "payload_bytes": 0,
            "values": 0,
        }
    finally:
        for curve in curves.values():
            curve.fill(0.0)


def test_frozen_seal_binds_code_plan_qualification_and_predictions() -> None:
    seal_path = ROOT / primary.SEAL_NAME
    predictions_path = ROOT / primary.PREDICTIONS_NAME
    seal_sha256 = (
        "58802ab8f4dfcc0a2050bcf6c37b4d3b751b97d02a8efc28127340f0b45df62b"
    )
    seal, curves = primary.validate_seal(
        seal_path, predictions_path, seal_sha256
    )
    try:
        assert seal["source_commit"] == (
            "548b7a28f3bc36904142ed2ceef259b121657429"
        )
        assert seal["source_sha256"] == (
            "bbacf8653a74198941a6380640d43b5e7ffc7d46767039e84604db0de61793fc"
        )
        assert seal["proof_plan_manifest_sha256"] == (
            "0068385ef4aaf1014f0211efaa47da52da8c5fb18cf51377f4812434fd2b5f3c"
        )
        assert seal["qualification_outcome_sha256"] == (
            primary.QUALIFICATION_OUTCOME_SHA256
        )
        assert all(
            product["bytes"] is None and product["sha256"] is None
            for product in seal["primary_products"]
        )
        assert all(value == 0 for value in seal["access_at_seal"].values())
        assert seal["authority"]["live_execution_authorized_by_seal"] is False
    finally:
        for curve in curves.values():
            curve.fill(0.0)


def test_single_frozen_primary_outcome_is_strict_and_value_free() -> None:
    path = ROOT / primary.OUTCOME_NAME
    raw = path.read_bytes()
    assert len(raw) == 9_799
    assert sha256(raw).hexdigest() == (
        "66adf39fa1b10cbf43bdb712ebf4d1f3d8f598203caaa8fa2a41601fea511f9d"
    )
    assert b"NaN" not in raw and b"Infinity" not in raw
    assert all(
        token not in raw
        for token in (
            b'"phase_cycles"',
            b'"observed_m"',
            b'"curves_m"',
            b'"value"',
        )
    )
    receipt = json.loads(raw)

    assert receipt["outcome"] == "ORBITAL_MODEL_PREDICTIVELY_PREFERRED"
    assert receipt["seal_sha256"] == (
        "58802ab8f4dfcc0a2050bcf6c37b4d3b751b97d02a8efc28127340f0b45df62b"
    )
    assert receipt["source_commit"] == (
        "548b7a28f3bc36904142ed2ceef259b121657429"
    )
    assert receipt["proof_plan_manifest_sha256"] == (
        "0068385ef4aaf1014f0211efaa47da52da8c5fb18cf51377f4812434fd2b5f3c"
    )
    assert [
        (
            row["station"],
            row["attempts"],
            row["complete_file_bytes"],
            row["complete_file_sha256"],
        )
        for row in receipt["artifacts"]
    ] == [
        (
            "GOLD00USA",
            1,
            2_182_238,
            "b1763eb485311c0fd3a073f7b9b0beda3c9af8f8f9f7be4c868a56fdeb5b7e3d",
        ),
        (
            "NLIB00USA",
            1,
            2_523_817,
            "48d80ce59776fa6b10024a8cf5456153f1c1fd9906d1a4acfc84053799d40b3f",
        ),
    ]
    assert all(
        row["hash_before_any_decode"] is True
        for row in receipt["artifacts"]
    )
    assert receipt["measurement_admission"][
        "core_phase_and_lli"
    ] == "SATISFIED"
    assert receipt["measurement_admission"][
        "same_path_code_witness"
    ]["state"] == "SATISFIED"
    assert all(
        row["coverage_fraction"] == 1.0
        for row in receipt["measurement_admission"][
            "same_path_code_witness"
        ]["links"]
    )
    health = receipt["measurement_admission"][
        "geometry_free_phase_health"
    ]
    assert health["state"] == "SATISFIED"
    assert max(
        row["maximum_absolute_second_difference_m"]
        for row in health["links"]
    ) == pytest.approx(0.008667878806591034)

    score = receipt["score"]
    assert score["calibration_admission"][
        "calibration_peak_to_peak_m"
    ] == pytest.approx(0.3672753512726934)
    assert score["calibration_admission"]["state"] == "SATISFIED"
    comparison = score["heldout_comparison"]
    assert comparison["best_hypothesis"] == "ORBITAL_G22"
    assert comparison["runner_up_hypothesis"] == "WRONG_ORBIT_G01"
    assert comparison["preference_margin_m"] == pytest.approx(
        8856.65168424408
    )
    scores = {
        row["hypothesis"]: row for row in comparison["scores"]
    }
    assert scores["ORBITAL_G22"][
        "heldout_peak_to_peak_m"
    ] == pytest.approx(2.312586041483124)
    assert scores["WRONG_ORBIT_G01"][
        "heldout_peak_to_peak_m"
    ] == pytest.approx(8858.964270285564)
    assert (
        comparison["preference_margin_m"]
        > comparison["preference_guard_m"]
    )
    assert receipt["retry"] == {
        "post_freeze_attempts_per_locator": 1,
        "substitution": False,
    }
    assert receipt["persistence"]["observation_values"] == 0
    assert receipt["observation_access"][
        "phase_code_or_snr_values_persisted"
    ] == 0
    assert receipt["claim_scope"] == (
        "HELDOUT_ORBITAL_MODEL_PREFERENCE_BELOW_SATELLITE_IDENTITY"
    )
