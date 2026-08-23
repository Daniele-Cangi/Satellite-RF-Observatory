from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

import pytest

from experiments.orbital_discriminability import (
    gnss_structural_qualification as structural,
)


EPOCH = datetime(2026, 8, 3, 10, 1, 30, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "GNSS_STRUCTURAL_FAILURE_RECEIPT.json"
PARENT_OUTCOME = ROOT / "GNSS_DOUBLE_DIFFERENCE_MEASUREMENT_OUTCOME.json"
CONTRACT = ROOT / "GNSS_INDEPENDENT_QUALIFICATION_CONTRACT.md"


def header_line(data: str, label: str) -> str:
    return f"{data:<60}{label:<20}\n"


def field(token: str | None) -> str:
    if token is None:
        return " " * 16
    return f"{token:>14}  "


def fixture(
    observables: tuple[str, ...],
    fields: tuple[str | None, ...],
    *,
    data_continuation: tuple[str | None, ...] | None = None,
    header_continuation: bool = False,
) -> bytearray:
    if header_continuation:
        first, rest = observables[:13], observables[13:]
        type_lines = [
            header_line(
                f"G  {len(observables):3d} " + "".join(f"{item:>3} " for item in first),
                "SYS / # / OBS TYPES",
            ),
            header_line(
                "       " + "".join(f"{item:>3} " for item in rest),
                "SYS / # / OBS TYPES",
            ),
        ]
    else:
        type_lines = [
            header_line(
                f"G  {len(observables):3d} "
                + "".join(f"{item:>3} " for item in observables),
                "SYS / # / OBS TYPES",
            )
        ]
    lines = [
        header_line("     3.04           OBSERVATION DATA    G", "RINEX VERSION / TYPE"),
        *type_lines,
        header_line("", "END OF HEADER"),
        "> 2026 08 03 10 01 30.0000000  0  1\n",
        "G11" + "".join(field(value) for value in fields) + "\n",
    ]
    if data_continuation is not None:
        lines.append("   " + "".join(field(value) for value in data_continuation) + "\n")
    return bytearray("".join(lines).encode("ascii"))


def scan(payload: bytearray, observables: tuple[str, ...]) -> dict[str, object]:
    return structural.scan_plain_rinex_structure(
        payload,
        station="QUAL00TST",
        required_satellites=("G11",),
        required_observables=observables,
        window_start_gps=EPOCH,
        window_stop_gps=EPOCH,
    )


def last_state(receipt: dict[str, object]) -> str:
    return receipt["diagnostics"][-1]["typed_structural_state"]


def test_spec_variable_length_trailing_blank_is_omitted_not_truncated() -> None:
    observables = ("C1C", "L1C", "S1C", "C2W", "L2W", "S2W")
    receipt = scan(
        fixture(observables, ("22000000", "115000000", "45", "22000010", "89000000")),
        observables,
    )

    diagnostic = receipt["diagnostics"][-1]
    assert diagnostic == {
        "station": "QUAL00TST",
        "gps_epoch": "2026-08-03T10:01:30.000000Z",
        "satellite": "G11",
        "required_observable": "S2W",
        "header_declared_index": 5,
        "reconstructed_field_count": 5,
        "source_line_class": "RINEX_3_OBSERVATION_DATA_RECORD",
        "continuation_class": "SINGLE_LINE_VARIABLE_LENGTH_RECORD",
        "typed_structural_state": "TRAILING_FIELD_OMITTED",
    }
    assert receipt["observation_values_retained"] == 0
    assert receipt["orbital_scores_produced"] == 0


def test_existing_blank_field_is_distinct_from_omitted_trailing_field() -> None:
    observables = ("C1C", "L1C", "S1C", "C2W", "L2W", "S2W")
    receipt = scan(
        fixture(observables, ("22000000", "115000000", None, "22000010", "89000000", "43")),
        observables,
    )

    assert last_state(receipt) == "FIELD_BLANK"
    assert receipt["diagnostics"][-1]["required_observable"] == "S1C"


def test_header_absence_is_distinct_from_record_occupancy() -> None:
    declared = ("C1C", "L1C", "C2W", "L2W")
    required = declared + ("S2W",)
    receipt = structural.scan_plain_rinex_structure(
        fixture(declared, ("1", "2", "3", "4")),
        station="QUAL00TST",
        required_satellites=("G11",),
        required_observables=required,
        window_start_gps=EPOCH,
        window_stop_gps=EPOCH,
    )

    assert last_state(receipt) == "FIELD_ABSENT"
    assert receipt["diagnostics"][-1]["header_declared_index"] is None


def test_spec_header_continuation_is_supported() -> None:
    observables = (
        "C1C", "L1C", "D1C", "S1C", "C1W", "L1W", "D1W",
        "S1W", "C2W", "L2W", "D2W", "S2W", "C2L", "L2L",
    )
    receipt = scan(
        fixture(observables, tuple(str(index) for index in range(14)), header_continuation=True),
        observables,
    )

    states = [row["typed_structural_state"] for row in receipt["diagnostics"]]
    assert states == ["CONTINUATION_SUPPORTED"]
    assert receipt["diagnostics"][0]["required_observable"] == "L2L"
    assert receipt["state"] == "STRUCTURE_QUALIFIED"


def test_rinex3_observation_data_continuation_is_not_silently_joined() -> None:
    observables = ("C1C", "L1C", "S1C", "C2W")
    receipt = scan(
        fixture(
            observables,
            ("1", "2"),
            data_continuation=("3", "4"),
        ),
        observables,
    )

    assert last_state(receipt) == "CONTINUATION_UNSUPPORTED"
    assert receipt["diagnostics"][-1]["required_observable"] == "S1C"


def test_malformed_source_line_is_record_invalid() -> None:
    observables = ("C1C",)
    payload = fixture(observables, ("1",))
    marker = payload.index(b"G11")
    payload[marker : marker + 3] = b"???"

    receipt = scan(payload, observables)

    assert last_state(receipt) == "RECORD_INVALID"


def test_description_error_cannot_become_measurement_refusal() -> None:
    receipt = structural.description_error_receipt(
        "QUAL00TST", "STRICT_JSON_SERIALIZATION"
    )

    assert receipt["description_state"] == "DESCRIPTION_ERROR"
    assert receipt["measurement_admission_state"] == "NOT_EVALUATED"
    assert last_state(receipt) == "DESCRIPTION_ERROR"


def test_diagnostic_allowlist_excludes_observation_values() -> None:
    observables = ("C1C",)
    secret = "987654321.123"
    receipt = scan(fixture(observables, (secret,)), observables)
    encoded = structural.strict_json(receipt)

    assert secret not in encoded
    assert receipt["diagnostics"] == []
    assert receipt["state"] == "STRUCTURE_QUALIFIED"


def test_parent_outcome_and_forensic_roles_are_immutable() -> None:
    manifest = structural.parser_manifest()

    assert manifest["parent_terminal"] == [
        "MEASUREMENT_INVALID",
        "TRUNCATED_REQUIRED_OBSERVATION_RECORD",
    ]
    assert manifest["artifact_roles"] == [
        "FORENSIC_DEVELOPMENT_ONLY",
        "NEVER_PRIMARY_AGAIN",
        "NEVER_SCORED_AGAIN",
    ]
    assert manifest["rinex_semantics"]["trailing_empty_fields"] == "MAY_BE_OMITTED"
    assert json.loads(structural.strict_json(manifest)) == manifest


def test_timezone_naive_window_is_description_error() -> None:
    with pytest.raises(structural.StructuralDescriptionError):
        structural.format_gps_epoch(datetime(2026, 8, 3, 10, 1, 30))


def test_forensic_receipt_preserves_parent_and_exact_failure_boundary() -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))

    assert receipt["parent"] == {
        "outcome": "MEASUREMENT_INVALID",
        "reason": "TRUNCATED_REQUIRED_OBSERVATION_RECORD",
        "outcome_sha256": structural.PARENT_OUTCOME_SHA256,
    }
    canonical_lf = PARENT_OUTCOME.read_bytes().replace(b"\r\n", b"\n")
    assert sha256(canonical_lf).hexdigest() == (
        structural.PARENT_OUTCOME_SHA256
    )
    diagnostic = receipt["station_results"][1]["diagnostics"][0]
    assert set(diagnostic) == structural.DIAGNOSTIC_KEYS
    assert diagnostic["station"] == "NLIB00USA"
    assert diagnostic["gps_epoch"] == "2026-08-03T10:06:00.000000Z"
    assert diagnostic["satellite"] == "G21"
    assert diagnostic["required_observable"] == "C2W"
    assert diagnostic["header_declared_index"] == 5
    assert diagnostic["reconstructed_field_count"] == 3
    assert diagnostic["typed_structural_state"] == "TRAILING_FIELD_OMITTED"
    assert receipt["parser"]["manifest_sha256"] == (
        structural.parser_manifest_sha256()
    )
    assert receipt["outcome"] == "GNSS_FAILURE_TOPOLOGY_EXPLAINED"


def test_forensic_receipt_contains_no_value_or_score_surface() -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    encoded = structural.strict_json(receipt)

    assert receipt["access"]["observation_values_persisted"] == 0
    assert receipt["access"]["orbital_scores_produced"] == 0
    assert '"value"' not in encoded
    assert '"score"' not in encoded


def test_draft_contract_keeps_qualification_and_primary_distinct() -> None:
    contract = CONTRACT.read_text(encoding="utf-8")

    assert "DRAFT_NOT_EXECUTED" in contract
    assert "The qualification artifact can never become the primary" in contract
    assert "No contract outcome implies selection" in contract
    assert "`S1C` and `S2W` are optional diagnostics" in contract
