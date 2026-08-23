from hashlib import sha256
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTCOME = ROOT / "GNSS_INDEPENDENT_PRIMARY_OUTCOME.jsonl"
MATERIALIZATION = (
    ROOT / "GNSS_INDEPENDENT_PRIMARY_MATERIALIZATION_RECEIPT.json"
)


def load_strict(path: Path) -> dict[str, object]:
    return json.loads(
        path.read_text(encoding="ascii"),
        parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError(value)
        ),
    )


def test_terminal_outcome_hash_and_failure_boundary() -> None:
    raw = OUTCOME.read_bytes()
    assert sha256(raw).hexdigest() == (
        "5e4e54c1cae1f431eacc8101bb995de18c548e4ea7dcb46a71313517e90ea02b"
    )
    receipt = load_strict(OUTCOME)
    assert receipt["outcome"] == "MEASUREMENT_INVALID"
    assert receipt["reason"] == "GEOMETRY_FREE_PHASE_DISCONTINUITY"
    assert receipt["decompression_started"] is True
    assert receipt["alternate_run_authorized"] is False
    assert receipt["clauses"]["calibration_detectability"] == (
        "NOT_EVALUATED"
    )
    assert receipt["clauses"]["heldout_model_comparison"] == (
        "NOT_EVALUATED"
    )
    assert receipt["raw_or_derived_measurement_persisted"] is False


def test_materialization_hashes_are_frozen_without_rf_persistence() -> None:
    receipt = load_strict(MATERIALIZATION)
    assert receipt["hashes_completed_before_decompression"] is True
    assert receipt["primary_decompression_bytes_before_receipt"] == 0
    assert [item["sha256"] for item in receipt["artifacts"]] == [
        "e65de2fe6db79a9908a87ee7892f75558601c9bd28edd98fd61e22a21b4812f2",
        "48a973ae7ad1f365553c590337fc5ea838bc06a9db6d567417109f2dde0ad65f",
    ]
    assert receipt["quarantine_policy"][
        "raw_or_decompressed_products_persisted_in_repository"
    ] is False
