from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import inspect
import json
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import gnss_native_doppler_primary as primary


ROOT = Path(__file__).parents[1]
SEAL = ROOT / "GNSS_NATIVE_DOPPLER_PRIMARY_EVALUATOR_SEAL.json"
AUTHORITY = ROOT / "GNSS_NATIVE_DOPPLER_PRIMARY_AUTHORITY.json"
OUTCOME = ROOT / "GNSS_NATIVE_DOPPLER_PRIMARY_OUTCOME.jsonl"
OUTCOME_SHA256 = "e2c15a9939ac3fcef9fd28d0f46d5906bde629cb852197cf062876c15135d5c7"


def header_line(data: str, label: str) -> str:
    return f"{data:<60}{label:<20}\n"


def field(value: float | None) -> str:
    return " " * 16 if value is None else f"{value:14.3f}  "


def short_epochs(count: int = 5) -> tuple[datetime, ...]:
    start = datetime(2026, 8, 7, 16, 20, tzinfo=timezone.utc)
    return tuple(start + timedelta(seconds=30 * index) for index in range(count))


def fixture(grid: tuple[datetime, ...], *, station: str = "KIRU00SWE", missing: bool = False) -> bytearray:
    lines = [
        header_line("     3.04           OBSERVATION DATA    M", "RINEX VERSION / TYPE"),
        header_line(station, "MARKER NAME"),
        header_line(f"{primary.STEP_S:10.3f}", "INTERVAL"),
        header_line(" " * 48 + "GPS", "TIME OF FIRST OBS"),
        header_line(f"G  {len(primary.OBSERVABLES):3d} " + "".join(f"{item:>3} " for item in primary.OBSERVABLES), "SYS / # / OBS TYPES"),
        header_line("", "END OF HEADER"),
    ]
    for index, epoch in enumerate(grid):
        lines.append(f"> {epoch.year:4d} {epoch.month:02d} {epoch.day:02d} {epoch.hour:02d} {epoch.minute:02d} {epoch.second:10.7f}  0  2\n")
        for sat_index, satellite in enumerate(primary.SATELLITES):
            values = (22_000_000.0 + index, None if missing and index == 2 and sat_index == 0 else 1000.0 + index, 45.0, 22_000_010.0 + index, 800.0 + sat_index, 43.0)
            lines.append(satellite + "".join(field(value) for value in values) + "\n")
    return bytearray("".join(lines).encode("ascii"))


def station(station_id: str, *, drop_snr: bool = False, dispersive: float = 0.0) -> primary.StationRun:
    values = np.ones((primary.RECORDS, 2, len(primary.OBSERVABLES)), dtype=np.float64)
    values[:, :, primary.OBSERVABLES.index("C1C")] = 22_000_000.0
    values[:, :, primary.OBSERVABLES.index("C2W")] = 22_000_010.0
    values[:, :, primary.OBSERVABLES.index("S1C")] = 45.0
    values[:, :, primary.OBSERVABLES.index("S2W")] = 43.0
    values[:, :, primary.OBSERVABLES.index("D1C")] = 1000.0
    ratio = primary.envelope.GPS_L1_HZ / primary.envelope.GPS_L2_HZ
    values[:, :, primary.OBSERVABLES.index("D2W")] = 1000.0 / ratio
    if drop_snr:
        values[primary.CALIBRATION_RECORDS :, 0, primary.OBSERVABLES.index("S1C")] = 44.0
    if dispersive:
        values[primary.CALIBRATION_RECORDS :, 0, primary.OBSERVABLES.index("D1C")] += np.linspace(0.0, dispersive, primary.HELDOUT_RECORDS)
    return primary.StationRun(station_id, primary.frozen_epoch_grid(), values)


def health() -> dict[str, object]:
    return {"prefix_dispersive_clause": "SATISFIED", "heldout_dispersive_clause": "SATISFIED", "same_link_snr_non_degradation_clause": "SATISFIED"}


def orbital_curve(peak: float = 5000.0) -> np.ndarray:
    curve = np.zeros(primary.RECORDS)
    phase = np.linspace(0.0, 1.0, primary.HELDOUT_RECORDS)
    curve[primary.CALIBRATION_RECORDS :] = peak * phase**1.05
    return curve


def write_json(path: Path, value: dict[str, object]) -> str:
    payload = primary.strict_json(value) + "\n"
    path.write_text(payload, encoding="ascii", newline="\n")
    return sha256(payload.encode("ascii")).hexdigest()


def seal_document() -> dict[str, object]:
    return {"schema": "gnss-native-doppler-primary-evaluator-seal-v1", "source_commit": "a" * 40, "plan_sha256": primary.PLAN_SHA256, "evaluator_source_sha256": primary.file_sha256(Path(primary.__file__)), "runtime_manifest_sha256": primary.runtime_manifest_sha256()}


def authority_document(seal: dict[str, object], seal_sha: str) -> dict[str, object]:
    return {"schema": "gnss-native-doppler-primary-access-authority-v1", "state": "PRIMARY_ACCESS_AUTHORIZED", "plan_sha256": primary.PLAN_SHA256, "prospective_markdown_sha256": primary.PLAN_SHA256, "evaluator_seal_sha256": seal_sha, "evaluator_source_sha256": seal["evaluator_source_sha256"], "source_commit": seal["source_commit"], "single_run": True, "products": [item["name"] for item in primary.PRIMARY_PRODUCTS]}


def test_frozen_numerical_regressions_and_parent_receipt() -> None:
    grid = primary.frozen_epoch_grid()
    assert len(grid) == 380 and grid[0] == primary.START_GPS and grid[-1] == primary.STOP_GPS
    assert primary.CALIBRATION_RECORDS + primary.HELDOUT_RECORDS == primary.RECORDS
    assert primary.GEOMETRY_MARGIN_AFTER_CLOCK_HZ == pytest.approx(6743.536574359732, abs=1e-12)
    assert primary.PAIRWISE_DECISION_GUARD_HZ == pytest.approx(2326.8486747825173, abs=1e-12)
    path = ROOT / primary.MODEL_BOUND_RECEIPT_NAME
    assert primary.file_sha256(path) == primary.MODEL_BOUND_RECEIPT_SHA256
    receipt = json.loads(path.read_text(encoding="ascii"))
    row = next(item for item in receipt["candidate_audits"] if item["doy"] == 219)
    assert receipt["outcome"] == "NATIVE_DOPPLER_BROADCAST_MODEL_BOUND_ADMITTED"
    assert row["broadcast_model_interval"]["per_link_path_bound_m"] == pytest.approx(10.608)
    assert row["pairwise_guard_hz"] == pytest.approx(primary.PAIRWISE_DECISION_GUARD_HZ)


def test_model_blind_parser_and_measurement_refusals() -> None:
    grid = short_epochs()
    parsed = primary.parse_plain_rinex_primary(fixture(grid), "KIRU00SWE", grid)
    try:
        assert parsed.values.shape == (5, 2, 6)
        signature = inspect.signature(primary.parse_plain_rinex_primary)
        assert "navigation" not in signature.parameters and "model" not in signature.parameters
    finally:
        parsed.erase()
    assert np.all(parsed.values == 0.0)
    with pytest.raises(primary.MeasurementInvalid, match="MISSING_OR_NONFINITE"):
        primary.parse_plain_rinex_primary(fixture(grid, missing=True), "KIRU00SWE", grid)
    with pytest.raises(primary.MeasurementInvalid, match="STATION_MARKER"):
        primary.parse_plain_rinex_primary(fixture(grid, station="WRONG"), "KIRU00SWE", grid)


def test_coordinate_order_and_health_clauses() -> None:
    left = station("KIRU00SWE", drop_snr=True, dispersive=1.0)
    right = station("MAT100ITA")
    coordinate = np.zeros(primary.RECORDS)
    try:
        result = primary.same_path_health(left, right)
        assert result["prefix_dispersive_clause"] == "SATISFIED"
        assert result["heldout_dispersive_clause"] == "UNSATISFIED"
        assert result["same_link_snr_non_degradation_clause"] == "UNSATISFIED"
        left.values[:, 0, primary.OBSERVABLES.index("D1C")] += 10.0
        left.values[:, 1, primary.OBSERVABLES.index("D1C")] += 3.0
        right.values[:, 0, primary.OBSERVABLES.index("D1C")] += 4.0
        right.values[:, 1, primary.OBSERVABLES.index("D1C")] += 2.0
        coordinate = primary.observed_coordinate(left, right)
        alpha, _ = primary.envelope.ionosphere_free_coefficients()
        assert np.ptp(coordinate - alpha * 5.0) > 0.0  # injected witness drift remains visible
    finally:
        left.erase(); right.erase(); coordinate.fill(0.0)


@pytest.mark.parametrize(("winner", "expected"), (("H_ORBITAL", "ORBITAL_MODEL_PREDICTIVELY_PREFERRED"), ("H_AFFINE", "PREFIX_AFFINE_NULL_PREFERRED")))
def test_each_frozen_hypothesis_can_win(winner: str, expected: str) -> None:
    orbital = orbital_curve()
    elapsed = np.arange(primary.RECORDS) * primary.STEP_S
    observed = (orbital if winner == "H_ORBITAL" else np.zeros_like(orbital)) + 12.0 - 0.001 * elapsed
    outcome, scores, margins, detectability = primary.evaluate_observed(observed, orbital, health())
    assert outcome == expected and scores[winner]["heldout_peak_to_peak_hz"] < 1e-8
    assert margins[winner] > primary.PAIRWISE_DECISION_GUARD_HZ
    assert detectability["clause"] == "SATISFIED"


def test_suffix_cannot_refit_prefix_and_guard_equality_is_ambiguous() -> None:
    orbital = orbital_curve(primary.PAIRWISE_DECISION_GUARD_HZ)
    observed = orbital + 7.0 + 0.002 * np.arange(primary.RECORDS) * primary.STEP_S
    first = primary.prefix_calibration(observed, orbital)
    observed[primary.CALIBRATION_RECORDS :] += 100_000.0
    second = primary.prefix_calibration(observed, orbital)
    try:
        assert np.array_equal(first["coefficients"], second["coefficients"])
    finally:
        first["coefficients"].fill(0.0); second["coefficients"].fill(0.0)
    outcome, _, margins, _ = primary.evaluate_observed(np.zeros(primary.RECORDS), orbital, health())
    assert margins["H_AFFINE"] == pytest.approx(primary.PAIRWISE_DECISION_GUARD_HZ)
    assert outcome == "AMBIGUOUS"


def test_health_and_prefix_failure_block_scoring(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError("heldout scorer called")
    monkeypatch.setattr(primary, "score_hypothesis", forbidden)
    bad_health = health(); bad_health["heldout_dispersive_clause"] = "UNSATISFIED"
    outcome, scores, margins, _ = primary.evaluate_observed(np.zeros(primary.RECORDS), np.zeros(primary.RECORDS), bad_health)
    assert outcome == "NOT_DETECTABLE" and scores == {} and margins == {}
    observed = np.zeros(primary.RECORDS)
    observed[: primary.CALIBRATION_RECORDS] = (np.arange(primary.CALIBRATION_RECORDS) % 2) * 10.0
    outcome, scores, margins, _ = primary.evaluate_observed(observed, np.zeros_like(observed), health())
    assert outcome == "NOT_DETECTABLE" and scores == {} and margins == {}


def test_manifest_json_and_claim_scope_are_strict() -> None:
    manifest = primary.runtime_manifest()
    assert manifest["model_blind_extractor"] is True and manifest["network_surface"] is False
    assert manifest["access_authorized"] is False and manifest["claim_ceiling"] == "ORBITAL_MODEL_PREDICTIVELY_PREFERRED"
    primary.strict_json(manifest)
    for value in (float("nan"), float("inf")):
        with pytest.raises(ValueError): primary.strict_json({"bad": value})
    for value in (np.bool_(True), np.float64(1.0)):
        with pytest.raises(TypeError): primary.strict_json({"bad": value})


def test_repository_seal_binds_committed_source_and_opens_zero_observation_bytes() -> None:
    seal, seal_sha = primary.verify_seal(SEAL, Path(primary.__file__))
    assert seal["source_commit"] == "2d694fea4f42bd10238096c1c717b130474b36d1"
    assert seal["primary_state"] == "PRIMARY_BLOCKED"
    assert seal["access_authority_created"] is False
    assert seal["observation_access"] == {
        "headers_opened": 0,
        "numeric_values_decoded": 0,
        "products_opened": 0,
        "total_bytes_opened": 0,
    }
    assert seal_sha == primary.file_sha256(SEAL)


def test_repository_authority_is_one_use_and_bound_to_seal() -> None:
    seal, seal_sha = primary.verify_seal(SEAL, Path(primary.__file__))
    authority, authority_sha = primary.verify_authority(AUTHORITY, seal, seal_sha)
    assert authority["single_run"] is True
    assert authority["products"] == [item["name"] for item in primary.PRIMARY_PRODUCTS]
    assert authority_sha == primary.file_sha256(AUTHORITY)


def test_seal_and_authority_bind_plan_source_and_single_run(tmp_path: Path) -> None:
    seal = seal_document(); seal_path = tmp_path / "seal.json"; seal_sha = write_json(seal_path, seal)
    loaded, actual = primary.verify_seal(seal_path, Path(primary.__file__))
    assert loaded == seal and actual == seal_sha
    authority = authority_document(seal, seal_sha); authority_path = tmp_path / "authority.json"
    authority_sha = write_json(authority_path, authority)
    loaded_authority, actual_authority = primary.verify_authority(authority_path, loaded, seal_sha)
    assert loaded_authority == authority and actual_authority == authority_sha
    authority["single_run"] = False; write_json(authority_path, authority)
    with pytest.raises(primary.PrimaryEvaluationError, match="AUTHORITY_BINDING_CHANGED:single_run"):
        primary.verify_authority(authority_path, loaded, seal_sha)


def test_materialization_failure_precedes_decode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seal = seal_document(); seal_path = tmp_path / "seal.json"; seal_sha = write_json(seal_path, seal)
    authority_path = tmp_path / "authority.json"; authority_sha = write_json(authority_path, authority_document(seal, seal_sha))
    materialization = {"schema": "gnss-native-doppler-primary-materialization-v1", "state": "PRIMARY_ARTIFACTS_MATERIALIZED", "plan_sha256": primary.PLAN_SHA256, "evaluator_seal_sha256": seal_sha, "authority_receipt_sha256": authority_sha, "hashes_completed_before_decompression": True, "artifacts": [{"station_id": item["station_id"], "name": item["name"], "bytes": 1, "sha256": "0" * 64} for item in primary.PRIMARY_PRODUCTS]}
    materialization_path = tmp_path / "materialization.json"; write_json(materialization_path, materialization)
    def forbidden(*args: object, **kwargs: object) -> object: raise AssertionError("decode/compiler called")
    monkeypatch.setattr(primary, "decode_exact_station", forbidden); monkeypatch.setattr(primary, "compile_model", forbidden)
    output = tmp_path / "result.jsonl"
    receipt = primary.run_once(tmp_path / str(primary.PRIMARY_PRODUCTS[0]["name"]), tmp_path / str(primary.PRIMARY_PRODUCTS[1]["name"]), tmp_path / primary.NAVIGATION_PRODUCT.compressed_name, seal_path, authority_path, materialization_path, output)
    assert receipt["outcome"] == "ARTIFACT_MATERIALIZATION_FAILED" and receipt["physical_decision"] == "NOT_EVALUATED"
    assert receipt["decompression_started"] is False
    assert receipt["clauses"]["heldout_model_comparison"] == "NOT_EVALUATED"
    assert output.read_text(encoding="ascii").count("\n") == 1


def test_nonphysical_error_never_changes_physical_decision() -> None:
    receipt = primary.nonphysical_error_receipt("DESCRIPTION_ERROR", "a" * 64, "b" * 64, True)
    assert receipt["outcome"] == "PRIMARY_EVALUATION_ERROR" and receipt["physical_decision"] == "NOT_EVALUATED"
    assert set(receipt["clauses"].values()) == {"NOT_EVALUATED"}


def test_frozen_primary_outcome_is_scalar_not_detectable_and_unscored() -> None:
    assert primary.file_sha256(OUTCOME) == OUTCOME_SHA256
    raw = OUTCOME.read_bytes()
    assert raw.count(b"\n") == 1
    receipt = json.loads(raw.decode("ascii"), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    assert receipt["outcome"] == "NOT_DETECTABLE"
    assert receipt["scores"] == {}
    assert receipt["preference_margins_hz"] == {}
    assert receipt["clauses"]["measurement_admission"] == "SATISFIED"
    assert receipt["clauses"]["heldout_model_comparison"] == "NOT_EVALUATED"
    assert receipt["detectability"]["nominal_prefix_peak_to_peak_hz"] < receipt["detectability"]["nominal_prefix_limit_hz"]
    assert receipt["detectability"]["prefix_dispersive_clause"] == "SATISFIED"
    assert receipt["detectability"]["heldout_dispersive_clause"] == "SATISFIED"
    assert receipt["detectability"]["same_link_snr_non_degradation_clause"] == "UNSATISFIED"
    assert receipt["claims"]["authorized"] == "MEASUREMENT_PATH_OUTCOME_ONLY"
    assert receipt["raw_or_derived_measurement_persisted"] is False
    assert "measurement_series" not in receipt and "observed_coordinate" not in receipt
