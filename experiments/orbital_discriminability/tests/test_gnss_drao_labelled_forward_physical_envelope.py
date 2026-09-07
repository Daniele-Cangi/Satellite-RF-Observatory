"""Offline tests for the fixed DRAO DOY237 physical-envelope audit."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import (
    gnss_drao_labelled_forward_physical_envelope as audit,
)


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / audit.RECEIPT_NAME


def test_frozen_authority_and_manifest_have_zero_observation_surface() -> None:
    authority = audit.validate_frozen_authority(ROOT)
    assert authority["parent"]["rank"] == 1
    value = audit.manifest(ROOT)
    assert value["geometry"]["codebook"] == list(audit.CODEBOOK)
    assert value["geometry"]["nulls"] == [
        "PREFIX_AFFINE_ONLY",
        "TIME_REVERSED_GEOMETRY",
    ]
    assert set(value["observation_boundary"].values()) == {0}
    assert value["new_gate"] is False
    assert value["generic_framework"] is False


def test_grid_is_exactly_the_frozen_gps_window() -> None:
    epochs = audit.expected_utc_epochs()
    assert len(epochs) == 139
    assert (epochs[1] - epochs[0]).total_seconds() == 30.0
    assert epochs[0].isoformat() == "2026-08-25T04:54:42+00:00"
    assert epochs[-1].isoformat() == "2026-08-25T06:03:42+00:00"


def test_box_bound_matches_single_variable_linear_extremum() -> None:
    upper = np.zeros((len(audit.CODEBOOK), audit.screen.RAW_EPOCHS))
    upper[2, 17] = 2.5
    operator = audit.prefix_projection_operator()
    bound, by_satellite = audit.transformed_box_peak_to_peak_bound(
        upper, projection=operator
    )
    centering = np.eye(len(audit.CODEBOOK)) - np.ones(
        (len(audit.CODEBOOK), len(audit.CODEBOOK))
    ) / len(audit.CODEBOOK)
    heldout = range(audit.screen.PREFIX_EPOCHS, audit.screen.RAW_EPOCHS)
    expected = {}
    for target, satellite in enumerate(audit.CODEBOOK):
        expected[satellite] = max(
            abs(centering[target, 2])
            * abs(operator[17, left] - operator[17, right])
            * 2.5
            for left in heldout
            for right in range(left + 1, audit.screen.RAW_EPOCHS)
        )
    assert by_satellite == pytest.approx(expected)
    assert bound == pytest.approx(max(expected.values()))


def test_box_bound_rejects_nonfinite_or_negative_inputs() -> None:
    values = np.zeros((len(audit.CODEBOOK), audit.screen.RAW_EPOCHS))
    values[0, 0] = np.nan
    with pytest.raises(audit.DraoLabelledEnvelopeError, match="BOX_UPPER_INVALID"):
        audit.transformed_box_peak_to_peak_bound(values)
    values[0, 0] = -1.0
    with pytest.raises(audit.DraoLabelledEnvelopeError, match="BOX_UPPER_INVALID"):
        audit.transformed_box_peak_to_peak_bound(values)


def test_strict_json_rejects_nonfinite() -> None:
    with pytest.raises(ValueError):
        audit.strict_json({"bad": float("inf")})


def test_navigation_identity_is_checked_before_parsing() -> None:
    with pytest.raises(
        audit.DraoLabelledEnvelopeError,
        match="NAVIGATION_COMPRESSED_BYTES_CHANGED",
    ):
        audit.parse_navigation(b"not-the-frozen-navigation-product")


def test_audit_has_no_observation_transport_or_decoder() -> None:
    source = inspect.getsource(audit).casefold()
    for forbidden in (
        "requests.get",
        "urllib.request",
        "observation_locator",
        "hatanaka",
        "georinex",
    ):
        assert forbidden not in source


def test_conditional_reserve_is_not_claimed_as_observed() -> None:
    value = audit.manifest(ROOT)
    assert value["next_if_admitted"] == (
        "REVIEW_ONE_STRUCTURAL_ONLY_QUALIFICATION_CONTRACT"
    )
    assert audit.CAPABILITY_CONDITIONAL_RESERVE_M == pytest.approx(
        2506.0017238368006
    )


@pytest.mark.skipif(not RECEIPT.exists(), reason="receipt is produced only after frozen source")
def test_committed_receipt_is_strict_and_physically_consistent() -> None:
    value = json.loads(RECEIPT.read_text(encoding="ascii"))
    assert value["outcome"] in {audit.OUTCOME_ADMITTED, audit.OUTCOME_DOMINATES}
    assert value["geometry"]["retarded_controlling_null"] in {
        "PREFIX_AFFINE_ONLY",
        "TIME_REVERSED_GEOMETRY",
    }
    assert value["geometry"]["minimum_retarded_time_shifted_elevation_deg"] <= (
        value["geometry"]["minimum_retarded_nominal_elevation_deg"]
    )
    envelope = value["envelope"]
    assert envelope["required_separation_3b_m"] == pytest.approx(
        3.0 * envelope["one_model_bound_b_m"]
    )
    assert envelope["remaining_physical_margin_m"] == pytest.approx(
        envelope["retarded_controlling_separation_m"]
        - envelope["required_separation_3b_m"]
    )
    assert set(value["observation_access"].values()) == {0}
    assert value["navigation_payloads_retained"] == 0
    assert value["primary_selected"] is False
    assert value["prospective_plan_frozen"] is False
