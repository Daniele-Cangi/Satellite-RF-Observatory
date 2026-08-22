"""Bounded metadata-only audit for a second Cassini SAGR3 dispersive root.

The audit is limited to the two raw-RSR collections named by the frozen SAGR3
bundle index. It consumes frozen inventory rows and parent receipts only. It
has no network, RSR header, payload, IQ, sample, amplitude, or detector input.
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Final, Sequence

from experiments.orbital_discriminability import cassini_sagr3_composite_xka as composite


AUDIT_VERSION: Final = "cassini-sagr3-second-dispersive-root-audit-v1"
OUTCOME_NO_ROOT: Final = "NO_SECOND_DISPERSIVE_ROOT_AVAILABLE"
OUTCOME_CANDIDATE: Final = "SECOND_DISPERSIVE_ROOT_CANDIDATE_FOUND_METADATA_ONLY"
DAY_PREFIX: Final = (
    "urn:nasa:pds:cassini.rss.raw.sagr:data.rsr01:s23sags2006_251_"
)
DSS65_KA_SUFFIX: Final = "k65rd::1.0"
DAY_PRODUCT_PREFIX: Final = "s23sags2006_251_"

BUNDLE_INDEX: Final = {
    "url": "https://atmos.nmsu.edu/PDS/data/PDS4/cassini-rss-raw-sagr/",
    "bytes": 3_734,
    "sha256": "4b9a7aa186b9b52d9b9760160e917bb69e95b75be9acc4596fb825052a8e1394",
    "raw_rsr_collections": ("data-rsr01/", "data-rsr02/"),
}
COLLECTIONS: Final = {
    "data-rsr01": {
        "url": (
            "https://atmos.nmsu.edu/PDS/data/PDS4/cassini-rss-raw-sagr/"
            "data-rsr01/collection_sagr_rsr01.csv"
        ),
        "bytes": 48_708,
        "sha256": "0051d9079e72a8e4d803534b543caa5b1402fb8c287802114dac96f2894ee16d",
    },
    "data-rsr02": {
        "url": (
            "https://atmos.nmsu.edu/PDS/data/PDS4/cassini-rss-raw-sagr/"
            "data-rsr02/collection_sagr_rsr02.csv"
        ),
        "bytes": 164,
        "sha256": "636235dc28eb27d35b959c547fe232d6ef7956d6d00a73b6b69215418af13971",
    },
}
RSR01_DAY_LIDVIDS: Final = (
    DAY_PREFIX + "1200nnnx14rd::1.0",
    DAY_PREFIX + "1200x14k25rd::1.0",
    DAY_PREFIX + "1200x14x25rd::1.0",
    DAY_PREFIX + "1200x14x65rd::1.0",
    DAY_PREFIX + "1502x14x14rd::1.0",
    DAY_PREFIX + "1646x14s14rd::1.0",
    DAY_PREFIX + "1955x14s43rd::1.0",
    DAY_PREFIX + "1955x14x43rd::1.0",
)
RSR02_DAY_LIDVIDS: Final = ()
FROZEN_DISTRIBUTED_PRODUCTS: Final = (
    DAY_PREFIX + "1200x14k25rd::1.0",
    DAY_PREFIX + "1200x14x25rd::1.0",
    DAY_PREFIX + "1200x14x65rd::1.0",
)
PARENT_RECEIPT_REPOSITORY_TEXT_SHA256: Final = {
    "CASSINI_SAGR3_DISTRIBUTED_HEADER_RECEIPT.json": (
        "eba267949a4aa3cb26996ac9664dfd3c68cf1f4e43d5ed0611e2e66adfa8655f"
    ),
    "CASSINI_SAGR3_COMPOSITE_XKA_RECEIPT.json": (
        "577eacf5b9c93a8f8a76c6719c0efd908a7f79d3dd0525d6bdadebfaec32994c"
    ),
}


class CassiniSecondDispersiveRootError(ValueError):
    """The bounded inventory or frozen parent topology is inconsistent."""


def evaluate_inventory(
    rsr01_lidvids: Sequence[str],
    rsr02_lidvids: Sequence[str],
) -> dict[str, object]:
    """Evaluate only the frozen day rows from the two raw-RSR collections."""

    rsr01 = _validated_lidvids("RSR01", rsr01_lidvids)
    rsr02 = _validated_lidvids("RSR02", rsr02_lidvids)
    missing = sorted(set(FROZEN_DISTRIBUTED_PRODUCTS) - set(rsr01))
    if missing:
        raise CassiniSecondDispersiveRootError(
            "frozen distributed products are absent from the inventory snapshot"
        )
    candidates = sorted(
        lidvid
        for lidvid in (*rsr01, *rsr02)
        if f":{DAY_PRODUCT_PREFIX}" in lidvid
        and lidvid.endswith(DSS65_KA_SUFFIX)
    )
    return {
        "outcome": OUTCOME_CANDIDATE if candidates else OUTCOME_NO_ROOT,
        "dss65_ka_candidates": candidates,
        "rsr01_day_product_count": len(rsr01),
        "rsr02_day_product_count": len(rsr02),
    }


def build_audit_receipt() -> dict[str, object]:
    """Build the deterministic refusal from frozen metadata snapshots."""

    parents = validate_parent_receipts()
    header = parents["CASSINI_SAGR3_DISTRIBUTED_HEADER_RECEIPT.json"]
    prior = parents["CASSINI_SAGR3_COMPOSITE_XKA_RECEIPT.json"]
    if header["outcome"] != "CASSINI_SAGR3_HEADER_TOPOLOGY_QUALIFIED":
        raise CassiniSecondDispersiveRootError("parent header topology changed")
    if prior["outcome"] != "CASSINI_COMPOSITE_OBSERVABLE_NOT_ADMITTED":
        raise CassiniSecondDispersiveRootError("parent composite outcome changed")

    inventory = evaluate_inventory(RSR01_DAY_LIDVIDS, RSR02_DAY_LIDVIDS)
    receipt: dict[str, object] = {
        "audit_version": AUDIT_VERSION,
        "audit_manifest_sha256": audit_manifest_sha256(),
        "scope": "SAGR3_BUNDLE_TWO_RAW_RSR_COLLECTION_INVENTORIES_METADATA_ONLY",
        "outcome": inventory["outcome"],
        "physical_question": (
            "Does the frozen SAGR3 pass contain simultaneous DSS-65 Ka reception "
            "needed to cancel first-order plasma at the second receive root?"
        ),
        "information_value": (
            "Determines whether a symmetric DSS25_X_Ka minus DSS65_X_Ka "
            "orbital observable can exist in this archived pass."
        ),
        "source_snapshots": {
            "bundle_index": {
                **BUNDLE_INDEX,
                "raw_rsr_collections": list(BUNDLE_INDEX["raw_rsr_collections"]),
            },
            "collections": COLLECTIONS,
            "retrieved_utc_date": "2026-08-22",
            "full_inventory_content_persisted": False,
            "matching_inventory_rows_persisted": True,
        },
        "bounded_inventory": {
            "data-rsr01_day_lidvids": list(RSR01_DAY_LIDVIDS),
            "data-rsr02_day_lidvids": list(RSR02_DAY_LIDVIDS),
            **inventory,
        },
        "frozen_topology": {
            "DSS25_X": FROZEN_DISTRIBUTED_PRODUCTS[1],
            "DSS25_KA": FROZEN_DISTRIBUTED_PRODUCTS[0],
            "DSS65_X": FROZEN_DISTRIBUTED_PRODUCTS[2],
            "DSS65_KA": None,
            "pretransition_receive_window": (
                "2006-09-08T12:00:01Z/2006-09-08T14:57:31Z"
            ),
        },
        "exact_carrier_grid": {
            "state": "NOT_EVALUATED_TOPOLOGY_ABSENT",
            "reason": (
                "Without a DSS-65 Ka branch no symmetric composite can be "
                "formed, so header reaccess cannot restore the missing root."
            ),
        },
        "authorized_claims": [
            "NO_DSS65_KA_PRODUCT_IN_THE_TWO_HASHED_SAGR3_RAW_RSR_COLLECTION_SNAPSHOTS",
            "NO_SYMMETRIC_DUAL_BAND_COMPOSITE_IN_THIS_BOUNDED_PASS",
        ],
        "unauthorized_claims": [
            "NO_DSS65_KA_RECORDING_EXISTS_ANYWHERE",
            "PLASMA_WAS_MEASURED_OR_ABSENT",
            "ORBITAL_MODEL_PREFERENCE",
            "RF_OR_CARRIER_PRESENCE",
        ],
        "parent_receipts": {
            name: {
                "repository_text_sha256": digest,
                "line_ending_policy": "CRLF_NORMALIZED_TO_LF_BEFORE_HASH",
            }
            for name, digest in PARENT_RECEIPT_REPOSITORY_TEXT_SHA256.items()
        },
        "access": {
            "network_metadata_tool_calls": 11,
            "source_snapshots_bound_by_hash": 3,
            "rsr_label_requests": 0,
            "rsr_header_bytes_accessed": 0,
            "rsr_payload_or_iq_bytes_accessed": 0,
            "sample_or_amplitude_fields_represented": False,
            "detector_implemented": False,
        },
        "stop_condition": OUTCOME_NO_ROOT,
        "next_action": (
            "CLOSE_SAGR3_SYMMETRIC_COMPOSITE_PATH_WITHOUT_IQ; "
            "DO_NOT_MATERIALIZE_EXACT_CARRIER_GRID"
        ),
        "new_gate_created": False,
    }
    strict_json(receipt)
    return receipt


def validate_parent_receipts() -> dict[str, dict[str, object]]:
    directory = Path(__file__).parent
    loaded: dict[str, dict[str, object]] = {}
    for name, expected_sha256 in PARENT_RECEIPT_REPOSITORY_TEXT_SHA256.items():
        raw = (directory / name).read_bytes()
        actual = composite.repository_text_sha256(raw)
        if actual != expected_sha256:
            raise CassiniSecondDispersiveRootError(
                f"frozen parent receipt hash changed: {name}"
            )
        loaded[name] = json.loads(
            raw,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
        )
    return loaded


def audit_manifest_sha256() -> str:
    manifest = {
        "audit_version": AUDIT_VERSION,
        "bundle_index": BUNDLE_INDEX,
        "collections": COLLECTIONS,
        "rsr01_day_lidvids": RSR01_DAY_LIDVIDS,
        "rsr02_day_lidvids": RSR02_DAY_LIDVIDS,
        "frozen_distributed_products": FROZEN_DISTRIBUTED_PRODUCTS,
        "parent_receipts": PARENT_RECEIPT_REPOSITORY_TEXT_SHA256,
        "search_predicate": "DAY_PRODUCT_TOKEN_AND_K65RD_SUFFIX_ACROSS_BOTH_COLLECTIONS",
        "forbidden": [
            "RSR label access",
            "RSR header access",
            "RSR payload or IQ access",
            "amplitude diagnostics",
            "detector implementation",
            "global absence claim",
            "new gate",
        ],
    }
    return sha256(strict_json(manifest).encode("ascii")).hexdigest()


def strict_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def _validated_lidvids(name: str, lidvids: Sequence[str]) -> tuple[str, ...]:
    values = tuple(lidvids)
    if len(values) != len(set(values)):
        raise CassiniSecondDispersiveRootError(f"{name} inventory has duplicates")
    if any(
        not isinstance(value, str)
        or not value.startswith("urn:nasa:pds:cassini.rss.raw.sagr:data.rsr")
        or "::" not in value
        or value.strip() != value
        for value in values
    ):
        raise CassiniSecondDispersiveRootError(f"{name} inventory has invalid LIDVIDs")
    return values


if __name__ == "__main__":
    print(strict_json(build_audit_receipt()))
