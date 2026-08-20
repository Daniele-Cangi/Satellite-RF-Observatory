"""Integrity checks for the frozen DSS-45 detector manifest."""

from hashlib import sha256
import json
from math import isfinite
from pathlib import Path

from experiments.orbital_discriminability.maven_rsr_carrier_tracker import (
    PARAMETERS,
    parameter_manifest,
)


ROOT = Path(__file__).parents[1]
MANIFEST_PATH = ROOT / "MAVEN_DSS45_CARRIER_DETECTOR_MANIFEST.json"


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _assert_finite(value: object) -> None:
    if isinstance(value, dict):
        for child in value.values():
            _assert_finite(child)
    elif isinstance(value, list):
        for child in value:
            _assert_finite(child)
    elif isinstance(value, float):
        assert isfinite(value)


def test_manifest_binds_exact_detector_and_development_result() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    binding = manifest["freeze_binding"]
    assert manifest["outcome"] == "DETECTOR_FROZEN_FOR_RSR_DEVELOPMENT"
    assert _sha(ROOT / "maven_rsr_carrier_tracker.py") == binding[
        "detector_code_sha256"
    ]
    assert _sha(ROOT / "maven_dss45_detector_develop.py") == binding[
        "development_runner_sha256"
    ]
    assert _sha(ROOT / "MAVEN_DSS45_DETECTOR_DEVELOPMENT_RESULT.json") == binding[
        "development_result_sha256"
    ]
    assert len(binding["source_commit"]) == 40


def test_manifest_parameters_are_exactly_the_frozen_code_parameters() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["parameters"] == parameter_manifest(PARAMETERS)
    assert manifest["parameters"]["effective_frequency_resolution_hz"] == 0.3662109375
    assert manifest["model_blind_boundary"]["orbital_model_input_used"] is False


def test_manifest_is_strictly_finite_and_contains_no_other_sample_role() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    _assert_finite(manifest)
    text = MANIFEST_PATH.read_text(encoding="utf-8")
    assert "DSS-35" not in text
    assert "DSS-55" not in text
    assert "27.398" not in text
    assert "50.809" not in text
