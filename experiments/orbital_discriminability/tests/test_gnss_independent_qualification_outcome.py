from __future__ import annotations

import json
from pathlib import Path

from experiments.orbital_discriminability import gnss_independent_qualification as qualification


ROOT = Path(__file__).resolve().parents[1]
OUTCOME = ROOT / qualification.OUTCOME_NAME
COVERAGE = ROOT / qualification.COVERAGE_NAME
SUMMARY = ROOT / qualification.SUMMARY_NAME
HISTORICAL_OUTCOME = ROOT / "GNSS_DOUBLE_DIFFERENCE_MEASUREMENT_OUTCOME.json"


def test_frozen_real_qualification_failure_is_complete_and_value_free() -> None:
    outcome = json.loads(OUTCOME.read_text(encoding="ascii"))
    summary = json.loads(SUMMARY.read_text(encoding="ascii"))
    rows = [json.loads(line) for line in COVERAGE.read_text(encoding="ascii").splitlines()]

    assert outcome["outcome"] == "GNSS_INDEPENDENT_QUALIFICATION_FAILED"
    assert outcome["primary_selected"] is False
    assert outcome["primary_accessed"] is False
    assert outcome["orbital_measurement_performed"] is False
    assert outcome["artifact_persistence"] == {"compressed_rinex": 0, "decoded_rinex": 0, "observation_values": 0}
    assert outcome["plan"]["sha256"] == qualification.PLAN_SHA256
    assert outcome["coverage"]["rows"] == 9_264 == len(rows)
    assert outcome["coverage"]["sha256"] == qualification.canonical_text_sha256(COVERAGE)
    assert outcome["summary"]["sha256"] == qualification.canonical_text_sha256(SUMMARY)
    assert all("value" not in row and "phase" not in row for row in rows)
    identities = {(row["station"], row["gps_epoch"], row["satellite"], row["observable"]) for row in rows}
    assert len(identities) == len(rows)
    assert set(row["state"] for row in rows) <= set(qualification.FIELD_STATES)
    assert summary["structural_counts"] == {
        "BLANK": 162,
        "PRESENT": 9_102,
        "TRAILING_FIELD_OMITTED": 0,
        "CONTINUATION_SUPPORTED": 0,
        "CONTINUATION_UNSUPPORTED": 0,
        "RECORD_INVALID": 0,
    }


def test_real_failure_is_attributed_to_predeclared_nlib_g21_cuts() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="ascii"))
    rows = [json.loads(line) for line in COVERAGE.read_text(encoding="ascii").splitlines()]
    missing = [row for row in rows if row["station"] == "NLIB00USA" and row["satellite"] == "G21" and row["state"] == qualification.BLANK]
    acquisition = [row for row in rows if row["station"] == "NLIB00USA" and row["satellite"] == "G21" and row["gps_epoch"] == "2026-08-02T10:19:00.000000Z" and row["observable"] in qualification.CORE_PHASE]

    assert len(missing) == 27 * len(qualification.RELEVANT_OBSERVABLES)
    assert {row["source_line_class"] for row in missing} == {"SATELLITE_RECORD_ABSENT"}
    assert {row["lli_state"] for row in acquisition} == {"NONZERO"}
    assert summary["joint_maximal_segments"] == [{
        "start_gps": "2026-08-02T10:19:30.000000Z",
        "stop_gps": "2026-08-02T13:18:00.000000Z",
        "epoch_count": 358,
        "duration_s": 10_710.0,
    }]
    assert summary["full_joint_window"] is False
    assert summary["same_path_code_witness"]["state"] == "UNSATISFIED"
    assert summary["geometry_free_phase_continuity"]["state"] == "UNSATISFIED"


def test_historical_gold_nlib_terminal_receipt_remains_canonical_byte_exact() -> None:
    assert qualification.canonical_text_sha256(HISTORICAL_OUTCOME) == (
        "4060e8e3046696f6433ce5226e3d7f524d430cbbd49261fd1041554ab76b5172"
    )
    receipt = json.loads(HISTORICAL_OUTCOME.read_text(encoding="ascii"))
    assert receipt["outcome"] == "MEASUREMENT_INVALID"
    assert receipt["clauses"]["reason"] == "TRUNCATED_REQUIRED_OBSERVATION_RECORD"
