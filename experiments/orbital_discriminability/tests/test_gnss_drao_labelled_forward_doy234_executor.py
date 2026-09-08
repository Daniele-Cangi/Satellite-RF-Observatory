from __future__ import annotations

from pathlib import Path
from hashlib import sha256
import json

import numpy as np
import pytest

from experiments.orbital_discriminability import (
    gnss_drao_labelled_forward_doy234_executor as executor,
)
from experiments.orbital_discriminability import (
    gnss_drao_labelled_forward_doy234_plan as plan,
)
from experiments.orbital_discriminability import (
    gnss_drao_labelled_forward_doy238_executor as prior,
)


ROOT = Path(__file__).resolve().parents[1]
SEAL = ROOT / "GNSS_DRAO_LABELLED_FORWARD_DOY234_EXECUTOR_MANIFEST.json"


def phase_record(observable: str, correction: str = "") -> str:
    raw = [" "] * 60
    raw[0] = "G"
    raw[2:5] = observable
    if correction:
        raw[6:14] = f"{float(correction):8.5f}"
        raw[16:18] = " 0"
    return "".join(raw)


def header_line(data: str, label: str) -> str:
    return f"{data:<60}{label:<20}\n"


def field(value: float) -> str:
    return f"{value:14.3f}  "


def synthetic_nominal_fixture() -> bytearray:
    observables = ("C1C", "L1C", "C2W", "L2W")
    bundle = json.loads((ROOT / plan.BUNDLE_NAME).read_text(encoding="ascii"))
    curves = {
        satellite: np.asarray(bundle["labelled_model_curves_m"][satellite])
        for satellite in plan.CODEBOOK
    }
    lines = [
        header_line("     3.04           OBSERVATION DATA    G", "RINEX VERSION / TYPE"),
        header_line("DRAO synthetic regression", "MARKER NAME"),
        header_line(plan.DOMES, "MARKER NUMBER"),
        header_line(
            f"{'RX':<20}{'SEPT POLARX5':<20}{'5.2.0':<20}",
            "REC # / TYPE / VERS",
        ),
        header_line(f"{'ANT':<20}{'TWIVC6050':<16}{'SCIS':<4}", "ANT # / TYPE"),
        header_line(" -2059164.0 -3621108.0 4814432.0", "APPROX POSITION XYZ"),
        header_line(
            f"G  {len(observables):3d} "
            + "".join(f"{observable:>3} " for observable in observables),
            "SYS / # / OBS TYPES",
        ),
        header_line("      30.000", "INTERVAL"),
        header_line("  2026     8    22     0     0    0.0000000     GPS", "TIME OF FIRST OBS"),
        header_line("  2026     8    22    23    59   30.0000000     GPS", "TIME OF LAST OBS"),
        header_line("     1", "RCV CLOCK OFFS APPL"),
        header_line(phase_record("L1C"), "SYS / PHASE SHIFT"),
        header_line(phase_record("L2W"), "SYS / PHASE SHIFT"),
        header_line("", "END OF HEADER"),
    ]
    for epoch_index, epoch in enumerate(executor.expected_epochs()):
        second = epoch.second + epoch.microsecond / 1_000_000
        lines.append(
            f"> {epoch.year:4d} {epoch.month:02d} {epoch.day:02d} "
            f"{epoch.hour:02d} {epoch.minute:02d} {second:10.7f}  0 "
            f"{len(plan.CODEBOOK):2d}\n"
        )
        for satellite in plan.CODEBOOK:
            physical = 22_000_000.0 + curves[satellite][epoch_index]
            values = (
                physical,
                physical / prior.LAMBDA_L1_M,
                physical,
                physical / prior.LAMBDA_L2_M,
            )
            lines.append(satellite + "".join(field(value) for value in values) + "\n")
    return bytearray("".join(lines).encode("ascii"))


def test_manifest_binds_final_shortlist_proof_and_refuses_selection() -> None:
    value = executor.executor_manifest(ROOT)

    assert value["state"] == "DRAO_DOY234_EXECUTOR_FROZEN_ARTIFACT_UNSELECTED"
    assert value["phase_shift_states"][executor.REFERENCE_BLANK].startswith("VALID")
    assert value["phase_shift_states"][executor.UNKNOWN] == "PRIMARY_NOT_EVALUATED"
    assert not any(value["access_at_freeze"].values())
    with pytest.raises(
        executor.Doy234DescriptionError,
        match="UNREVIEWED_DOY234_SELECTION_PRESENT",
    ):
        executor.refuse_unselected(ROOT)


def test_post_commit_seal_binds_source_contract_and_zero_access() -> None:
    value = json.loads(SEAL.read_text(encoding="ascii"))
    contract_hash = sha256(
        executor.strict_json(executor.executor_manifest(ROOT)).encode("ascii")
    ).hexdigest()

    assert value["source_commit"] == "f3421b3bf78259d1abc61e0d0847cf35556c925f"
    assert value["executor_source_canonical_sha256"] == executor.source_sha256()
    assert value["executor_contract_sha256"] == contract_hash
    assert value["frozen_inputs"] == executor.executor_manifest(ROOT)["frozen_inputs"]
    assert value["selection_receipt"]["present_at_freeze"] is False
    assert value["authority"]["observation_access_authorized"] is False
    assert not any(value["access_at_freeze"].values())


def test_reference_signal_blank_and_explicit_zero_are_distinct_valid_states() -> None:
    blank = executor.phase_shift_ledger(
        (phase_record("L1C"), phase_record("L2W")), plan.CODEBOOK
    )
    explicit = executor.phase_shift_ledger(
        (phase_record("L1C", "0"), phase_record("L2W", "0")), plan.CODEBOOK
    )

    assert blank["required_observables"]["L1C"]["state"] == executor.REFERENCE_BLANK
    assert blank["required_observables"]["L1C"]["declared_correction_cycles"] is None
    assert explicit["required_observables"]["L1C"]["state"] == executor.EXPLICIT
    assert explicit["required_observables"]["L1C"]["declared_correction_cycles"] == 0.0
    assert explicit["required_observables"]["L1C"]["stored_phase_numerically_modified_again"] is False


def test_blank_reference_phase_shift_survives_full_model_blind_vertical() -> None:
    payload = synthetic_nominal_fixture()
    measurement = executor.scan_decoded(payload, archive_site_id=plan.STATION)
    coordinate = None
    try:
        ledger = measurement.header["transforms"]["phase_shift"]
        assert ledger["required_observables"]["L1C"]["state"] == executor.REFERENCE_BLANK
        admission, coordinate = executor.admit_model_blind(measurement)
        outcome = executor.score(coordinate, ROOT)
        assert admission["state"] == "DRAO_DOY234_MEASUREMENT_ADMITTED_FOR_FROZEN_SCORE"
        assert outcome["outcome"] == "ORBITAL_MODEL_PREDICTIVELY_PREFERRED"
    finally:
        if coordinate is not None:
            coordinate.fill(0.0)
        measurement.erase()
        payload[:] = b"\x00" * len(payload)
    assert not any(payload)


def test_system_unknown_and_missing_required_record_are_typed() -> None:
    unknown = list(" " * 60)
    unknown[0] = "G"
    with pytest.raises(executor.Doy234DescriptionError, match=executor.UNKNOWN):
        executor.phase_shift_ledger(("".join(unknown),), plan.CODEBOOK)
    with pytest.raises(
        executor.Doy234DescriptionError, match="PHASE_SHIFT_REQUIRED_RECORD_MISSING:L2W"
    ):
        executor.phase_shift_ledger((phase_record("L1C"),), plan.CODEBOOK)


def test_nominal_and_null_family_controls_use_doy234_guard() -> None:
    models = executor._load_models(ROOT)
    try:
        nominal = executor.score(models[prior.FAMILY_ORBITAL].copy(), ROOT)
        affine_control = models[prior.FAMILY_ORBITAL].copy()
        affine_control[plan.PREFIX_EPOCHS :] = 0.0
        affine = executor.score(affine_control, ROOT)
    finally:
        affine_control.fill(0.0)
        for values in models.values():
            values.fill(0.0)

    assert nominal["outcome"] == "ORBITAL_MODEL_PREDICTIVELY_PREFERRED"
    assert nominal["guard_b_m"] == executor.ONE_MODEL_BOUND_M
    assert affine["outcome"] == "PREFIX_AFFINE_NULL_PREFERRED"


def test_prefix_mismatch_is_not_detectable() -> None:
    models = executor._load_models(ROOT)
    observed = models[prior.FAMILY_ORBITAL].copy()
    excursion = np.square(np.arange(plan.RAW_EPOCHS, dtype=np.float64)) * 5.0
    observed[:, 0] += excursion
    observed -= np.mean(observed, axis=1, keepdims=True)
    try:
        result = executor.score(observed, ROOT)
    finally:
        observed.fill(0.0)
        excursion.fill(0.0)
        for values in models.values():
            values.fill(0.0)
    assert result["outcome"] == "NOT_DETECTABLE"


def test_strict_json_rejects_nonfinite() -> None:
    with pytest.raises(ValueError):
        executor.strict_json({"bad": float("inf")})
