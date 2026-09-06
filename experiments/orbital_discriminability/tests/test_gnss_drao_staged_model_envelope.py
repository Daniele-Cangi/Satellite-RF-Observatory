"""Offline tests for the staged DRAO model-side compiler."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import (
    gnss_drao_staged_model_envelope as staged,
)


ROOT = Path(__file__).resolve().parents[1]


def test_scope_is_bound_and_closed_roles_are_not_reused() -> None:
    authority = staged._validate_scope(ROOT)

    assert authority["scope"]["canonical_sha256"] == staged.SCOPE_SHA256
    assert authority["closed_audit"]["outcome"] == (
        "DRAO_PHYSICAL_ENVELOPE_NOT_ADMITTED"
    )
    assert authority["closed_audit"]["reopened"] is False
    assert staged.QUALIFICATION_DOY == 232
    assert staged.PRIMARY_DOY == 233


def test_unused_primary_grid_is_exact() -> None:
    epochs = staged.expected_utc_epochs()

    assert len(epochs) == 139
    assert (epochs[1] - epochs[0]).total_seconds() == 30.0
    assert staged.geometry.format_gps(epochs[0]) == "2026-08-21T01:14:30 GPS"
    assert staged.geometry.format_gps(epochs[-1]) == "2026-08-21T02:23:30 GPS"


def test_earth_rotation_transform_preserves_radius() -> None:
    vector = np.asarray([20_000_000.0, -13_000_000.0, 9_000_000.0])
    rotated = staged._rotate_transmit_ecef_to_receive_ecef(vector, 0.075)

    assert np.linalg.norm(rotated) == pytest.approx(np.linalg.norm(vector))
    assert not np.array_equal(rotated, vector)


def test_conditional_reserve_requires_complete_witness() -> None:
    assert staged.CONDITIONAL_RESERVE_M == pytest.approx(2_506.0017238368005)
    assert staged.GUARD_M > staged.CONDITIONAL_RESERVE_M
    assert staged.CONDITIONAL_COMPLETE_CODE_WITNESS_M == 2_500.0


def test_wrong_navigation_identity_is_refused() -> None:
    with pytest.raises(
        staged.DraoStagedEnvelopeError,
        match="NAVIGATION_COMPRESSED_IDENTITY_CHANGED",
    ):
        staged.parse_navigation(b"not the frozen navigation")


def test_source_has_no_observation_or_network_surface() -> None:
    source = inspect.getsource(staged).lower()
    for forbidden in (
        "import requests",
        "import urllib",
        "import socket",
        "observation-gzip",
        "phase_values",
        "code_values",
        "product_url",
    ):
        assert forbidden not in source


def test_persisted_result_is_model_only_if_present() -> None:
    path = ROOT / staged.RECEIPT_NAME
    if not path.exists():
        pytest.skip("model-side receipt is created only after the scope commit")
    value = json.loads(path.read_text(encoding="ascii"))

    assert value["outcome"] in {staged.OUTCOME_ADMITTED, staged.OUTCOME_BLOCKED}
    assert set(value["observation_access"].values()) == {0}
    assert value["navigation_payloads_retained"] == 0
    assert value["orbital_scores_produced"] == 0
    assert value["prospective_primary_plan_frozen"] is False
    assert value["retained_model_curves_sha256"] == staged.sha256(
        staged.strict_json(value["retained_model_curves"]).encode("ascii")
    ).hexdigest()
