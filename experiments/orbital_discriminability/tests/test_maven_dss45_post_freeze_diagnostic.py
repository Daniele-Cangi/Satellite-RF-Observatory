"""Offline checks for the post-freeze development-only comparison."""

from hashlib import sha256
import json
from pathlib import Path

from experiments.orbital_discriminability.maven_dss45_post_freeze_diagnostic import (
    build_diagnostic,
)


ROOT = Path(__file__).parents[1]


def test_diagnostic_is_no_fit_and_bound_to_frozen_manifest() -> None:
    manifest_path = ROOT / "MAVEN_DSS45_CARRIER_DETECTOR_MANIFEST.json"
    diagnostic = build_diagnostic(
        json.loads((ROOT / "MAVEN_DSS45_DETECTOR_DEVELOPMENT_RESULT.json").read_text()),
        json.loads((ROOT / "MAVEN_DSS45_METADATA_RESULT.json").read_text()),
        detector_manifest_sha256=sha256(manifest_path.read_bytes()).hexdigest(),
        detector_manifest=json.loads(manifest_path.read_text()),
    )
    assert diagnostic["comparison_order"] == (
        "DETECTOR_FROZEN_THEN_METADATA_CURVE_COMPARED"
    )
    assert diagnostic["comparison_method"]["interpolation"] == "NONE"
    assert diagnostic["comparison_method"]["fitted_frequency_offset"] == "NONE"
    assert diagnostic["comparison_method"]["fitted_time_offset"] == "NONE"
    assert diagnostic["comparison_count"] == 72
    assert diagnostic["nominal_residual"]["within_effective_resolution_count"] == 70
    assert diagnostic["spk_independence"] == ("RECONSTRUCTED_POST_PASS_NOT_INDEPENDENT")
