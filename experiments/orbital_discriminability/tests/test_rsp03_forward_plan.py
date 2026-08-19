"""Offline integrity tests for the scoped RSP-03 prospective plan."""

from dataclasses import FrozenInstanceError

import pytest

from experiments.orbital_discriminability.rsp03_forward_plan import (
    DOPPLER_CORRECTION_CLASSIFICATION,
    PER_FILE_EXPLICIT_DOPPLER_FLAG,
    PLAN,
    PLAN_STATUS,
    primary_analysis_blockers,
    structural_errors,
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
    assert PLAN_STATUS == "PROSPECTIVE_PLAN_BLOCKED"
    assert primary_analysis_blockers() == (
        "NO_DEFENSIBLE_FINITE_PPS_TO_ADC_UTC_ERROR_BOUND",
        "DEVELOPMENT_FIXTURE_DETECTOR_MANIFEST_NOT_FROZEN",
    )
    assert PLAN.absolute_time_error_bound_s is None
    assert PLAN.detector_manifest_sha256 is None


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
