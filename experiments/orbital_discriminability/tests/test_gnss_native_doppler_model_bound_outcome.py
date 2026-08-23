from __future__ import annotations

import json
from pathlib import Path

from experiments.orbital_discriminability import gnss_native_doppler_model_bound as bound


ROOT = Path(__file__).parents[1]
RECEIPT = ROOT / "GNSS_NATIVE_DOPPLER_MODEL_BOUND_RECEIPT.json"


def load_receipt() -> dict[str, object]:
    return json.loads(
        RECEIPT.read_text(encoding="ascii"),
        parse_constant=lambda item: (_ for _ in ()).throw(ValueError(item)),
    )


def test_frozen_receipt_identity_and_outcome() -> None:
    receipt = load_receipt()
    assert bound.file_sha256(RECEIPT) == (
        "cfc43f90b3c8bfacf4003d47a1c33719f6ac866caf9dfbf18c4d0f27b64023f9"
    )
    assert receipt["outcome"] == "NATIVE_DOPPLER_BROADCAST_MODEL_BOUND_ADMITTED"
    assert receipt["compiler_manifest_sha256"] == bound.compiler_manifest_sha256()
    assert receipt["compiler_manifest"]["compiler_source_sha256"] == bound.file_sha256(
        Path(bound.__file__)
    )


def test_all_three_frozen_candidates_keep_positive_margin() -> None:
    receipt = load_receipt()
    rows = receipt["candidate_audits"]
    assert [row["doy"] for row in rows] == [219, 220, 221]
    assert all(row["broadcast_model_interval"]["admitted"] for row in rows)
    assert all(row["remaining_margin_hz"] > 4_000.0 for row in rows)
    assert all(
        satellite["selected_health_values"] == [0]
        for row in rows
        for satellite in row["satellite_audits"]
    )


def test_navigation_result_cannot_authorize_observation() -> None:
    receipt = load_receipt()
    assert receipt["authority"] == {
        "primary_observation_access_authorized": False,
        "primary_plan_frozen": False,
        "reserve_observation_access_authorized": False,
    }
    assert receipt["observation_access"] == {
        "bytes_opened": 0,
        "headers_opened": 0,
        "numeric_values_decoded": 0,
        "products_opened": 0,
    }
    assert receipt["new_gate_created"] is False
