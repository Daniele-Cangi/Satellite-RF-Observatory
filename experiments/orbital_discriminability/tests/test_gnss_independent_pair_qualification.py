from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import (
    gnss_independent_pair_qualification as qualification,
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
    receiver_serial: str | None = None,
) -> bytearray:
    config = qualification.EXPECTED_CONFIGURATION[locator.station]
    receiver_serial = receiver_serial or config["receiver_serial"]
    lines = [
        header_line(
            "     3.04           OBSERVATION DATA    G",
            "RINEX VERSION / TYPE",
        ),
        header_line(locator.station[:4], "MARKER NAME"),
        header_line(
            f"{receiver_serial:<20}{config['receiver_type']:<20}"
            f"{config['receiver_version']:<20}",
            "REC # / TYPE / VERS",
        ),
        header_line(
            f"{config['antenna_serial']:<20}{config['antenna_type']:<20}",
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
        header_line(
            "  2026     8     5    23    59   30.0000000     GPS",
            "TIME OF LAST OBS",
        ),
        header_line("", "END OF HEADER"),
    ]
    for epoch_index, epoch in enumerate(qualification.expected_epochs()):
        lines.append(
            f"> {epoch.year:4d} {epoch.month:02d} {epoch.day:02d} "
            f"{epoch.hour:02d} {epoch.minute:02d} {epoch.second:10.7f}  0  2\n"
        )
        for satellite_index, satellite in enumerate(qualification.SATELLITES):
            values: dict[str, tuple[float | None, int]] = {}
            for observable in observables:
                if observable.startswith("C"):
                    value = 22_000_000.0 + epoch_index + satellite_index * 10.0
                elif observable == "L1C":
                    value = 115_000_000.0 + epoch_index * 0.020 + satellite_index
                elif observable == "L2W":
                    value = 89_000_000.0 + epoch_index * 0.015 + satellite_index
                else:
                    value = 45.0
                if phase_jump == (epoch_index, satellite) and observable == "L1C":
                    value += 1.0
                values[observable] = value, 0
            if blank and blank[:2] == (epoch_index, satellite):
                values[blank[2]] = None, 0
            if nonzero_lli and nonzero_lli[:2] == (epoch_index, satellite):
                value, _ = values[nonzero_lli[2]]
                values[nonzero_lli[2]] = value, 1
            lines.append(
                satellite
                + "".join(field(*values[observable]) for observable in observables)
                + "\n"
            )
    return bytearray("".join(lines).encode("ascii"))


def scans(**left_options):
    left_payload = fixture(qualification.PRODUCTS[0], **left_options)
    right_payload = fixture(qualification.PRODUCTS[1])
    return (
        qualification.scan_decoded(left_payload, qualification.PRODUCTS[0]),
        qualification.scan_decoded(right_payload, qualification.PRODUCTS[1]),
    )


def test_manifest_is_bound_to_plan_and_contains_no_primary_locator() -> None:
    manifest = qualification.manifest()
    encoded = qualification.strict_json(manifest)

    assert manifest["proof_plan_manifest_sha256"] == (
        qualification.PROOF_PLAN_MANIFEST_SHA256
    )
    assert [item["station"] for item in manifest["products"]] == [
        "ALGO00CAN",
        "MDO100USA",
    ]
    assert all("2026217" in item["name"] for item in manifest["products"])
    assert "2026219" not in encoded and "/219/" not in encoded
    assert manifest["transport"]["both_complete_hashes_before_first_decode"]
    assert manifest["persistence"]["observation_values"] == 0
    assert len(qualification.manifest_sha256()) == 64


def test_complete_pair_passes_model_blind_health() -> None:
    left, right = scans()
    try:
        summary = qualification.evaluate((left, right))
    finally:
        left.erase()
        right.erase()

    assert summary["outcome"] == "GNSS_INDEPENDENT_PAIR_QUALIFICATION_PASSED"
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
    assert summary["same_path_code_witness"]["state"] == "SATISFIED"
    assert summary["orbital_model_used"] is False
    assert summary["orbital_scores_produced"] == 0


def test_core_gap_lli_and_geometry_free_jump_each_fail() -> None:
    options = (
        {"blank": (40, "G22", "L2W")},
        {"nonzero_lli": (40, "G22", "L1C")},
        {"phase_jump": (50, "G30")},
    )
    for kwargs in options:
        left, right = scans(**kwargs)
        try:
            summary = qualification.evaluate((left, right))
        finally:
            left.erase()
            right.erase()
        assert summary["outcome"] == "GNSS_INDEPENDENT_PAIR_QUALIFICATION_FAILED"


def test_code_witness_uses_frozen_coverage_and_boundary_rule() -> None:
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


def test_optional_signal_strength_is_never_fatal_or_parsed() -> None:
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

    assert summary["outcome"] == "GNSS_INDEPENDENT_PAIR_QUALIFICATION_PASSED"
    assert {row["state"] for row in optional} == {"BLANK"}
    assert summary["code_or_snr_scalars_parsed"] == 0


def test_header_identity_includes_receiver_serial() -> None:
    payload = fixture(qualification.PRODUCTS[0], receiver_serial="WRONG")
    with pytest.raises(
        qualification.QualificationFailure, match="RECEIVER_SERIAL_CHANGED"
    ):
        qualification.scan_decoded(payload, qualification.PRODUCTS[0])


def test_coverage_contains_topology_but_no_observation_values() -> None:
    payload = fixture(qualification.PRODUCTS[0])
    scan = qualification.scan_decoded(payload, qualification.PRODUCTS[0])
    try:
        encoded = qualification.strict_json(scan.coverage)
        assert len(scan.coverage) == 139 * 2 * 6
    finally:
        scan.erase()
        payload[:] = b"\x00" * len(payload)

    assert '"value"' not in encoded
    assert "115000000" not in encoded
    assert np.count_nonzero(scan.phase_cycles) == 0


def test_materialization_hashes_complete_bytes_before_return(monkeypatch) -> None:
    payload = b"complete-compressed-qualification-fixture"

    class Response:
        headers = {
            "Content-Length": str(len(payload)),
            "ETag": '"fixture"',
            "Last-Modified": "frozen",
        }

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


def test_run_hashes_both_products_before_first_decode(monkeypatch, tmp_path) -> None:
    materialized: list[str] = []
    decoded: list[str] = []

    def fake_materialize(locator):
        materialized.append(locator.station)
        payload = bytearray(locator.station.encode("ascii"))
        return payload, {
            "station": locator.station,
            "product": locator.name,
            "url": locator.url,
            "attempts": 1,
            "complete_file_bytes": len(payload),
            "complete_file_sha256": sha256(payload).hexdigest(),
            "hash_before_any_decode": True,
        }

    def fake_decode(_payload, station):
        assert materialized == ["ALGO00CAN", "MDO100USA"]
        decoded.append(station)
        return fixture(next(item for item in qualification.PRODUCTS if item.station == station))

    monkeypatch.setattr(qualification, "materialize", fake_materialize)
    monkeypatch.setattr(qualification, "decode_in_memory", fake_decode)
    monkeypatch.setattr(qualification, "_git_commit", lambda: "f" * 40)
    outcome = qualification.run_once(tmp_path, qualification.AUTHORITY_TOKEN)

    assert materialized == ["ALGO00CAN", "MDO100USA"]
    assert decoded == ["ALGO00CAN", "MDO100USA"]
    assert outcome["outcome"] == "GNSS_INDEPENDENT_PAIR_QUALIFICATION_PASSED"
    assert all(
        value == 0
        for value in outcome["future_primary_doy219_access"].values()
    )
    coverage = (tmp_path / qualification.COVERAGE_NAME).read_bytes()
    assert b'"value"' not in coverage and b"115000000" not in coverage


def test_wrong_authority_never_reaches_transport(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        qualification,
        "materialize",
        lambda _locator: pytest.fail("transport must remain closed"),
    )
    with pytest.raises(PermissionError, match="AUTHORITY_REQUIRED"):
        qualification.run_once(tmp_path, "wrong")


def test_receipt_failure_retains_physical_decision(monkeypatch, tmp_path) -> None:
    def fake_materialize(locator):
        payload = bytearray(locator.station.encode("ascii"))
        return payload, {
            "station": locator.station,
            "product": locator.name,
            "url": locator.url,
            "attempts": 1,
            "complete_file_bytes": len(payload),
            "complete_file_sha256": sha256(payload).hexdigest(),
            "hash_before_any_decode": True,
        }

    monkeypatch.setattr(qualification, "materialize", fake_materialize)
    monkeypatch.setattr(
        qualification,
        "decode_in_memory",
        lambda _payload, station: fixture(
            next(item for item in qualification.PRODUCTS if item.station == station)
        ),
    )
    monkeypatch.setattr(qualification, "_write_jsonl", lambda *_: (_ for _ in ()).throw(OSError("disk")))
    monkeypatch.setattr(qualification, "_git_commit", lambda: "f" * 40)

    with pytest.raises(
        qualification.DescriptionError,
        match=(
            "RECEIPT_WRITE_FAILED_PHYSICAL_DECISION_RETAINED:"
            "GNSS_INDEPENDENT_PAIR_QUALIFICATION_PASSED"
        ),
    ):
        qualification.run_once(tmp_path, qualification.AUTHORITY_TOKEN)


def test_strict_json_rejects_nonfinite_and_numpy_scalars() -> None:
    for value in (float("nan"), float("inf"), float("-inf"), np.bool_(True)):
        with pytest.raises((TypeError, ValueError)):
            qualification.strict_json({"bad": value})
    assert json.loads(qualification.strict_json(qualification.manifest())) == (
        qualification.manifest()
    )


def test_frozen_real_outcome_qualifies_without_primary_or_orbit_access() -> None:
    outcome = json.loads(
        (ROOT / qualification.OUTCOME_NAME).read_text(encoding="utf-8")
    )
    summary = json.loads(
        (ROOT / qualification.SUMMARY_NAME).read_text(encoding="utf-8")
    )

    assert outcome["outcome"] == "GNSS_INDEPENDENT_PAIR_QUALIFICATION_PASSED"
    assert outcome["source_commit"] == (
        "6410ab195b2b6b535bcb57c357fce5300e8fffae"
    )
    assert outcome["source_sha256"] == qualification.source_sha256()
    assert outcome["manifest_sha256"] == qualification.manifest_sha256()
    assert [
        (row["complete_file_bytes"], row["complete_file_sha256"])
        for row in outcome["artifacts"]
    ] == [
        (
            4_305_409,
            "339b4de652b3b9f1cbdf60804834fe97ff5dbf374e042e4871f5b761c5cfd821",
        ),
        (
            3_560_934,
            "fe7df3b7186519c108a192b2549f2b42f20fac353f6f38238db27b51164e0552",
        ),
    ]
    assert summary["structural_counts"] == {"PRESENT": 3336}
    assert summary["full_joint_window"] is True
    assert summary["same_path_code_witness"]["state"] == "SATISFIED"
    assert all(
        row["coverage_fraction"] == 1.0
        for row in summary["same_path_code_witness"]["links"]
    )
    assert summary["geometry_free_phase_health"]["state"] == "SATISFIED"
    assert max(
        row["maximum_absolute_second_difference_m"]
        for row in summary["geometry_free_phase_health"]["links"]
    ) == pytest.approx(0.022172391414642334)
    assert all(
        value == 0 for value in outcome["future_primary_doy219_access"].values()
    )
    assert outcome["orbital_prediction_access"] == 0
    assert outcome["orbital_scores_produced"] == 0
    assert outcome["persistence"]["observation_values"] == 0
    assert outcome["next_authority"] == "PRIMARY_SELECTION_REVIEW_ONLY"


def test_frozen_coverage_is_strict_structural_jsonl_only() -> None:
    path = ROOT / qualification.COVERAGE_NAME
    raw = path.read_bytes()
    rows = [json.loads(line) for line in raw.splitlines()]
    allowed = {
        "station",
        "gps_epoch",
        "satellite",
        "observable",
        "physical_role",
        "state",
        "header_declared_index",
        "reconstructed_field_count",
        "source_line_class",
        "continuation_state",
        "lli_state",
        "epoch_flag",
    }

    assert len(rows) == 3336
    assert all(set(row) == allowed for row in rows)
    assert b'"value"' not in raw
    assert b"NaN" not in raw and b"Infinity" not in raw
    assert sha256(raw).hexdigest() == (
        "544e1b6d584c3bb2e666d1cb5190743c60a9f2758bebd6fa4d656e714ad08b19"
    )
