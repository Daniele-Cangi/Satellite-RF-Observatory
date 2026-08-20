"""Offline integrity tests for the scoped RSP-03 prospective plan."""

from dataclasses import FrozenInstanceError
from datetime import datetime

import pytest

from experiments.orbital_discriminability.rsp03_forward_plan import (
    ArtifactOutcome,
    DEVELOPMENT_READY,
    DOPPLER_CORRECTION_CLASSIFICATION,
    DevelopmentAuthority,
    PER_FILE_EXPLICIT_DOPPLER_FLAG,
    PLAN,
    PLAN_FROZEN,
    PRIMARY_BLOCKED,
    classify_artifact_outcome,
    development_authority_errors,
    lifecycle_states,
    materialization_retry_allowed,
    primary_analysis_blockers,
    structural_errors,
)
from experiments.live_instrument.orbital_kernel import (
    Observer,
    TLEElements,
    compute_orbital_state,
)


def test_dataset_roles_and_primary_split_are_frozen() -> None:
    assert PLAN.primary.role == "PRIMARY_HELD_OUT"
    assert PLAN.development_fixture.role == "DEVELOPMENT_FIXTURE"
    assert PLAN.sealed_replication_reserve.role == "SEALED_REPLICATION_RESERVE"
    assert PLAN.primary_sample_count == 467_360_000
    assert PLAN.calibration_stop_sample_exclusive == 93_472_000
    assert PLAN.holdout_start_sample == 93_472_000
    assert PLAN.holdout_stop_sample_exclusive == 467_360_000
    assert PLAN.holdout_start_utc == "2026-02-09T07:07:24.182039Z"
    assert PLAN.recording_end_utc_exclusive == "2026-02-09T07:13:38.070039Z"


def test_plan_is_immutable_and_structurally_valid() -> None:
    assert structural_errors() == ()
    with pytest.raises(FrozenInstanceError):
        PLAN.nominal_carrier_hz = 437_050_001  # type: ignore[misc]


def test_primary_remains_blocked_without_inventing_timing_or_detector_values() -> None:
    assert lifecycle_states() == (PLAN_FROZEN, PRIMARY_BLOCKED)
    assert primary_analysis_blockers() == (
        "NO_DEFENSIBLE_FINITE_PPS_TO_ADC_UTC_ERROR_BOUND",
        "DEVELOPMENT_FIXTURE_DETECTOR_MANIFEST_NOT_FROZEN",
    )
    assert PLAN.absolute_time_error_bound_s is None
    assert PLAN.detector_manifest_sha256 is None


def test_development_authority_does_not_unblock_primary() -> None:
    authority = DevelopmentAuthority(
        source_commit="f7d3aa522976b8a428915212816006fd2e1e65f5",
        structural_plan_hash=PLAN.plan_hash,
        prospective_markdown_sha256=(
            "a8371ca061a5b4ed89f2114d7cbce3590439d32dad451fb5a0793d1646d7b8f3"
        ),
    )
    assert development_authority_errors(authority) == ()
    assert lifecycle_states(authority) == (
        PLAN_FROZEN,
        DEVELOPMENT_READY,
        PRIMARY_BLOCKED,
    )


def test_materialization_retry_precedes_hash_and_measurement_semantics() -> None:
    assert materialization_retry_allowed(
        complete_file_sha256=None,
        decoding_started=False,
    )
    assert classify_artifact_outcome(
        complete_file_sha256=None,
        decoding_started=False,
        measurement_valid=None,
    ) is ArtifactOutcome.ARTIFACT_MATERIALIZATION_FAILED
    digest = "a" * 64
    assert not materialization_retry_allowed(
        complete_file_sha256=digest,
        decoding_started=False,
    )
    assert classify_artifact_outcome(
        complete_file_sha256=digest,
        decoding_started=False,
        measurement_valid=None,
    ) is ArtifactOutcome.ARTIFACT_READY_FOR_DECODING
    assert classify_artifact_outcome(
        complete_file_sha256=digest,
        decoding_started=True,
        measurement_valid=False,
    ) is ArtifactOutcome.MEASUREMENT_INVALID


def test_frozen_pass_geometry_numerical_regression() -> None:
    observer = Observer(*PLAN.observer)
    tle = TLEElements(
        PLAN.historical_tle_lines[1],
        PLAN.historical_tle_lines[2],
        PLAN.historical_tle_lines[0],
    )
    split_state = compute_orbital_state(
        observer,
        tle,
        datetime.fromisoformat(
            PLAN.holdout_start_utc.replace("Z", "+00:00")
        ),
        PLAN.nominal_carrier_hz,
    )
    assert split_state.elevation_deg == pytest.approx(9.720070653355425, abs=1e-9)
    assert split_state.range_rate_km_s == pytest.approx(-6.1352350465965895, abs=1e-12)
    assert split_state.doppler_shift_hz == pytest.approx(8_944.202582691521, abs=1e-9)


def test_provenance_classifications_are_exact() -> None:
    assert PLAN.doppler_correction_classification == (
        DOPPLER_CORRECTION_CLASSIFICATION
    )
    assert DOPPLER_CORRECTION_CLASSIFICATION == (
        "PRE_CORRECTION_PATH_SUPPORTED_BY_OPERATOR_DOCUMENTATION"
    )
    assert PLAN.per_file_explicit_doppler_flag == PER_FILE_EXPLICIT_DOPPLER_FLAG
    assert PER_FILE_EXPLICIT_DOPPLER_FLAG == "ABSENT"
    assert PLAN.historical_tle_canonical_sha256 == (
        "1df5f80a1d84d7926e6545e799088db1574a57a65ed42bd37d1990804f9eecd5"
    )
    assert PLAN.sensitivity_tle_canonical_sha256 == (
        "d93d67c004111cb8e81ac2d7f4146e04e6c06d666a00a44df9f76c0db23b38a2"
    )
    assert PLAN.sensitivity_source_observation_id == 13_352_524


def test_nulls_and_nuisance_surface_do_not_expand() -> None:
    assert tuple((item.name, item.parameter_count) for item in PLAN.null_families) == (
        ("N0_CONSTANT", 1),
        ("N1_AFFINE", 2),
        ("N2_QUADRATIC", 3),
        ("N3_BOUNDED_CUBIC", 4),
    )
    assert PLAN.orbital_nuisance_parameters == (
        "constant_frequency_offset_hz",
        "affine_frequency_drift_hz_per_s",
        "one_constant_absolute_time_offset_s",
    )


def test_plan_hash_is_stable() -> None:
    assert PLAN.plan_hash == (
        "add5c2a3d5121d86978bc5d76ee07d1cc7484f9f533f4f1e04bdda0c8bd79dca"
    )
