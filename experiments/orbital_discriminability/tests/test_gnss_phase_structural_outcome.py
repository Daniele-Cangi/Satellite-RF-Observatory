from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from experiments.orbital_discriminability import gnss_phase_structural_scan as scan


ROOT = Path(__file__).resolve().parents[1]
COVERAGE = ROOT / scan.COVERAGE_NAME
SUMMARY = ROOT / scan.SUMMARY_NAME
OUTCOME = ROOT / scan.OUTCOME_NAME
REPORT = ROOT / "GNSS_PHASE_STRUCTURE_REPORT.md"
ROW_KEYS = {
    "station",
    "gps_epoch",
    "satellite",
    "observable",
    "physical_role",
    "header_declared_index",
    "reconstructed_field_count",
    "source_line_class",
    "header_line_class",
    "continuation_class",
    "state",
    "lli_state",
}


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def coverage_rows() -> list[dict[str, object]]:
    return [json.loads(line) for line in COVERAGE.read_text().splitlines()]


def test_outcome_is_bound_to_preaccess_commit_and_exact_artifacts() -> None:
    outcome = json.loads(OUTCOME.read_text())

    assert outcome["outcome"] == "GNSS_PHASE_STRUCTURE_REJECTED"
    assert outcome["source_commit"] == "a5033c9ce84c483fea9ebd43c75918a3dec9cf32"
    assert outcome["manifest_sha256"] == scan.manifest_sha256()
    assert [(row["complete_file_bytes"], row["complete_file_sha256"]) for row in outcome["artifacts"]] == [
        (2_197_783, "286babf58a11d8a87c8b72a07f7fd1de03c8cd0fa844afa8d571a25ddf2eeb21"),
        (2_551_870, "a0ae412ed32b31e31aa879cebab43a8c1c9329cc106eac5a44631a88bdf347c8"),
    ]
    assert all(row["attempts"] == 1 for row in outcome["artifacts"])
    assert all(row["hash_before_decompression"] is True for row in outcome["artifacts"])


def test_all_9264_rows_are_value_blind_and_strict() -> None:
    rows = coverage_rows()

    assert len(rows) == 9_264
    assert all(set(row) == ROW_KEYS for row in rows)
    assert Counter(row["state"] for row in rows) == {
        "PRESENT": 9_022,
        "BLANK": 122,
        "TRAILING_FIELD_OMITTED": 120,
    }
    encoded = COVERAGE.read_text()
    assert '"value"' not in encoded
    assert "NaN" not in encoded
    assert "Infinity" not in encoded


def test_failure_is_nlib_topology_not_parser_or_description() -> None:
    summary = json.loads(SUMMARY.read_text())

    assert summary["parser_issues"] == []
    assert summary["full_joint_window"] is False
    assert summary["same_path_code_witness"]["state"] == "UNSATISFIED"
    gold = [row for row in summary["per_link_core_segments"] if row["station"] == "GOLD00USA"]
    nlib = [row for row in summary["per_link_core_segments"] if row["station"] == "NLIB00USA"]
    assert all(row["full_window"] for row in gold)
    assert all(not row["full_window"] for row in nlib)
    assert max(segment["epoch_count"] for segment in summary["joint_core_segments"]) == 282


def test_physical_clauses_and_primary_remain_unopened() -> None:
    outcome = json.loads(OUTCOME.read_text())
    summary = json.loads(SUMMARY.read_text())

    assert outcome["clause_states"]["geometry_free_phase_health"] == "NOT_EVALUATED"
    assert outcome["clause_states"]["measurement_admission"] == "NOT_EVALUATED"
    assert outcome["clause_states"]["orbital_score"] == "NOT_EVALUATED"
    assert outcome["primary_doy220_access"] == {"headers": 0, "payload_bytes": 0, "values": 0}
    assert outcome["persistence"] == {
        "compressed_artifact_bytes": 0,
        "decoded_observation_bytes": 0,
        "observation_values": 0,
        "structural_receipts_only": True,
    }
    assert summary["observation_values_parsed"] == 0
    assert summary["observation_values_persisted"] == 0


def test_receipt_hashes_and_report_are_exact() -> None:
    outcome = json.loads(OUTCOME.read_text())
    report = REPORT.read_text()

    assert file_sha256(COVERAGE) == outcome["coverage"]["sha256"]
    assert file_sha256(SUMMARY) == outcome["summary"]["sha256"]
    assert file_sha256(OUTCOME) == "7b7efb4fc3fb81e029f85bebde1e9f53520a49ffb9f5909a200ea4da4ec571d8"
    assert "GNSS_PHASE_STRUCTURE_REJECTED" in report
    assert "Geometry-free phase health is not structural" not in report
    assert "Observation scalars parsed or persisted: zero" in report
