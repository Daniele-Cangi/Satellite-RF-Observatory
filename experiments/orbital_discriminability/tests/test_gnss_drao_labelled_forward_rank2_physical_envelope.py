from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
import json
from pathlib import Path

import pytest

from experiments.orbital_discriminability import (
    gnss_drao_labelled_forward_rank2_physical_envelope as audit,
)


ROOT = Path(__file__).resolve().parents[1]
OUTCOME = ROOT / "GNSS_DRAO_LABELLED_FORWARD_RANK2_PHYSICAL_ENVELOPE.json"


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


def test_frozen_real_outcome_has_positive_exact_margin_and_zero_observation() -> None:
    value = json.loads(
        OUTCOME.read_text(encoding="ascii"),
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )

    assert sha256(OUTCOME.read_bytes()).hexdigest() == (
        "211542ab506e109e91aba754ad93ff32acab451e74d14ab1d4e42d5a9f36beb1"
    )
    assert value["outcome"] == audit.OUTCOME_ADMITTED
    assert value["source_commit"] == "e5a7b2b470530ac8920a2c57f5ccfe9a7e4c3a0c"
    envelope = value["envelope"]
    assert envelope["retarded_controlling_separation_m"] == pytest.approx(
        36_418.37342430651, abs=1.0e-9
    )
    assert envelope["required_separation_3b_m"] == pytest.approx(
        11_914.942466424636, abs=1.0e-9
    )
    assert envelope["remaining_physical_margin_m"] == pytest.approx(
        24_503.430957881876, abs=1.0e-9
    )
    assert set(value["observation_access"].values()) == {0}
    assert value["navigation_payloads_retained"] == 0
    assert value["primary_selected"] is False
