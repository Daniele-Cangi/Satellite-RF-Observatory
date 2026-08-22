from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from experiments.orbital_discriminability import (
    cassini_sagr3_second_dispersive_root as audit,
)


def test_frozen_inventories_end_at_exact_bounded_refusal():
    receipt = audit.build_audit_receipt()

    assert receipt["outcome"] == audit.OUTCOME_NO_ROOT
    assert receipt["bounded_inventory"]["dss65_ka_candidates"] == []
    assert receipt["bounded_inventory"]["rsr01_day_product_count"] == 8
    assert receipt["bounded_inventory"]["rsr02_day_product_count"] == 0
    assert receipt["frozen_topology"]["DSS65_KA"] is None
    assert receipt["exact_carrier_grid"]["state"] == (
        "NOT_EVALUATED_TOPOLOGY_ABSENT"
    )


def test_dss65_x_is_not_misclassified_as_a_dispersive_pair():
    result = audit.evaluate_inventory(
        audit.RSR01_DAY_LIDVIDS,
        audit.RSR02_DAY_LIDVIDS,
    )

    assert result["outcome"] == audit.OUTCOME_NO_ROOT
    assert any(lidvid.endswith("x65rd::1.0") for lidvid in audit.RSR01_DAY_LIDVIDS)
    assert not any(lidvid.endswith("k65rd::1.0") for lidvid in audit.RSR01_DAY_LIDVIDS)


def test_injected_k65_row_changes_only_to_metadata_candidate():
    candidate = (
        "urn:nasa:pds:cassini.rss.raw.sagr:data.rsr02:"
        + audit.DAY_PRODUCT_PREFIX
        + "1200x14k65rd::1.0"
    )
    result = audit.evaluate_inventory(
        audit.RSR01_DAY_LIDVIDS,
        (candidate,),
    )

    assert result["outcome"] == audit.OUTCOME_CANDIDATE
    assert result["dss65_ka_candidates"] == [candidate]


def test_missing_frozen_product_and_duplicate_rows_are_refused():
    missing = tuple(
        lidvid
        for lidvid in audit.RSR01_DAY_LIDVIDS
        if lidvid != audit.FROZEN_DISTRIBUTED_PRODUCTS[0]
    )
    with pytest.raises(audit.CassiniSecondDispersiveRootError, match="absent"):
        audit.evaluate_inventory(missing, ())

    duplicated = (*audit.RSR01_DAY_LIDVIDS, audit.RSR01_DAY_LIDVIDS[0])
    with pytest.raises(audit.CassiniSecondDispersiveRootError, match="duplicates"):
        audit.evaluate_inventory(duplicated, ())


def test_claim_scope_is_bounded_and_iq_remains_sealed():
    receipt = audit.build_audit_receipt()

    assert "NO_DSS65_KA_RECORDING_EXISTS_ANYWHERE" in receipt["unauthorized_claims"]
    assert receipt["access"]["rsr_payload_or_iq_bytes_accessed"] == 0
    assert receipt["access"]["rsr_header_bytes_accessed"] == 0
    assert receipt["access"]["rsr_label_requests"] == 0
    assert receipt["access"]["sample_or_amplitude_fields_represented"] is False
    assert receipt["new_gate_created"] is False


def test_module_has_no_network_or_signal_input_surface():
    signature = inspect.signature(audit.build_audit_receipt)
    source = inspect.getsource(audit.build_audit_receipt).casefold()

    assert not signature.parameters
    assert "invoke-webrequest" not in source
    assert "requests." not in source
    assert "urlopen" not in source
    assert "http" not in source
    assert "decode" not in source
    assert "fromfile" not in source


def test_static_receipt_matches_deterministic_builder_and_strict_json():
    path = Path(audit.__file__).with_name(
        "CASSINI_SAGR3_SECOND_DISPERSIVE_ROOT_RECEIPT.json"
    )
    receipt = json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
    )

    assert receipt == audit.build_audit_receipt()
    assert receipt["audit_manifest_sha256"] == audit.audit_manifest_sha256()
    with pytest.raises(ValueError):
        audit.strict_json({"value": float("nan")})
