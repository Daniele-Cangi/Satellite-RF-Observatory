from __future__ import annotations

import json
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
OUTCOME = ROOT / "GNSS_NATIVE_DOPPLER_PRIMARY_OUTCOME.jsonl"
POSTMORTEM = ROOT / "GNSS_NATIVE_DOPPLER_PRIMARY_POSTMORTEM.md"


def receipt() -> dict[str, object]:
    return json.loads(OUTCOME.read_text(encoding="ascii"))


def test_exact_failed_streams_are_descriptive_not_orbital_scores() -> None:
    value = receipt()
    prefix = value["same_path_health"]["prefix_snr_minima_db_hz"]
    heldout = value["same_path_health"]["heldout_snr_minima_db_hz"]
    failed = {name for name in prefix if heldout[name] < prefix[name]}
    assert failed == {
        "KIRU00SWE:G15:S1C",
        "KIRU00SWE:G15:S2W",
        "MAT100ITA:G22:S1C",
        "MAT100ITA:G22:S2W",
    }
    assert value["scores"] == {}
    assert value["preference_margins_hz"] == {}


def test_unequal_window_minimum_rule_has_twenty_percent_exchangeable_pass_rate() -> None:
    value = receipt()
    prefix_records = value["calibration_records"]
    total_records = value["records"]
    per_stream_pass = prefix_records / total_records
    assert per_stream_pass == pytest.approx(0.2)
    assert per_stream_pass**8 == pytest.approx(0.00000256)


def test_postmortem_preserves_outcome_and_refuses_causal_overclaim() -> None:
    text = POSTMORTEM.read_text(encoding="utf-8")
    assert "FROZEN_RUNTIME_OUTCOME: NOT_DETECTABLE" in text
    assert "SENSOR_DEGRADATION_ATTRIBUTION: INCONCLUSIVE" in text
    assert "ORBITAL_HYPOTHESIS_RESULT: NOT_EVALUATED" in text
    assert "NOT_FALSIFIABLE_WITH_THIS_RECEIPT" in text
    assert "DOY 219 primary must not be rescored" in text
