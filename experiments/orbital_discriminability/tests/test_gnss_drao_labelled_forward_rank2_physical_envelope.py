from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from experiments.orbital_discriminability import (
    gnss_drao_labelled_forward_rank2_physical_envelope as audit,
)


ROOT = Path(__file__).resolve().parents[1]


def test_frozen_rank2_is_selected_from_pre_observation_shortlist() -> None:
    authority = audit.validate_frozen_authority(ROOT)

    assert authority["parent"]["rank"] == 2
    assert authority["selection_rule"] == (
        "HIGHEST_RANKED_UNCONSUMED_GEOMETRY_FROM_PRE_OBSERVATION_SHORTLIST"
    )
    assert authority["doy237_reopened"] is False
    manifest = audit.manifest(ROOT)
    assert manifest["geometry"] == {
        "station": "DRAO00CAN",
        "doy": 238,
        "gps_date": "2026-08-26",
        "codebook": ["G14", "G15", "G17", "G20", "G24", "G30"],
        "raw_start_gps": "2026-08-26T04:50:00 GPS",
        "raw_stop_gps": "2026-08-26T05:59:00 GPS",
        "heldout_start_gps": "2026-08-26T05:29:30 GPS",
        "prefix_epochs": 79,
        "raw_epochs": 139,
    }
    assert set(manifest["observation_access"].values()) == {0}


def test_grid_is_exact_and_retains_frozen_gps_event_time_semantics() -> None:
    epochs = audit.expected_utc_epochs()

    assert len(epochs) == 139
    assert (epochs[-1] - epochs[0]) == timedelta(seconds=4_140)
    assert (epochs[1] - epochs[0]) == timedelta(seconds=30)


def test_wrong_navigation_identity_is_refused_before_parse() -> None:
    with pytest.raises(
        audit.Rank2EnvelopeError, match="NAVIGATION_COMPRESSED_BYTES_CHANGED"
    ):
        audit.parse_navigation(b"not the exact navigation product")


def test_scope_or_parent_change_is_a_typed_refusal(tmp_path: Path) -> None:
    for name in (audit.SCOPE_NAME, audit.PARENT_NAME):
        (tmp_path / name).write_bytes((ROOT / name).read_bytes())
    (tmp_path / audit.SCOPE_NAME).write_text("changed", encoding="ascii")

    with pytest.raises(audit.Rank2EnvelopeError, match="FROZEN_SCOPE_CHANGED"):
        audit.validate_frozen_authority(tmp_path)
