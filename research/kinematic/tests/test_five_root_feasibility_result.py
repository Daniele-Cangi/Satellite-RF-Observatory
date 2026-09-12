"""Exact frozen-result checks for the target-free five-root audit."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT/"research/kinematic/five_root_feasibility_plan.json"
RESULT = ROOT/"research/kinematic/results/s2_five_root_feasibility_v1.json"


def test_frozen_result_identity_and_boundaries():
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    assert result["status"] == "FIVE_ROOT_PROSPECTIVE_VERTICAL_INCOMPLETE"
    assert result["freeze"] == {
        "plan_sha256": hashlib.sha256(PLAN.read_bytes()).hexdigest(),
        "source_commit": "09a7273a648c9a0eb6398da7c7924f08e1652f41",
    }
    assert result["input_boundaries"] == {
        "fit_root_count": 5,
        "independent_heldout_root_count": 0,
        "new_network_access": False,
        "real_observation_values_read": False,
        "station_coordinate_source_sha256": "f9ff6db885f250112cf33a307ebde753be1e40847d4460904ece28fec15c24c6",
        "target_state_or_orbit_used": False,
    }


def test_frozen_result_keeps_failed_clauses_and_all_cases():
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    assert result["synthetic_case_accounting"] == {
        "generated": 2304,
        "joint_visible": 181,
        "phase_model_rank_failures": 0,
        "rejected_by_joint_visibility": 2123,
    }
    assert len(result["cases"]) == 181
    assert result["clauses"] == {
        "CONDITIONAL_LOCAL_MARGIN": "NOT_SATISFIED",
        "INDEPENDENT_HELDOUT_ROOT": "UNSATISFIED",
        "LOCAL_FIT_IDENTIFIABILITY": "SATISFIED",
        "TOTAL_PHYSICAL_ERROR_ENVELOPE": "UNRESOLVED",
    }
    envelopes = [case["code_and_interval_phase"]["position"]["t_plus_60_s"]["conditional_local_position_envelope_m"]
                 for case in result["cases"]]
    assert sum(value <= 10000 for value in envelopes) == 65
    assert min(envelopes) == 501.35265049987163
    assert max(envelopes) == 83332.01366600442


def test_frozen_source_hashes_match_checkout():
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    for name, expected in result["sources_sha256"].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == expected
