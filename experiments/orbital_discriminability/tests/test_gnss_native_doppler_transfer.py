from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import gnss_native_doppler_transfer as transfer


ROOT = Path(__file__).parents[1]
RECEIPT = ROOT / "GNSS_NATIVE_DOPPLER_TRANSFER_RECEIPT.json"


def test_path_projection_is_conservative_and_numerically_frozen() -> None:
    coefficient = transfer.projection_gain_hz_per_path_m()
    assert coefficient == pytest.approx(40.63775321596158, abs=1e-12)
    assert coefficient > 0.0


def test_transfer_contract_uses_relative_same_path_health_not_invented_snr() -> None:
    contract = transfer.transfer_contract()
    assert contract["snr_policy"]["absolute_db_hz_threshold"] is None
    assert contract["snr_policy"]["development_minimum_2_25_db_hz_promoted_to_threshold"] is False
    assert contract["heldout_health_clauses"]["same_link_snr_not_below_its_prefix_minimum"] == "REQUIRED"
    assert contract["post_freeze_retry"] == 0


def test_model_bound_is_not_silently_filled_by_illustrative_value() -> None:
    candidate = {
        "prospective_role": "primary_candidate",
        "doy": 219,
        "target": "G15",
        "reference": "G22",
        "start_observation_epoch_gps": "start",
        "stop_observation_epoch_gps": "stop",
        "remaining_after_direct_clock_envelope_hz": 6743.536574359732,
        "minimum_elevation_across_stations_and_clock_shifts_deg": 15.049791272672596,
    }
    result = transfer.audit_candidate(candidate)
    assert result["broadcast_orbit_bound_state"] == "UNRESOLVED_IN_FROZEN_RECEIPTS"
    assert result["actual_negative_result_interpretable"] is False
    assert result["illustrative_not_admitted_4m_bound"]["may_satisfy_contract"] is False
    assert result["maximum_admissible_broadcast_orbit_per_link_path_bound_m"] == pytest.approx(64.95017630223762, abs=1e-9)
    assert result["illustrative_not_admitted_4m_bound"]["remaining_margin_hz"] > 4_900.0


def test_real_frozen_receipts_produce_conditional_transfer_not_primary_authority() -> None:
    result = transfer.compile_transfer(ROOT)
    assert result["outcome"] == "NATIVE_DOPPLER_TRANSFER_RULE_FROZEN_MODEL_BOUND_REQUIRED"
    assert len(result["candidate_audits"]) == 3
    assert all(item["conditional_negative_result_interpretable"] for item in result["candidate_audits"])
    assert all(not item["actual_negative_result_interpretable"] for item in result["candidate_audits"])
    assert result["broadcast_model_admission"]["unresolved_as_zero"] is False
    assert result["authority"]["primary_plan_frozen"] is False
    assert result["observation_access"]["bytes_opened"] == 0
    assert transfer.strict_json(result)


def test_strict_json_refuses_numpy_and_nonfinite_scalars() -> None:
    with pytest.raises(TypeError):
        transfer.strict_json({"bad": np.float64(1.0)})
    with pytest.raises(ValueError):
        transfer.strict_json({"bad": float("inf")})


def test_lineage_hash_failure_precedes_compilation(tmp_path: Path) -> None:
    for name in (
        transfer.ORBITALITY_RECEIPT_NAME,
        transfer.DEVELOPMENT_RECEIPT_NAME,
        transfer.TRANSFORM_MANIFEST_NAME,
    ):
        (tmp_path / name).write_text("{}", encoding="ascii")
    with pytest.raises(transfer.TransferAuditError, match="FROZEN_LINEAGE_MISMATCH"):
        transfer.compile_transfer(tmp_path)


def test_manifest_has_physical_information_gain_and_no_new_gate() -> None:
    manifest = transfer.compiler_manifest()
    assert "MAXIMUM_ADMISSIBLE_BROADCAST_ORBIT_PATH_ERROR" in manifest["new_information"]
    assert manifest["observation_access_forbidden"] is True
    assert manifest["new_gate_created"] is False
    json.loads(transfer.strict_json(manifest))


def test_frozen_transfer_receipt_is_byte_exact_and_matches_compiler() -> None:
    receipt = json.loads(
        RECEIPT.read_text(encoding="ascii"),
        parse_constant=lambda item: (_ for _ in ()).throw(ValueError(item)),
    )
    assert transfer.file_sha256(RECEIPT) == (
        "16e15a2e91712429ebb27f374558d2ab04e1a28b5e376a6317c753ed47055ebb"
    )
    assert receipt == transfer.compile_transfer(ROOT)
    assert receipt["compiler_manifest"]["compiler_source_sha256"] == (
        transfer.file_sha256(Path(transfer.__file__))
    )
    assert receipt["broadcast_model_admission"]["state"] == "UNRESOLVED"
