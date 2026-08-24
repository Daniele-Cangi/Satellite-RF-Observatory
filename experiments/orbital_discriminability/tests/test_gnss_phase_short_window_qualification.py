from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import (
    gnss_phase_short_window_qualification as qualification,
)


ROOT = Path(__file__).resolve().parents[1]


def header_line(data: str, label: str) -> str:
    return f"{data:<60}{label:<20}\n"


def field(value: float | None, lli: int = 0) -> str:
    if value is None:
        return " " * 16
    return f"{value:14.3f}{' ' if lli == 0 else lli} "


def fixture(
    locator: qualification.ProductLocator,
    *,
    observables: tuple[str, ...] = qualification.OBSERVABLES,
    blank: tuple[int, str, str] | None = None,
    nonzero_lli: tuple[int, str, str] | None = None,
    phase_jump: tuple[int, str] | None = None,
    omit_time_of_last: bool = False,
) -> bytearray:
    config = qualification.EXPECTED_CONFIGURATION[locator.station]
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
        header_line(" -2350000.0 -4650000.0 3670000.0", "APPROX POSITION XYZ"),
        header_line(
            f"G  {len(observables):3d} "
            + "".join(f"{item:>3} " for item in observables),
            "SYS / # / OBS TYPES",
        ),
        header_line("      30.000", "INTERVAL"),
        header_line(
            "  2026     8     5     0     0    0.0000000     GPS",
            "TIME OF FIRST OBS",
        ),
    ]
    if not omit_time_of_last:
        lines.append(
            header_line(
                "  2026     8     5    23    59   30.0000000     GPS",
                "TIME OF LAST OBS",
            )
        )
    lines.append(header_line("", "END OF HEADER"))
    for epoch_index, epoch in enumerate(qualification.expected_epochs()):
        lines.append(
            f"> {epoch.year:4d} {epoch.month:02d} {epoch.day:02d} "
            f"{epoch.hour:02d} {epoch.minute:02d} {epoch.second:10.7f}  0  2\n"
        )
        for sat_index, satellite in enumerate(qualification.SATELLITES):
            values: dict[str, tuple[float | None, int]] = {}
            for observable in observables:
                if observable.startswith("C"):
                    value = 22_000_000.0 + epoch_index + sat_index * 10.0
                elif observable == "L1C":
                    value = 115_000_000.0 + epoch_index * 0.020 + sat_index
                elif observable == "L2W":
                    value = 89_000_000.0 + epoch_index * 0.015 + sat_index
                else:
                    value = 45.0
                if phase_jump == (epoch_index, satellite) and observable == "L1C":
                    value += 1.0
                values[observable] = (value, 0)
            if blank and blank[:2] == (epoch_index, satellite):
                values[blank[2]] = (None, 0)
            if nonzero_lli and nonzero_lli[:2] == (epoch_index, satellite):
                value, _ = values[nonzero_lli[2]]
                values[nonzero_lli[2]] = (value, 1)
            record = satellite + "".join(
                field(*values[observable]) for observable in observables
            )
            lines.append(record + "\n")
    return bytearray("".join(lines).encode("ascii"))


def scans(**left_kwargs):
    left_payload = fixture(qualification.PRODUCTS[0], **left_kwargs)
    right_payload = fixture(qualification.PRODUCTS[1])
    left = qualification.scan_decoded(left_payload, qualification.PRODUCTS[0])
    right = qualification.scan_decoded(right_payload, qualification.PRODUCTS[1])
    return left, right


def test_complete_short_window_passes_model_blind_health() -> None:
    left, right = scans()
    try:
        summary = qualification.evaluate((left, right))
    finally:
        left.erase()
        right.erase()

    assert summary["outcome"] == "GNSS_SHORT_WINDOW_QUALIFICATION_PASSED"
    assert summary["full_joint_window"] is True
    assert summary["joint_core_segments"] == [
        {
            "start_gps": "2026-08-05T05:54:00.000000Z",
            "stop_gps": "2026-08-05T07:03:00.000000Z",
            "epoch_count": 139,
            "duration_s": 4140,
        }
    ]
    assert summary["geometry_free_phase_health"]["state"] == "SATISFIED"
    assert summary["orbital_model_used"] is False
    assert summary["orbital_scores_produced"] == 0


def test_missing_core_or_nonzero_lli_breaks_without_reselection() -> None:
    for kwargs in (
        {"blank": (40, "G22", "L2W")},
        {"nonzero_lli": (40, "G22", "L1C")},
    ):
        left, right = scans(**kwargs)
        try:
            summary = qualification.evaluate((left, right))
        finally:
            left.erase()
            right.erase()
        assert summary["outcome"] == "GNSS_SHORT_WINDOW_QUALIFICATION_FAILED"
        assert summary["full_joint_window"] is False


def test_geometry_free_jump_fails_without_orbit_prediction() -> None:
    left, right = scans(phase_jump=(50, "G30"))
    try:
        summary = qualification.evaluate((left, right))
    finally:
        left.erase()
        right.erase()

    health = summary["geometry_free_phase_health"]
    assert health["state"] == "UNSATISFIED"
    assert health["orbital_prediction_used"] is False
    assert summary["outcome"] == "GNSS_SHORT_WINDOW_QUALIFICATION_FAILED"


def test_code_witness_is_fractional_but_partition_boundaries_are_fatal() -> None:
    left, right = scans(blank=(100, "G22", "C1C"))
    try:
        passing = qualification.evaluate((left, right))
    finally:
        left.erase()
        right.erase()
    assert passing["same_path_code_witness"]["state"] == "SATISFIED"

    left, right = scans(blank=(77, "G22", "C1C"))
    try:
        failing = qualification.evaluate((left, right))
    finally:
        left.erase()
        right.erase()
    assert failing["same_path_code_witness"]["state"] == "UNSATISFIED"
    assert failing["outcome"] == "GNSS_SHORT_WINDOW_QUALIFICATION_FAILED"


def test_optional_signal_strength_can_be_absent() -> None:
    observables = qualification.CORE_PHASE + qualification.SAME_PATH_CODE
    left, right = scans(observables=observables)
    try:
        summary = qualification.evaluate((left, right))
        optional = [
            row
            for row in left.coverage
            if row["observable"] in qualification.OPTIONAL_DIAGNOSTIC
        ]
    finally:
        left.erase()
        right.erase()

    assert summary["outcome"] == "GNSS_SHORT_WINDOW_QUALIFICATION_PASSED"
    assert {row["state"] for row in optional} == {"BLANK"}


def test_coverage_never_contains_observation_values() -> None:
    payload = fixture(qualification.PRODUCTS[0])
    scan = qualification.scan_decoded(payload, qualification.PRODUCTS[0])
    try:
        assert len(scan.coverage) == 139 * 2 * 6
        encoded = qualification.strict_json(scan.coverage)
    finally:
        scan.erase()
        payload[:] = b"\x00" * len(payload)

    assert '"value"' not in encoded
    assert "115000000" not in encoded
    assert np.count_nonzero(scan.phase_cycles) == 0


def test_header_requires_time_of_last_and_frozen_configuration() -> None:
    payload = fixture(qualification.PRODUCTS[0], omit_time_of_last=True)
    with pytest.raises(Exception, match="time_of_last_observation"):
        qualification.scan_decoded(payload, qualification.PRODUCTS[0])


def test_manifest_has_no_primary_or_orbital_surface() -> None:
    manifest = qualification.manifest()
    encoded = qualification.strict_json(manifest)

    assert all("2026217" in product["name"] for product in manifest["products"])
    assert "2026220" not in encoded
    assert manifest["health"]["orbital_model_available_to_qualification"] is False
    assert manifest["persistence"]["observation_values"] == 0
    assert len(qualification.manifest_sha256()) == 64


def test_materialization_hashes_complete_bytes_before_decode(monkeypatch) -> None:
    payload = b"complete-compressed-fixture"

    class Response:
        def __init__(self):
            self.blocks = [payload, b""]

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self, _size):
            return self.blocks.pop(0)

    monkeypatch.setattr(qualification, "urlopen", lambda *_args, **_kwargs: Response())
    materialized, receipt = qualification.materialize(qualification.PRODUCTS[0])
    try:
        assert bytes(materialized) == payload
        assert receipt["complete_file_bytes"] == len(payload)
        assert receipt["complete_file_sha256"] == sha256(payload).hexdigest()
        assert receipt["hash_before_any_decode"] is True
    finally:
        materialized[:] = b"\x00" * len(materialized)


def test_strict_json_rejects_nonfinite() -> None:
    with pytest.raises(ValueError):
        qualification.strict_json({"bad": float("nan")})
    assert json.loads(qualification.strict_json(qualification.manifest())) == (
        qualification.manifest()
    )


def test_frozen_real_outcome_passes_without_primary_or_orbital_access() -> None:
    outcome = json.loads(
        (ROOT / qualification.OUTCOME_NAME).read_text(encoding="utf-8")
    )
    summary = json.loads(
        (ROOT / qualification.SUMMARY_NAME).read_text(encoding="utf-8")
    )

    assert outcome["outcome"] == "GNSS_SHORT_WINDOW_QUALIFICATION_PASSED"
    assert outcome["source_commit"] == (
        "d22695e513734c41ebb909b45c3846b37069940a"
    )
    assert outcome["source_sha256"] == qualification.source_sha256()
    assert [(row["complete_file_bytes"], row["complete_file_sha256"]) for row in outcome["artifacts"]] == [
        (
            2_170_051,
            "ef2c80b96c5bbe7fbb83fb90abaa6203a9ff8d557a9aa3a39db5930188487573",
        ),
        (
            2_500_618,
            "582199ddeccd57fdde76f30aed9bb4e9489f4248563f3b7f217714fdd4dde473",
        ),
    ]
    assert summary["structural_counts"] == {"PRESENT": 3336}
    assert summary["full_joint_window"] is True
    assert summary["geometry_free_phase_health"]["state"] == "SATISFIED"
    assert max(
        row["maximum_absolute_second_difference_m"]
        for row in summary["geometry_free_phase_health"]["links"]
    ) == pytest.approx(0.019273575395345688)
    assert summary["same_path_code_witness"]["state"] == "SATISFIED"
    assert all(
        row["coverage_fraction"] == 1.0
        for row in summary["same_path_code_witness"]["links"]
    )
    assert all(value == 0 for value in outcome["primary_doy220_access"].values())
    assert outcome["orbital_prediction_access"] == 0
    assert outcome["orbital_scores_produced"] == 0
    assert outcome["persistence"]["observation_values"] == 0
    assert outcome["next_authority"] == "PRIMARY_SEAL_REVIEW_ONLY"


def test_frozen_coverage_is_structural_only_and_strict_jsonl() -> None:
    path = ROOT / qualification.COVERAGE_NAME
    raw = path.read_bytes()

    assert raw.count(b"\n") == 3336
    assert b'"value"' not in raw
    assert b"NaN" not in raw and b"Infinity" not in raw
    assert sha256(raw).hexdigest() == (
        "a1bcf2b0117caaa08694631bcacc6f3a4ea044f7319f7e1b90b79784ce8e3a5e"
    )
