"""Run the frozen model-blind tracker on the authorized DSS-45 fixture only."""

from __future__ import annotations

import argparse
from pathlib import Path

from experiments.orbital_discriminability.maven_rsr_carrier_tracker import (
    PARAMETERS,
    development_result_object,
    strict_json,
    track_narrowband_carrier,
    verify_and_decode_development_artifact,
)


def run_development(
    artifact_path: Path,
    authority_path: Path,
    output_path: Path,
) -> str:
    artifact = verify_and_decode_development_artifact(artifact_path, authority_path)
    result = track_narrowband_carrier(
        artifact.samples,
        artifact.sample_rate_hz,
        artifact.baseband,
        artifact.receiver,
        PARAMETERS,
    )
    output = development_result_object(artifact, result, PARAMETERS)
    output_path.write_text(strict_json(output, indent=2) + "\n", encoding="utf-8")
    return result.status


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True, type=Path)
    parser.add_argument("--authority", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    status = run_development(
        arguments.artifact,
        arguments.authority,
        arguments.output,
    )
    print(status)
    return 0 if status == "CARRIER_ADMITTED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
