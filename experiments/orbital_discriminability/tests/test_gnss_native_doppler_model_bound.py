from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import gnss_double_difference_screen as screen
from experiments.orbital_discriminability import gnss_native_doppler_model_bound as bound


ROOT = Path(__file__).parents[1]


def ephemeris(satellite: str = "G15", **changes: object) -> screen.GpsEphemeris:
    record = screen.GpsEphemeris(
        satellite=satellite,
        toc_gps=datetime(2026, 8, 7, 16, tzinfo=timezone.utc),
        af0_s=0.0,
        af1_s_s=0.0,
        af2_s_s2=0.0,
        iode=1.0,
        crs_m=0.0,
        delta_n_rad_s=0.0,
        m0_rad=0.0,
        cuc_rad=0.0,
        eccentricity=0.01,
        cus_rad=0.0,
        sqrt_a_m_sqrt=5153.7,
        toe_sow=0.0,
        cic_rad=0.0,
        omega0_rad=0.0,
        cis_rad=0.0,
        i0_rad=0.9,
        crc_m=0.0,
        argument_perigee_rad=0.0,
        omega_dot_rad_s=0.0,
        idot_rad_s=0.0,
        gps_week=2430,
        sv_accuracy_m=2.0,
        sv_health=0,
        tgd_s=0.0,
        transmission_sow=0.0,
        fit_interval_h=4.0,
    )
    return replace(record, **changes)


def test_ura_nominal_maps_to_published_upper_edge_and_legacy_scale() -> None:
    index, upper, interval = bound.integrity_interval_m(2.0)
    assert index == 0
    assert upper == 2.4
    assert interval == pytest.approx(10.608, abs=1e-12)
    assert bound.integrity_interval_m(11.3) == pytest.approx((5, 13.65, 60.333), abs=1e-12)


def test_unbounded_or_nonstandard_ura_is_never_zero() -> None:
    for value in (0.0, float("nan"), 3.0, 8192.0):
        with pytest.raises(bound.ModelBoundAuditError):
            bound.integrity_interval_m(value)


def test_selection_uses_latest_record_before_health_filtering() -> None:
    epoch = datetime(2026, 8, 7, 16, 30, tzinfo=timezone.utc)
    healthy = ephemeris(toc_gps=epoch - timedelta(seconds=3600))
    unhealthy_latest = ephemeris(toc_gps=epoch - timedelta(seconds=60), sv_health=1)
    with pytest.raises(bound.ModelBoundAuditError, match="UNHEALTHY"):
        bound.select_latest_record((healthy, unhealthy_latest), epoch - timedelta(seconds=18))


def test_age_and_fit_interval_are_runtime_admission_clauses() -> None:
    model_utc = datetime(2026, 8, 7, 16, 0, tzinfo=timezone.utc)
    gps_epoch = model_utc + timedelta(seconds=18)
    stale = ephemeris(toc_gps=gps_epoch - timedelta(seconds=14_401))
    with pytest.raises(bound.ModelBoundAuditError, match="AGE"):
        bound.select_latest_record((stale,), model_utc)
    outside_fit = ephemeris(toc_gps=gps_epoch - timedelta(seconds=3700), fit_interval_h=1.0)
    with pytest.raises(bound.ModelBoundAuditError, match="FIT_INTERVAL"):
        bound.select_latest_record((outside_fit,), model_utc)


def test_grid_audit_takes_maximum_across_both_satellites() -> None:
    model_utc = datetime(2026, 8, 7, 16, 0, tzinfo=timezone.utc)
    gps_toc = model_utc + timedelta(seconds=18)
    records = {
        "G15": (ephemeris("G15", toc_gps=gps_toc, sv_accuracy_m=2.0),),
        "G22": (ephemeris("G22", toc_gps=gps_toc, sv_accuracy_m=4.0),),
    }
    rows, maximum = bound.audit_selected_records(records, (model_utc,))
    assert len(rows) == 2
    assert maximum == pytest.approx(4.42 * 4.85, abs=1e-12)
    assert rows[1]["selected_health_values"] == [0]


def test_plan_lineage_manifest_and_input_surface_are_frozen() -> None:
    assert bound.file_sha256(ROOT / bound.PLAN_NAME) == bound.PLAN_SHA256
    manifest = bound.compiler_manifest()
    assert manifest["lineage"]["orbitality_receipt_sha256"] == bound.ORBITALITY_RECEIPT_SHA256
    assert manifest["model_interval"]["pure_orbit_only_error_claimed"] is False
    assert manifest["observation_access_forbidden"] is True
    assert manifest["new_gate_created"] is False
    json.loads(bound.strict_json(manifest))


def test_parent_navigation_specs_match_frozen_orbitality_receipt() -> None:
    orbitality = json.loads(
        (ROOT / bound.ORBITALITY_RECEIPT_NAME).read_text(encoding="ascii")
    )
    bound.verify_parent_navigation_specs(orbitality)


def test_strict_json_refuses_numpy_and_nonfinite_scalars() -> None:
    with pytest.raises(TypeError):
        bound.strict_json({"bad": np.bool_(True)})
    with pytest.raises(ValueError):
        bound.strict_json({"bad": float("inf")})


def test_exact_product_set_is_only_navigation() -> None:
    assert [product.doy for product in bound.NAVIGATION_PRODUCTS] == [219, 220, 221]
    assert all(product.name.endswith("_MN.rnx") for product in bound.NAVIGATION_PRODUCTS)
    assert all("BRDC" in product.url for product in bound.NAVIGATION_PRODUCTS)
    rendered = bound.strict_json(bound.compiler_manifest()).lower()
    assert "observation" in rendered
    assert "carrier_phase" not in rendered
