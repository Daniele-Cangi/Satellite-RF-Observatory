"""Offline numerical replay of admitted measurements, never of an orbit product.

Run from repository root:
    python -m experiments.gnss_inverse_positioning.replay INPUT.json

This reproduces the frozen computation; it is not a new blinded experiment.
"""
import argparse
import json
from pathlib import Path

import numpy as np

from .solver import interpolate_event, solve, uncertainty_box


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    data = json.loads(args.input.read_text())
    allowed = {"description", "lineage", "fit_stations", "target_if_codes_m", "receiver_clocks_m", "station_ecef_m", "covariance_z_m2"}
    if set(data) - allowed:
        raise ValueError("unexpected input fields; no state or orbit inputs allowed")
    codes = np.array(data["target_if_codes_m"])
    clocks = np.array(data["receiver_clocks_m"])
    stations = np.array(data["station_ecef_m"])
    covariance = np.array(data["covariance_z_m2"])
    if codes.shape != (5,11) or clocks.shape != (5,11) or stations.shape != (5,3) or covariance.shape != (5,5):
        raise ValueError("expected frozen five-root, eleven-epoch input")
    event = interpolate_event(codes,clocks,stations)
    best = solve(event["z"],event["positions"],covariance)
    uncertainty = uncertainty_box(event["z"],event["positions"],covariance,best)
    print(json.dumps({"xyz_fixed_axes_m":best["q"][:3].tolist(), "B_m":float(best["q"][3]), "u0_relative_s":event["u0"], "total_95_outer_radius_m":uncertainty["total_95_outer_radius_m"], "status":"UNCERTAINTY_TOO_LARGE" if uncertainty["total_95_outer_radius_m"] > 10000 else "REPLAY_WITHIN_UNCERTAINTY_LIMIT"},indent=2))


if __name__ == "__main__":
    main()
