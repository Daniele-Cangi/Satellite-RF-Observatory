from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).parents[1]
QUALIFICATION = ROOT / "GNSS_INDEPENDENT_QUALIFICATION_RECEIPT.json"
TRANSFER = ROOT / "GNSS_NATIVE_DOPPLER_TRANSFER_RECEIPT.json"
PRIMARY = ROOT / "GNSS_NATIVE_DOPPLER_PRIMARY_OUTCOME.jsonl"
SOURCE = ROOT / "gnss_native_doppler_primary.py"
AUDIT = ROOT / "GNSS_NATIVE_DOPPLER_HEALTH_WITNESS_AUDIT.md"


def load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="ascii"))


def test_exact_receiver_and_rinex_health_lineage_is_preserved() -> None:
    receipt = load(QUALIFICATION)
    headers = {item["station_id"]: item for item in receipt["header_evidence"]}
    assert headers["KIRU00SWE"]["receiver"] == {
        "serial": "4701570",
        "type": "SEPT POLARX5TR",
        "version_or_radome": "5.6.0",
    }
    assert headers["KIRU00SWE"]["rinex_version"] == 4.01
    assert headers["MAT100ITA"]["receiver"] == {
        "serial": "1705344",
        "type": "LEICA GR30",
        "version_or_radome": "4.83/7.900",
    }
    assert headers["MAT100ITA"]["rinex_version"] == 3.04
    assert {item["signal_strength_unit"] for item in headers.values()} == {"DBHZ"}


def test_qualification_and_primary_parser_did_not_retain_lli_or_ssi() -> None:
    receipt = load(QUALIFICATION)
    access = receipt["measurement_access"]
    assert access["lli_values_decoded"] == 0
    assert access["ssi_values_decoded"] == 0

    source = SOURCE.read_text(encoding="utf-8")
    scalar_parser = source.split("def _parse_scalar", 1)[1].split(
        "def validate_station", 1
    )[0]
    assert "field[:14]" in scalar_parser
    assert "field[14" not in scalar_parser
    assert "field[15" not in scalar_parser


def test_audit_refuses_to_invent_a_doppler_health_threshold() -> None:
    text = AUDIT.read_text(encoding="utf-8")
    assert "GNSS_DOPPLER_HEALTH_WITNESS_BOUND_UNAVAILABLE" in text
    assert "BLOCKED_BY_DOPPLER_HEALTH_PROVENANCE" in text
    assert "30 dB-Hz cutoff" in text
    assert "would be post-outcome" in text
    assert "DOY_219_ORBITAL_HYPOTHESIS: NOT_EVALUATED" in text


def test_reserve_remains_unauthorized_and_primary_unscored() -> None:
    transfer = load(TRANSFER)
    primary = load(PRIMARY)
    assert transfer["authority"]["reserve_observation_access_authorized"] is False
    assert primary["scores"] == {}
    assert primary["preference_margins_hz"] == {}
