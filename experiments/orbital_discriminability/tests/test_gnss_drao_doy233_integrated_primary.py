from __future__ import annotations

from pathlib import Path
from hashlib import sha256
import json

import numpy as np
import pytest

from experiments.orbital_discriminability import gnss_all_track_clutter_scorer as scorer
from experiments.orbital_discriminability import gnss_drao_doy233_integrated_primary as primary
from experiments.orbital_discriminability import gnss_drao_doy233_integrated_primary_plan as plan


ROOT = Path(__file__).resolve().parents[1]
SATELLITES = ("G07", "G08", "G09", "G21", "G27", "G30", "G31")
MANIFEST = ROOT / "GNSS_DRAO_DOY233_INTEGRATED_PRIMARY_EXECUTOR_MANIFEST.json"


def header_line(data: str, label: str) -> str:
    return f"{data:<60}{label:<20}\n"


def phase_record(observable: str) -> str:
    raw = [" "] * 60
    raw[0] = "G"
    raw[2:5] = observable
    raw[6:14] = f"{0.0:8.5f}"
    raw[16:18] = " 0"
    return "".join(raw)


def field(value: float | None, lli: int = 0) -> str:
    if value is None:
        return " " * 16
    return f"{value:14.3f}{' ' if lli == 0 else lli} "


def fixture(
    *,
    missing: tuple[int, str, str] | None = None,
    witness_excursion: bool = False,
) -> bytearray:
    observables = ("C1C", "L1C", "C2W", "L2W")
    antenna_type = f"{'TWIVC6050':<16}SCIS"
    lines = [
        header_line("     3.04           OBSERVATION DATA    G", "RINEX VERSION / TYPE"),
        header_line("DRAO", "MARKER NAME"),
        header_line("40105M002", "MARKER NUMBER"),
        header_line(
            f"{'RX':<20}{'SEPT POLARX5':<20}{'5.2.0':<20}",
            "REC # / TYPE / VERS",
        ),
        header_line(f"{'ANT':<20}{antenna_type:<20}", "ANT # / TYPE"),
        header_line(" -2059164.0 -3621108.0 4814432.0", "APPROX POSITION XYZ"),
        header_line(
            f"G  {len(observables):3d} "
            + "".join(f"{observable:>3} " for observable in observables),
            "SYS / # / OBS TYPES",
        ),
        header_line("      30.000", "INTERVAL"),
        header_line(
            "  2026     8    21     0     0    0.0000000     GPS",
            "TIME OF FIRST OBS",
        ),
        header_line(
            "  2026     8    21    23    59   30.0000000     GPS",
            "TIME OF LAST OBS",
        ),
        header_line(f"{1:6d}", "RCV CLOCK OFFS APPL"),
        header_line(phase_record("L1C"), "SYS / PHASE SHIFT"),
        header_line(phase_record("L2W"), "SYS / PHASE SHIFT"),
        header_line("", "END OF HEADER"),
    ]
    for epoch_index, epoch in enumerate(primary.expected_epochs()):
        second = epoch.second + epoch.microsecond / 1_000_000
        lines.append(
            f"> {epoch.year:4d} {epoch.month:02d} {epoch.day:02d} "
            f"{epoch.hour:02d} {epoch.minute:02d} {second:10.7f}  0  7\n"
        )
        for sat_index, satellite in enumerate(SATELLITES):
            physical = 22_000_000.0 + sat_index * 125.0 + epoch_index * 0.75
            values: dict[str, float | None] = {
                "C1C": physical,
                "L1C": physical / primary.LAMBDA_L1_M,
                "C2W": physical,
                "L2W": physical / primary.LAMBDA_L2_M,
            }
            if witness_excursion and satellite == "G31" and epoch_index >= 79:
                values["C1C"] += (epoch_index - 79) * 100.0
            if missing is not None and missing[:2] == (epoch_index, satellite):
                values[missing[2]] = None
            lines.append(
                satellite
                + "".join(field(values[observable]) for observable in observables)
                + "\n"
            )
    return bytearray("".join(lines).encode("ascii"))


def scan(**kwargs: object) -> primary.PrimaryScan:
    payload = fixture(**kwargs)
    try:
        return primary._scan_decoded_fixture(payload, artifact_site_id=plan.STATION)
    finally:
        payload[:] = b"\x00" * len(payload)


def test_manifest_refuses_unselected_primary_without_access() -> None:
    manifest = primary.executor_manifest(ROOT)

    assert manifest["state"] == "EXECUTOR_FROZEN_PRIMARY_ARTIFACT_UNSELECTED"
    assert manifest["artifact"] == {
        "logical_product": None,
        "locator": None,
        "sha256": None,
        "selected": False,
    }
    assert not any(manifest["access_at_freeze"].values())
    with pytest.raises(PermissionError, match="PRIMARY_ARTIFACT_UNSELECTED"):
        primary.refuse_unselected_primary(ROOT)


def test_post_commit_executor_seal_binds_source_and_contract() -> None:
    value = json.loads(MANIFEST.read_text(encoding="ascii"))
    source = Path(primary.__file__).read_bytes().replace(b"\r\n", b"\n")
    contract_hash = sha256(
        primary.strict_json(primary.executor_manifest(ROOT)).encode("ascii")
    ).hexdigest()

    assert value["source_commit"] == "505237d3fa962a441e8a7a8389e854120881d9da"
    assert value["executor_source_canonical_sha256"] == sha256(source).hexdigest()
    assert value["executor_contract_sha256"] == contract_hash
    assert value["state"].endswith("ARTIFACT_UNSELECTED")
    assert not any(value["access_at_freeze"].values())
    assert value["authority"]["observation_access_authorized"] is False


def test_opaque_surface_is_complete_symmetric_and_identity_blind() -> None:
    hypotheses, registry = primary.hypothesis_surface(ROOT)
    try:
        assert len(hypotheses) == len(registry) == 10_087
        assert sum(row.family == scorer.FAMILY_ORBITAL for row in hypotheses) == 5_040
        assert sum(row.family == scorer.FAMILY_GEOMETRY_NULL for row in hypotheses) == 5_040
        assert sum(row.family == scorer.FAMILY_AFFINE_NULL for row in hypotheses) == 7
        assert not any(code in plan.strict_json(registry) for code in plan.MODEL_CODES)
    finally:
        for row in hypotheses:
            row.model_matrix_m.fill(0.0)


def test_dynamic_all_track_scan_admits_seven_without_prn_filter() -> None:
    measurement = scan()
    try:
        admission, tracks = primary.admit(measurement)
        assert measurement.satellites == SATELLITES
        assert len(tracks) == 7
        assert admission["state"] == "PRIMARY_MEASUREMENT_ADMITTED_FOR_OPAQUE_SCORE"
        assert admission["same_path_witness"]["exclusions_evaluated"] == 7
        assert len(admission["same_path_witness"]["rows"]) == 42
        encoded = primary.strict_json(measurement.coverage)
        assert "22000000" not in encoded
        assert all(identifier.startswith("T_") for identifier in tracks)
    finally:
        for values in locals().get("tracks", {}).values():
            values.fill(0.0)
        measurement.erase()


def test_missing_seventh_complete_track_refuses_before_score() -> None:
    with pytest.raises(
        primary.PrimaryMeasurementInvalid,
        match="COMPLETE_OPAQUE_TRACK_COUNT_NOT_SEVEN:6",
    ):
        scan(missing=(25, "G31", "L2W"))


def test_every_possible_exclusion_must_pass_same_path_witness() -> None:
    measurement = scan(witness_excursion=True)
    try:
        with pytest.raises(
            primary.PrimaryMeasurementInvalid,
            match="SAME_PATH_WITNESS_UNSATISFIED",
        ):
            primary.admit(measurement)
    finally:
        measurement.erase()


def test_score_is_identity_blind_and_hash_precedes_reveal() -> None:
    measurement = scan()
    seen: dict[str, object] = {}

    def fake_score(
        tracks: dict[str, np.ndarray],
        hypotheses: tuple[scorer.OpaqueHypothesis, ...],
        *,
        pairwise_guard_m: float,
    ) -> dict[str, object]:
        seen["track_ids"] = tuple(sorted(tracks))
        seen["hypothesis_count"] = len(hypotheses)
        seen["guard"] = pairwise_guard_m
        assert all(value.startswith("T_") for value in tracks)
        assert not any(prn in primary.strict_json(sorted(tracks)) for prn in SATELLITES)
        return {
            "schema": "synthetic-opaque-score-receipt",
            "score_state": "AMBIGUOUS",
            "identity_reveal_performed": False,
        }

    outcome = primary.execute_admitted_scan(
        measurement, ROOT, score_function=fake_score
    )

    assert outcome["outcome"] == "AMBIGUOUS"
    assert outcome["reveal_performed_after_score_hash"] is True
    assert len(outcome["score_receipt_sha256_before_reveal"]) == 64
    assert seen["hypothesis_count"] == 10_087
    assert seen["guard"] == plan.PAIRWISE_GUARD_M
    assert np.count_nonzero(measurement.phase_cycles) == 0
    assert np.count_nonzero(measurement.code_m) == 0


def test_description_identity_failure_cannot_become_measurement_rejection() -> None:
    payload = fixture()
    try:
        with pytest.raises(
            primary.PrimaryDescriptionError,
            match="FROZEN_ARTIFACT_SITE_ID_MISMATCH",
        ):
            primary._scan_decoded_fixture(payload, artifact_site_id="OTHER00XXX")
    finally:
        payload[:] = b"\x00" * len(payload)


def test_strict_json_rejects_nonfinite_values() -> None:
    with pytest.raises(ValueError):
        primary.strict_json({"bad": float("nan")})
