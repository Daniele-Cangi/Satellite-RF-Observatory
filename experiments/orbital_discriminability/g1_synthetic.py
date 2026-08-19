"""Deterministic, offline-only Gate G1 vertical fixtures."""

from __future__ import annotations

from datetime import timedelta

from .g1_admission import (
    DEFAULT_REQUIRED_TRANSFORMS,
    DEFAULT_REQUIRED_WITNESSES,
    G1AdmissionResult,
    OrbitalPassPlan,
    OrbitalReceiverOffer,
    evaluate_capability_admission,
)
from .synthetic import COPENHAGEN, ISS_TLE, LAYOUTS, PASS_END, PASS_START


EVALUATED_AT = PASS_START - timedelta(seconds=30)


def reference_pass_plan() -> OrbitalPassPlan:
    return OrbitalPassPlan(
        pass_id="G1-ISS-2019-FIXTURE",
        orbital_elements=ISS_TLE,
        start_time=PASS_START,
        end_time=PASS_END,
        cadence_s=5.0,
        carrier_hz=145_800_000.0,
        minimum_elevation_deg=10.0,
        minimum_joint_holdout_samples=12,
        maximum_gap_s=10.0,
        orbital_prediction_uncertainty_hz_per_station=1.0,
    )


def reference_offers() -> tuple[OrbitalReceiverOffer, ...]:
    plan = reference_pass_plan()
    return tuple(
        _offer(capability_id, observer, resolution_hz=5.0, clock_error_s=1.0, plan=plan)
        for capability_id, observer in (
            ("BERLIN", LAYOUTS["BERLIN"]),
            ("COPENHAGEN", COPENHAGEN),
            ("EINDHOVEN", LAYOUTS["EINDHOVEN"]),
        )
    )


def run_reference_admission() -> G1AdmissionResult:
    return evaluate_capability_admission(
        reference_pass_plan(),
        reference_offers(),
        evaluated_at=EVALUATED_AT,
    )


def coarse_local_offers() -> tuple[OrbitalReceiverOffer, ...]:
    plan = reference_pass_plan()
    return (
        _offer("COPENHAGEN", COPENHAGEN, resolution_hz=20.0, clock_error_s=5.0, plan=plan),
        _offer("LOCAL", LAYOUTS["LOCAL_10_KM"], resolution_hz=20.0, clock_error_s=5.0, plan=plan),
    )


def _offer(
    capability_id: str,
    observer,  # type: ignore[no-untyped-def]
    *,
    resolution_hz: float,
    clock_error_s: float,
    plan: OrbitalPassPlan,
) -> OrbitalReceiverOffer:
    return OrbitalReceiverOffer(
        capability_id=capability_id,
        observer=observer,
        hardware_root=f"receiver:{capability_id.lower()}",
        described_at=EVALUATED_AT - timedelta(seconds=10),
        ttl_s=600.0,
        availability_start=plan.start_time - timedelta(minutes=1),
        availability_end=plan.end_time + timedelta(minutes=1),
        band_low_hz=145_000_000.0,
        band_high_hz=146_000_000.0,
        frequency_resolution_hz=resolution_hz,
        event_time_source="GNSS_SAMPLE_TIME",
        maximum_event_time_error_s=clock_error_s,
        sequence_continuity_exposed=True,
        maximum_gap_s=5.0,
        transform_steps=DEFAULT_REQUIRED_TRANSFORMS,
        frequency_axis_preserved=True,
        ridge_shape_preserved=True,
        same_path_witnesses=DEFAULT_REQUIRED_WITNESSES,
    )
