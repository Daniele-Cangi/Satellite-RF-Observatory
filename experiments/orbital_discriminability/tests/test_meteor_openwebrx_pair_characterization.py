from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from experiments.orbital_discriminability import (
    meteor_openwebrx_pair_characterization as probe,
)


def test_frozen_profiles_cover_carrier_and_roots_are_independent() -> None:
    assert len(probe.ENDPOINTS) == 2
    assert len({row.hardware_root for row in probe.ENDPOINTS}) == 2
    assert all(
        probe.profile_covers(
            row.declared_center_hz,
            row.declared_span_hz,
            probe.TARGET_CARRIER_HZ,
        )
        for row in probe.ENDPOINTS
    )


def test_wire_parser_accepts_current_and_legacy_descriptive_envelopes() -> None:
    assert probe.parse_wire_text(
        '{"type":"config","value":{"fft_size":4096}}'
    ) == ("config", {"fft_size": 4096})
    assert probe.parse_wire_text(
        'MSG {"type":"profiles","value":[]}'
    ) == ("profiles", [])
    assert probe.parse_wire_text("CLIENT DE SERVER server=openwebrx") == (
        "handshake",
        "CLIENT DE SERVER server=openwebrx",
    )


def test_wire_profile_label_accounts_for_official_sdr_prefix_only() -> None:
    assert probe.wire_profile_label_matches(
        "Airspy AIR 136 - 142", "AIR 136 - 142"
    )
    assert probe.wire_profile_label_matches(
        "[RTL] 24 MHz - 1.766 GHz", "24 MHz - 1.766 GHz"
    )
    assert not probe.wire_profile_label_matches(
        "Airspy AIR 130 - 136", "AIR 136 - 142"
    )


def test_profile_config_deltas_cannot_mix_old_coordinates_with_new_identity() -> None:
    target = "airspy|air-136-142"
    accumulated = {
        "sdr_id": "other",
        "profile_id": "old",
        "center_freq": 7_100_000,
        "samp_rate": 2_400_000,
        "fft_size": 4096,
    }
    seen_after_selection: set[str] = set()

    identity_delta = {"sdr_id": "airspy", "profile_id": "air-136-142"}
    accumulated.update(identity_delta)
    seen_after_selection.update(identity_delta)
    assert not probe.target_config_is_coherent(
        accumulated,
        target,
        fields_seen_after_selection=seen_after_selection,
    )

    center_delta = {"center_freq": 139_000_000}
    accumulated.update(center_delta)
    seen_after_selection.update(center_delta)
    assert not probe.target_config_is_coherent(
        accumulated,
        target,
        fields_seen_after_selection=seen_after_selection,
    )

    span_delta = {"samp_rate": 6_000_000}
    accumulated.update(span_delta)
    seen_after_selection.update(span_delta)
    assert probe.target_config_is_coherent(
        accumulated,
        target,
        fields_seen_after_selection=seen_after_selection,
    )


def test_initial_complete_target_snapshot_needs_no_transition_generation() -> None:
    assert probe.target_config_is_coherent(
        {
            "sdr_id": "rtlsdr",
            "profile_id": "airband",
            "center_freq": 137_000_000,
            "samp_rate": 2_400_000,
            "fft_size": 4096,
        },
        "rtlsdr|airband",
        fields_seen_after_selection=None,
    )


def test_frozen_window_guard_is_inclusive() -> None:
    assert not probe.outside_frozen_windows(
        datetime(2026, 8, 31, 12, 32, 25, tzinfo=timezone.utc)
    )
    assert probe.outside_frozen_windows(
        datetime(2026, 8, 31, 13, 0, 0, tzinfo=timezone.utc)
    )


def test_pair_remains_insufficient_without_event_time_sequence_and_witness() -> None:
    row = {
        "event_time": {"finite_sample_to_utc_bound": None},
        "sequence": {"sample_continuity": "UNKNOWN"},
        "same_path_witness": {"state": "NOT_AVAILABLE"},
    }
    assert probe.pair_outcome([row, row]) == "MEASUREMENT_PATH_INSUFFICIENT"


def test_live_description_failure_returns_receipt_not_physical_refusal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_with_receipt(endpoint, ready, websocket_module):
        del ready, websocket_module
        error = probe.CharacterizationError("TARGET_PROFILE_NOT_DELIVERED")
        error.receipt = {
            "schema": probe.SCHEMA,
            "capability_id": endpoint.capability_id,
            "state": "QUALIFICATION_ERROR",
            "subtype": "DESCRIPTION_ERROR",
            "failure": error.code,
            "downstream_measurement_admission": "NOT_EVALUATED",
            "measurement_decision": "UNCHANGED",
        }
        raise error

    monkeypatch.setattr(probe, "_run_endpoint", fail_with_receipt)
    monkeypatch.setattr(probe, "outside_frozen_windows", lambda instant: True)
    result = probe.run_live(object())

    assert result["outcome"] == "QUALIFICATION_ERROR"
    assert result["downstream_measurement_admission"] == "NOT_EVALUATED"
    assert result["measurement_decision"] == "UNCHANGED"
    assert len(result["failures"]) == 2
    probe.validate_receipt(result)


def test_receipt_forbids_rf_values_and_non_finite_json() -> None:
    with pytest.raises(ValueError, match="forbidden RF persistence"):
        probe.validate_receipt({"samples": [1, 2]})
    with pytest.raises(ValueError):
        probe.validate_receipt({"cadence": float("nan")})


def test_no_network_without_explicit_live_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["probe"])
    with pytest.raises(SystemExit, match="explicit --live"):
        probe.main()


def test_path_closure_preserves_endpoint_uncertainty_and_zero_rf_persistence() -> None:
    path = Path(probe.__file__).with_name("METEOR_OPENWEBRX_PATH_CLOSURE.json")
    closure = json.loads(path.read_text(encoding="utf-8"))

    assert closure["endpoint_capability_decision"] == "UNRESOLVED"
    assert closure["measurement_path_decision"] == "MEASUREMENT_PATH_INSUFFICIENT"
    assert closure["terminal_state"] == "OPENWEBRX_PATH_CLOSED"
    assert closure["measurement_decision_changed_by_description_error"] is False
    assert closure["rf_persistence"]["bytes_persisted"] == 0
    assert closure["rf_persistence"]["spectrum_bins_decoded"] == 0
    assert closure["replacement_route"]["metadata_scope"]["waterfalls_opened"] == 0
    assert closure["replacement_route"]["metadata_scope"]["audio_payloads_opened"] == 0
    assert closure["replacement_route"]["primary_pair_selected"] is False
    assert closure["replacement_route"]["prospective_plan_frozen"] is False
