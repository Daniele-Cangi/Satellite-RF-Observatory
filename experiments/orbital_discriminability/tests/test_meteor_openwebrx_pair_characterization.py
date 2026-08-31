from __future__ import annotations

from datetime import datetime, timezone

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


def test_receipt_forbids_rf_values_and_non_finite_json() -> None:
    with pytest.raises(ValueError, match="forbidden RF persistence"):
        probe.validate_receipt({"samples": [1, 2]})
    with pytest.raises(ValueError):
        probe.validate_receipt({"cadence": float("nan")})


def test_no_network_without_explicit_live_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["probe"])
    with pytest.raises(SystemExit, match="explicit --live"):
        probe.main()
