"""Compare frozen ridge points with the metadata curve, without fitting."""

from __future__ import annotations

import argparse
from datetime import datetime
from hashlib import sha256
import json
from math import sqrt
from pathlib import Path


def build_diagnostic(
    development_result: dict,
    metadata_result: dict,
    *,
    detector_manifest_sha256: str,
    detector_manifest: dict,
) -> dict[str, object]:
    if detector_manifest["outcome"] != "DETECTOR_FROZEN_FOR_RSR_DEVELOPMENT":
        raise ValueError("detector was not frozen before comparison")
    receiver = development_result["receiver_configuration"]
    points = development_result["measurement"]["selected_segment"]["points"]
    first_sample = _utc(receiver["first_sample_utc"])
    first_offset = points[0]["event_time_offset_s"]
    last_offset = points[-1]["event_time_offset_s"]
    rows = []
    for curve_row in metadata_result["curve"]:
        prediction_offset = (
            _utc(curve_row["record_first_sample_utc"]) - first_sample
        ).total_seconds() + curve_row["prediction_epoch_offset_s"]
        if not first_offset <= prediction_offset <= last_offset:
            continue
        point = min(
            points,
            key=lambda candidate: abs(
                candidate["event_time_offset_s"] - prediction_offset
            ),
        )
        observed = point["baseband_frequency_hz"]
        predicted = curve_row["nominal_reconstructed_spk"][
            "recorded_baseband_frequency_hz"
        ]
        rows.append(
            {
                "prediction_event_time_offset_s": prediction_offset,
                "detector_event_time_offset_s": point["event_time_offset_s"],
                "detector_baseband_frequency_hz": observed,
                "predicted_baseband_frequency_hz": predicted,
                "nominal_residual_hz": observed - predicted,
                "mars_center_null_residual_hz": observed
                - curve_row["null_mars_center_geometry"][
                    "recorded_baseband_frequency_hz"
                ],
                "ramp_nco_only_null_residual_hz": observed
                - curve_row["null_ramp_nco_only"]["recorded_baseband_frequency_hz"],
            }
        )
    if not rows:
        raise ValueError("metadata curve and frozen ridge have no common interval")
    residuals = [row["nominal_residual_hz"] for row in rows]
    native_bin = detector_manifest["parameters"]["native_bin_spacing_hz"]
    effective_resolution = detector_manifest["parameters"][
        "effective_frequency_resolution_hz"
    ]
    outliers = [
        row for row in rows if abs(row["nominal_residual_hz"]) > effective_resolution
    ]
    return {
        "diagnostic_version": "maven-dss45-post-freeze-diagnostic-v1",
        "detector_manifest_sha256": detector_manifest_sha256,
        "comparison_order": "DETECTOR_FROZEN_THEN_METADATA_CURVE_COMPARED",
        "comparison_method": {
            "matching": "nearest frozen detector frame by event time",
            "interpolation": "NONE",
            "fitted_frequency_offset": "NONE",
            "fitted_time_offset": "NONE",
            "threshold_or_parameter_change": "NONE",
        },
        "comparison_count": len(rows),
        "maximum_absolute_time_separation_s": max(
            abs(
                row["detector_event_time_offset_s"]
                - row["prediction_event_time_offset_s"]
            )
            for row in rows
        ),
        "nominal_residual": {
            "mean_hz": sum(residuals) / len(residuals),
            "rmse_hz": sqrt(sum(value * value for value in residuals) / len(residuals)),
            "maximum_absolute_hz": max(abs(value) for value in residuals),
            "within_native_bin_count": sum(
                abs(value) <= native_bin for value in residuals
            ),
            "within_effective_resolution_count": sum(
                abs(value) <= effective_resolution for value in residuals
            ),
            "native_bin_spacing_hz": native_bin,
            "effective_frequency_resolution_hz": effective_resolution,
        },
        "frozen_null_diagnostic": {
            "minimum_absolute_mars_center_residual_hz": min(
                abs(row["mars_center_null_residual_hz"]) for row in rows
            ),
            "minimum_absolute_ramp_nco_only_residual_hz": min(
                abs(row["ramp_nco_only_null_residual_hz"]) for row in rows
            ),
        },
        "outliers_beyond_effective_resolution": outliers,
        "spk_independence": "RECONSTRUCTED_POST_PASS_NOT_INDEPENDENT",
        "claim_scope": (
            "development compiler/tracker diagnostic only; no independent orbital "
            "or spacecraft-identity claim"
        ),
    }


def _utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--development-result", required=True, type=Path)
    parser.add_argument("--metadata-result", required=True, type=Path)
    parser.add_argument("--detector-manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    output = build_diagnostic(
        _load(arguments.development_result),
        _load(arguments.metadata_result),
        detector_manifest_sha256=_sha(arguments.detector_manifest),
        detector_manifest=_load(arguments.detector_manifest),
    )
    arguments.output.write_text(
        json.dumps(output, allow_nan=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
