"""Freeze the exact opaque prediction bundle and identity-blind scorer pair."""

from __future__ import annotations

import argparse
import ast
from hashlib import sha256
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
from typing import Final, Mapping

from experiments.orbital_discriminability import (
    gnss_blind_orbit_assignment_predictions as predictions,
)
from experiments.orbital_discriminability import gnss_opaque_orbit_scorer as scorer


SEAL_VERSION: Final = "gnss-blind-orbit-prediction-scorer-seal-v1"
SEAL_NAME: Final = "GNSS_BLIND_ORBIT_ASSIGNMENT_PREDICTION_SCORER_SEAL.json"
PREDICTION_COMPILER_COMMIT: Final = (
    "9b17c7b39fe672cc3bcce01be8816f8b2ff92c6c"
)
PREDICTION_COMPILER_SOURCE_SHA256: Final = (
    "3160bc4ab9c9fbbabca20457d7cfd4aa14d3d84f8a388ca850a6162504600544"
)
PREDICTION_COMPILER_MANIFEST_SHA256: Final = (
    "e87298ef2af0cc7359f8458249468b10a08491788305c6932ce7f79c3a5023f7"
)
CURVE_SET_SHA256: Final = (
    "0e5eb9207a15574cf66d25f5f1eccdedb4e9ec4129a32abf5d23a066fdd9b2df"
)
BUNDLE_CANONICAL_BYTES: Final = 20_849
ALLOWED_SCORER_IMPORT_ROOTS: Final = {
    "__future__",
    "hashlib",
    "json",
    "math",
    "pathlib",
    "re",
    "typing",
    "numpy",
}


class BlindOrbitScorerSealError(ValueError):
    """The exact bundle/scorer pair or its authority changed."""


def strict_json(value: object, *, pretty: bool = False) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
        sort_keys=True,
    )


def canonical_sha256(path: Path) -> str:
    payload = Path(path).read_bytes().replace(b"\r\n", b"\n")
    return sha256(payload).hexdigest()


def source_sha256() -> str:
    return canonical_sha256(Path(__file__))


def _git_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
    ).strip()


def dependency_versions() -> dict[str, str]:
    return {
        "numpy": importlib.metadata.version("numpy"),
        "python": platform.python_version(),
    }


def _scorer_source_audit() -> dict[str, object]:
    path = Path(scorer.__file__)
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    import_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            import_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module is not None:
                import_roots.add(node.module.split(".")[0])
    unexpected = import_roots - ALLOWED_SCORER_IMPORT_ROOTS
    if unexpected:
        raise BlindOrbitScorerSealError(
            f"SCORER_IMPORT_SURFACE_CHANGED:{','.join(sorted(unexpected))}"
        )
    lowered = source.lower()
    forbidden = {
        "g22",
        "g30",
        "mapping_seal",
        "gnss_blind_orbit_assignment_plan",
        "decode_observation",
        "import requests",
        "import urllib",
        "import socket",
    }
    leaked = sorted(token for token in forbidden if token in lowered)
    if leaked:
        raise BlindOrbitScorerSealError(
            f"SCORER_IDENTITY_OR_TRANSPORT_SURFACE:{','.join(leaked)}"
        )
    return {
        "filename": path.name,
        "canonical_sha256": canonical_sha256(path),
        "import_roots": sorted(import_roots),
        "unexpected_import_roots": [],
        "named_hypothesis_tokens": 0,
        "observation_decoder": False,
        "network_client": False,
        "write_authority": False,
    }


def scorer_manifest(root: Path) -> dict[str, object]:
    root = Path(root)
    bundle_path = root / scorer.BUNDLE_NAME
    bundle = scorer.load_exact_bundle(bundle_path)
    canonical_bytes = len(bundle_path.read_bytes().replace(b"\r\n", b"\n"))
    if canonical_bytes != BUNDLE_CANONICAL_BYTES:
        raise BlindOrbitScorerSealError("BUNDLE_BYTE_COUNT_CHANGED")
    if predictions.bundle_curve_set_sha256(bundle) != CURVE_SET_SHA256:
        raise BlindOrbitScorerSealError("CURVE_SET_HASH_CHANGED")
    if predictions.source_sha256() != PREDICTION_COMPILER_SOURCE_SHA256:
        raise BlindOrbitScorerSealError("PREDICTION_COMPILER_SOURCE_CHANGED")
    if (
        predictions.compiler_manifest_sha256(root)
        != PREDICTION_COMPILER_MANIFEST_SHA256
    ):
        raise BlindOrbitScorerSealError("PREDICTION_COMPILER_MANIFEST_CHANGED")
    result = {
        "schema": "gnss-blind-orbit-scorer-manifest-v1",
        "seal_version": SEAL_VERSION,
        "prediction_bundle": {
            "filename": scorer.BUNDLE_NAME,
            "canonical_bytes": BUNDLE_CANONICAL_BYTES,
            "canonical_sha256": scorer.BUNDLE_CANONICAL_SHA256,
            "manifest_sha256": scorer.BUNDLE_MANIFEST_SHA256,
            "curve_set_sha256": CURVE_SET_SHA256,
            "opaque_hypotheses": 6,
            "named_hypotheses": 0,
        },
        "prediction_compiler": {
            "source_commit": PREDICTION_COMPILER_COMMIT,
            "source_sha256": PREDICTION_COMPILER_SOURCE_SHA256,
            "manifest_sha256": PREDICTION_COMPILER_MANIFEST_SHA256,
        },
        "scorer": _scorer_source_audit(),
        "scoring": {
            "raw_epochs": scorer.RAW_EPOCHS,
            "prefix_epochs": scorer.PREFIX_EPOCHS,
            "heldout_epochs": scorer.HELDOUT_EPOCHS,
            "per_hypothesis_parameters": ["CONSTANT", "LINEAR_RATE"],
            "per_hypothesis_parameter_count": 2,
            "pairwise_guard_m": scorer.PAIRWISE_GUARD_M,
            "metric_order": ["PEAK_TO_PEAK_M", "RMS_M", "OPAQUE_ID"],
            "same_loop_for_all_hypotheses": True,
            "heldout_refit": False,
            "free_time_phase": False,
            "time_warp": False,
        },
        "receipt_order": {
            "score_receipt_contains_only_opaque_ids": True,
            "score_receipt_hash_before_identity_reveal": True,
            "identity_reveal_inside_scorer": False,
        },
        "authority": {
            "primary_access": False,
            "primary_materialization": False,
            "observation_decode": False,
            "measurement_score": False,
            "executor": False,
            "separate_review_required": True,
        },
        "synthetic_tests_only": True,
        "stop": "STOP_BEFORE_EXECUTOR_OR_PRIMARY_PRODUCT_ACCESS",
        "new_gate_created": False,
        "generic_framework_created": False,
    }
    strict_json(result)
    return result


def scorer_manifest_sha256(root: Path) -> str:
    return sha256(strict_json(scorer_manifest(root)).encode("ascii")).hexdigest()


def write_seal(root: Path) -> dict[str, object]:
    root = Path(root)
    output = root / SEAL_NAME
    if output.exists():
        raise BlindOrbitScorerSealError("SCORER_SEAL_ALREADY_EXISTS")
    manifest = scorer_manifest(root)
    value = {
        **manifest,
        "state": "BLIND_ORBIT_PREDICTION_AND_SCORER_SEALED",
        "seal_source_commit": _git_commit(),
        "seal_source_sha256": source_sha256(),
        "scorer_manifest_sha256": scorer_manifest_sha256(root),
        "dependencies": dependency_versions(),
        "primary_access": {
            "locators_queried": 0,
            "headers_opened": 0,
            "payload_bytes": 0,
            "values": 0,
        },
        "orbital_scores_from_measurement": 0,
        "next_maximum": (
            "REVIEW_BEFORE_ONE_PRIMARY_MATERIALIZATION_AND_OPAQUE_SCORE"
        ),
    }
    output.write_bytes((strict_json(value, pretty=True) + "\n").encode("ascii"))
    return value


def cli_summary(value: Mapping[str, object]) -> dict[str, object]:
    return {
        "state": value.get("state", "SCORER_MANIFEST_VALID"),
        "scorer_manifest_sha256": value.get(
            "scorer_manifest_sha256", "NOT_WRITTEN"
        ),
        "primary_access": value.get(
            "primary_access",
            {"locators_queried": 0, "headers_opened": 0, "payload_bytes": 0, "values": 0},
        ),
        "orbital_scores_from_measurement": value.get(
            "orbital_scores_from_measurement", 0
        ),
    }


def main() -> None:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    value = write_seal(root) if args.write else scorer_manifest(root)
    print(strict_json(cli_summary(value)))


if __name__ == "__main__":
    main()
