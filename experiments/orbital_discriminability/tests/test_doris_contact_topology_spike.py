"""Tests for the offline DORIS contact-topology sufficiency spike."""

from __future__ import annotations

from hashlib import sha256
import inspect
import json
from pathlib import Path

import pytest

from experiments.orbital_discriminability import doris_contact_topology_spike as spike


RECEIPT = (
    Path(__file__).parents[1] / "DORIS_CONTACT_TOPOLOGY_SPIKE_RECEIPT.json"
)


def test_frozen_inputs_are_exact_and_parent_outcomes_are_preserved() -> None:
    inputs = spike.load_frozen_inputs()
    assert inputs["development_structure"]["outcome"] == (
        "DORIS_DEVELOPMENT_STRUCTURE_INSUFFICIENT"
    )
    assert inputs["exact_coepoch"]["outcome"] == (
        "DORIS_EXACT_COEPOCH_TOPOLOGY_QUALIFIED"
    )
    assert inputs["time_reference_geometry"]["outcome"] == (
        "DORIS_TIME_REFERENCE_TOPOLOGY_NO_JOINT_VISIBILITY"
    )
    assert inputs["development_structure"]["scanner"]["source_sha256"] == (
        spike.FROZEN_EXECUTED_SCANNER_SOURCE_SHA256
    )
    for name, path in {
        "development_header": spike.HEADER_RECEIPT,
        "development_structure": spike.STRUCTURAL_RECEIPT,
        "exact_coepoch": spike.COEPOCH_RECEIPT,
        "time_reference_geometry": spike.GEOMETRY_RECEIPT,
    }.items():
        assert spike.canonical_sha256(path) == spike.FROZEN_INPUT_HASHES[name]


def test_receipt_proves_retention_is_insufficient_for_contact_events() -> None:
    result = spike.build_spike()
    evidence = result["retained_evidence"]
    assert result["outcome"] == spike.OUTCOME
    assert evidence["header_declared_station_count"] == 56
    assert evidence["header_station_code_count"] == 56
    assert evidence["structurally_summarized_station_count"] == 4
    assert evidence["structurally_summarized_station_ids"] == [
        "D40",
        "D46",
        "D47",
        "D49",
    ]
    assert evidence["complete_all_station_presence_sequence_retained"] is False
    assert set(evidence["retained_longest_core_segment_count_by_station"].values()) == {
        5
    }
    assert evidence["segment_boundary_semantic"].endswith(
        "NOT_GEOMETRIC_RISE_SET"
    )
    assert spike.build_spike()["executed_structural_scanner"][
        "retention_rule_still_present_in_audited_current_source"
    ] is True


def test_positive_presence_and_negative_absence_are_not_conflated() -> None:
    clauses = spike.build_spike()["clause_evaluation"]
    assert clauses["positive_record_semantic"]["state"] == "PARTIALLY_SUPPORTED"
    assert clauses["negative_record_semantic"]["state"] == "UNRESOLVED"
    assert clauses["negative_record_semantic"]["consequence"] == (
        "ABSENCE_CANNOT_BE_MAPPED_TO_NOT_VISIBLE"
    )
    assert clauses["rise_set_event_identification"]["state"] == "NOT_RETAINED"
    assert clauses["finite_event_time_mapping"]["state"] == "UNRESOLVED"


def test_no_null_or_orbital_score_is_synthesized() -> None:
    result = spike.build_spike()
    assert result["scope"]["orbital_score"] == (
        "NOT_EVALUATED_INSUFFICIENT_EVENT_TOPOLOGY"
    )
    assert result["decision"]["retrospective_score_authorized"] is False
    assert result["decision"]["measurement_access_authorized"] is False
    assert result["decision"]["primary_selection_authorized"] is False
    assert all(
        state == "NOT_EVALUATED_INSUFFICIENT_EVENT_TOPOLOGY"
        for name, state in result["frozen_null_families"].items()
        if name != "common_reason"
    )


def test_hash_drift_stops_before_build(monkeypatch: pytest.MonkeyPatch) -> None:
    original = spike.canonical_sha256

    def changed(path: Path) -> str:
        if path == spike.STRUCTURAL_RECEIPT:
            return "0" * 64
        return original(path)

    monkeypatch.setattr(spike, "canonical_sha256", changed)
    with pytest.raises(
        spike.DorisContactTopologyError,
        match="FROZEN_RECEIPT_HASH_MISMATCH:development_structure",
    ):
        spike.load_frozen_inputs()


def test_spike_has_no_network_measurement_or_orbit_surface() -> None:
    source = inspect.getsource(spike)
    for forbidden in (
        "requests",
        "urllib",
        "ftplib",
        "subprocess",
        "spiceypy",
        "numpy",
        "scipy",
        "decompress",
        "parse_sp3",
    ):
        assert forbidden not in source
    assert "print(" not in source


def test_materialized_receipt_is_reproducible_source_bound_and_strict() -> None:
    actual = json.loads(RECEIPT.read_text(encoding="utf-8"))
    expected = json.loads(spike.strict_json(spike.build_spike()))
    assert actual == expected
    source = Path(spike.__file__).read_bytes().replace(b"\r\n", b"\n")
    assert actual["spike_source_sha256"] == sha256(source).hexdigest()
    encoded = spike.strict_json(actual)
    assert "NaN" not in encoded
    assert "Infinity" not in encoded
    assert actual["scope"]["observation_values_access"] == "ZERO"
