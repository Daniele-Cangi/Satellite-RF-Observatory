"""Frozen interface invariants for the RSP-03 historical forward experiment.

This module is deliberately scoped to one experiment.  It does not download,
decode, or inspect IQ, and it is not a generic dataset or detector adapter.
The accompanying prospective plan is the scientific authority.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from math import isfinite


DOPPLER_CORRECTION_CLASSIFICATION = (
    "PRE_CORRECTION_PATH_SUPPORTED_BY_OPERATOR_DOCUMENTATION"
)
PER_FILE_EXPLICIT_DOPPLER_FLAG = "ABSENT"
PLAN_STATUS = "PROSPECTIVE_PLAN_BLOCKED"


@dataclass(frozen=True, slots=True)
class RecordingRole:
    role: str
    metadata_url: str
    data_url: str
    sample_zero_utc: str
    iq_access_policy: str
    expected_bytes: int | None = None
    metadata_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class NullFamily:
    name: str
    shape: str
    parameter_count: int


@dataclass(frozen=True, slots=True)
class RSP03ForwardPlan:
    experiment_id: str
    norad_id: int
    observer: tuple[float, float, float]
    nominal_carrier_hz: int
    sample_rate_hz: int
    datatype: str
    bytes_per_complex_sample: int
    primary: RecordingRole
    development_fixture: RecordingRole
    sealed_replication_reserve: RecordingRole
    primary_sample_count: int
    calibration_start_sample: int
    calibration_stop_sample_exclusive: int
    holdout_start_sample: int
    holdout_stop_sample_exclusive: int
    calibration_start_utc: str
    holdout_start_utc: str
    recording_end_utc_exclusive: str
    orbital_nuisance_parameters: tuple[str, ...]
    absolute_time_error_bound_s: float | None
    null_families: tuple[NullFamily, ...]
    historical_tle_lines: tuple[str, str, str]
    historical_tle_canonical_sha256: str
    satnogs_observation_id: int
    satnogs_observation_response_sha256: str
    sensitivity_tle_lines: tuple[str, str, str]
    sensitivity_tle_canonical_sha256: str
    sensitivity_source_observation_id: int
    sensitivity_source_response_sha256: str
    detector_manifest_sha256: str | None
    doppler_correction_classification: str
    per_file_explicit_doppler_flag: str

    @property
    def plan_hash(self) -> str:
        encoded = json.dumps(
            asdict(self),
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return sha256(encoded).hexdigest()


PRIMARY = RecordingRole(
    role="PRIMARY_HELD_OUT",
    metadata_url=(
        "https://data.camras.nl/satellites/raw/"
        "rsp03_2026_02_09_07_05_50_436.950MHz_1.00Msps_ci16_le.chan1.sigmf-meta"
    ),
    data_url=(
        "https://data.camras.nl/satellites/raw/"
        "rsp03_2026_02_09_07_05_50_436.950MHz_1.00Msps_ci16_le.chan1.sigmf-data"
    ),
    sample_zero_utc="2026-02-09T07:05:50.710039Z",
    iq_access_policy="SEALED_UNTIL_PLAN_AND_DETECTOR_FREEZE",
    expected_bytes=1_869_440_000,
    metadata_sha256="0826fd8e6447d25a002697609e520ef152dc57a0cb787607aedbf99f9aa9d48c",
)

DEVELOPMENT_FIXTURE = RecordingRole(
    role="DEVELOPMENT_FIXTURE",
    metadata_url=(
        "https://data.camras.nl/satellites/raw/"
        "rsp03_2026_02_08_11_48_41_436.950MHz_1.00Msps_ci16_le.chan1.sigmf-meta"
    ),
    data_url=(
        "https://data.camras.nl/satellites/raw/"
        "rsp03_2026_02_08_11_48_41_436.950MHz_1.00Msps_ci16_le.chan1.sigmf-data"
    ),
    sample_zero_utc="2026-02-08T11:48:41.560039Z",
    iq_access_policy="DEVELOPMENT_ONLY_AFTER_SEPARATE_AUTHORIZATION",
)

SEALED_REPLICATION_RESERVE = RecordingRole(
    role="SEALED_REPLICATION_RESERVE",
    metadata_url=(
        "https://data.camras.nl/satellites/raw/"
        "rsp03_2026_02_13_09_39_30_436.950MHz_1.00Msps_ci16_le.chan1.sigmf-meta"
    ),
    data_url=(
        "https://data.camras.nl/satellites/raw/"
        "rsp03_2026_02_13_09_39_30_436.950MHz_1.00Msps_ci16_le.chan1.sigmf-data"
    ),
    sample_zero_utc="2026-02-13T09:39:30.000039Z",
    iq_access_policy="SEALED_REPLICATION_ONLY",
)

HISTORICAL_TLE_LINES = (
    "0 OBJECT XL",
    "1 65732U 98067XL  26039.66236070  .00844645  35986-3  13863-2 0  9991",
    "2 65732  51.6148 196.1853 0007277 299.9440  60.0848 16.02581073 22321",
)

SENSITIVITY_TLE_LINES = (
    "0 OBJECT XL",
    "1 65732U 98067XL  26037.72735522  .00753541  26934-3  14853-2 0  9999",
    "2 65732  51.6170 206.5302 0006539 284.0297  75.9985 15.99425235 22011",
)

NULL_FAMILIES = (
    NullFamily("N0_CONSTANT", "constant carrier", 1),
    NullFamily("N1_AFFINE", "constant plus linear drift", 2),
    NullFamily("N2_QUADRATIC", "quadratic polynomial", 3),
    NullFamily(
        "N3_BOUNDED_CUBIC",
        "cubic polynomial constrained to remain inside the recorded RF band",
        4,
    ),
)

PLAN = RSP03ForwardPlan(
    experiment_id="RSP03-65732-20260209-PI9RD-SINGLE-STATION-FORWARD-V1",
    norad_id=65_732,
    observer=(52.812, 6.396, 10.0),
    nominal_carrier_hz=437_050_000,
    sample_rate_hz=1_000_000,
    datatype="ci16_le",
    bytes_per_complex_sample=4,
    primary=PRIMARY,
    development_fixture=DEVELOPMENT_FIXTURE,
    sealed_replication_reserve=SEALED_REPLICATION_RESERVE,
    primary_sample_count=467_360_000,
    calibration_start_sample=0,
    calibration_stop_sample_exclusive=93_472_000,
    holdout_start_sample=93_472_000,
    holdout_stop_sample_exclusive=467_360_000,
    calibration_start_utc="2026-02-09T07:05:50.710039Z",
    holdout_start_utc="2026-02-09T07:07:24.182039Z",
    recording_end_utc_exclusive="2026-02-09T07:13:38.070039Z",
    orbital_nuisance_parameters=(
        "constant_frequency_offset_hz",
        "affine_frequency_drift_hz_per_s",
        "one_constant_absolute_time_offset_s",
    ),
    absolute_time_error_bound_s=None,
    null_families=NULL_FAMILIES,
    historical_tle_lines=HISTORICAL_TLE_LINES,
    historical_tle_canonical_sha256=(
        "1df5f80a1d84d7926e6545e799088db1574a57a65ed42bd37d1990804f9eecd5"
    ),
    satnogs_observation_id=13_364_515,
    satnogs_observation_response_sha256=(
        "64c1949a3c3e62c619d900854b73ec77a0d042f5a1e6f49dcaa5d86c9a3c4018"
    ),
    sensitivity_tle_lines=SENSITIVITY_TLE_LINES,
    sensitivity_tle_canonical_sha256=(
        "d93d67c004111cb8e81ac2d7f4146e04e6c06d666a00a44df9f76c0db23b38a2"
    ),
    sensitivity_source_observation_id=13_352_524,
    sensitivity_source_response_sha256=(
        "62bc86f16edf0b12ea88d8ba1a025f83a40c4b5db89099a23b93775ad245c071"
    ),
    detector_manifest_sha256=None,
    doppler_correction_classification=DOPPLER_CORRECTION_CLASSIFICATION,
    per_file_explicit_doppler_flag=PER_FILE_EXPLICIT_DOPPLER_FLAG,
)


def structural_errors(plan: RSP03ForwardPlan = PLAN) -> tuple[str, ...]:
    """Return plan-integrity errors without treating blockers as invalid data."""

    errors: list[str] = []
    roles = (
        plan.primary.role,
        plan.development_fixture.role,
        plan.sealed_replication_reserve.role,
    )
    if len(set(roles)) != 3:
        errors.append("dataset roles are not unique")
    if plan.primary.expected_bytes != (
        plan.primary_sample_count * plan.bytes_per_complex_sample
    ):
        errors.append("primary byte count does not match datatype and sample count")
    if plan.calibration_stop_sample_exclusive != plan.primary_sample_count // 5:
        errors.append("calibration prefix is not exactly 20 percent")
    if plan.holdout_start_sample != plan.calibration_stop_sample_exclusive:
        errors.append("calibration and holdout are not contiguous")
    if plan.holdout_stop_sample_exclusive != plan.primary_sample_count:
        errors.append("holdout does not end at the recording boundary")
    if tuple(item.parameter_count for item in plan.null_families) != (1, 2, 3, 4):
        errors.append("null complexity declaration changed")
    if plan.orbital_nuisance_parameters != (
        "constant_frequency_offset_hz",
        "affine_frequency_drift_hz_per_s",
        "one_constant_absolute_time_offset_s",
    ):
        errors.append("orbital nuisance surface changed")
    canonical_tle = ("\n".join(plan.historical_tle_lines) + "\n").encode("ascii")
    if sha256(canonical_tle).hexdigest() != plan.historical_tle_canonical_sha256:
        errors.append("historical TLE hash does not match its canonical content")
    sensitivity_tle = ("\n".join(plan.sensitivity_tle_lines) + "\n").encode("ascii")
    if sha256(sensitivity_tle).hexdigest() != plan.sensitivity_tle_canonical_sha256:
        errors.append("sensitivity TLE hash does not match its canonical content")
    bound = plan.absolute_time_error_bound_s
    if bound is not None and (not isfinite(bound) or bound < 0.0):
        errors.append("absolute timing bound must be finite and non-negative")
    if plan.doppler_correction_classification != DOPPLER_CORRECTION_CLASSIFICATION:
        errors.append("Doppler-correction provenance was reclassified")
    if plan.per_file_explicit_doppler_flag != PER_FILE_EXPLICIT_DOPPLER_FLAG:
        errors.append("per-file Doppler flag classification changed")
    return tuple(errors)


def primary_analysis_blockers(plan: RSP03ForwardPlan = PLAN) -> tuple[str, ...]:
    """Return pre-primary blockers; this function never accesses a recording."""

    blockers = list(structural_errors(plan))
    if plan.absolute_time_error_bound_s is None:
        blockers.append("NO_DEFENSIBLE_FINITE_PPS_TO_ADC_UTC_ERROR_BOUND")
    if plan.detector_manifest_sha256 is None:
        blockers.append("DEVELOPMENT_FIXTURE_DETECTOR_MANIFEST_NOT_FROZEN")
    return tuple(blockers)


__all__ = [
    "DEVELOPMENT_FIXTURE",
    "DOPPLER_CORRECTION_CLASSIFICATION",
    "HISTORICAL_TLE_LINES",
    "NULL_FAMILIES",
    "PER_FILE_EXPLICIT_DOPPLER_FLAG",
    "PLAN",
    "PLAN_STATUS",
    "PRIMARY",
    "SEALED_REPLICATION_RESERVE",
    "SENSITIVITY_TLE_LINES",
    "NullFamily",
    "RSP03ForwardPlan",
    "RecordingRole",
    "primary_analysis_blockers",
    "structural_errors",
]
