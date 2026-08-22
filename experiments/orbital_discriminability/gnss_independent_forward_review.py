"""Navigation-only review for one independent GNSS forward vertical.

The module reuses the hardened broadcast geometry and physical-envelope
primitives for a small, predeclared station set. Observation products enter
only as HTTP HEAD descriptions; no observation payload is accepted.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import timedelta
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
from typing import Final, Sequence

import numpy as np

from experiments.orbital_discriminability import gnss_double_difference_envelope as envelope
from experiments.orbital_discriminability import gnss_double_difference_screen as screen


REVIEW_VERSION: Final = "gnss-independent-forward-review-v1"
OUTCOME_READY: Final = "GNSS_INDEPENDENT_VERTICAL_READY_FOR_QUALIFICATION"
OUTCOME_NONE: Final = "NO_GNSS_INDEPENDENT_VERTICAL_WITH_POSITIVE_MARGIN"


STATIONS: Final = {
    "WTZA00DEU": screen.Station(
        "WTZA00DEU", 49.144228, 12.878908, 665.9,
        "EXTERNAL_CESIUM", "SEPT_MOSAIC_T_4.15.0", "ASH700936C_M_SNOW",
        "ROBOT", "WTZA00DEU_RECEIVER_ANTENNA_CLOCK",
        "https://network.igs.org/WTZA00DEU",
    ),
    "ONSA00SWE": screen.Station(
        "ONSA00SWE", 57.395297, 11.925514, 45.5,
        "EXTERNAL_H_MASER", "SEPT_POLARX5TR_5.7.0", "AOAD_M_B_OSOD",
        "UNKNOWN", "ONSA00SWE_RECEIVER_ANTENNA_CLOCK",
        "https://network.igs.org/ONSA00SWE",
    ),
    "BRUX00BEL": screen.Station(
        "BRUX00BEL", 50.798064, 4.358564, 158.3,
        "EXTERNAL_IMASER_3000", "SEPT_POLARX5TR_5.7.0", "JAVRINGANT_DM_SCIS",
        "ROBOT", "BRUX00BEL_RECEIVER_ANTENNA_CLOCK",
        "https://network.igs.org/BRUX00BEL",
    ),
    "DLF100NLD": screen.Station(
        "DLF100NLD", 51.986019, 4.387458, 75.8,
        "EXTERNAL_CESIUM", "TRIMBLE_ALLOY_6.20", "LEIAR25_R3_LEIT",
        "ROBOT", "DLF100NLD_RECEIVER_ANTENNA_CLOCK",
        "https://network.igs.org/DLF100NLD",
    ),
    "KIRU00SWE": screen.Station(
        "KIRU00SWE", 67.857350, 20.968442, 390.9,
        "EXTERNAL_CESIUM", "SEPT_POLARX5TR_5.6.0", "SEPCHOKE_B3E6_SPKE",
        "ROBOT", "KIRU00SWE_RECEIVER_ANTENNA_CLOCK",
        "https://network.igs.org/KIRU00SWE",
    ),
    "MAT100ITA": screen.Station(
        "MAT100ITA", 40.649061, 16.704544, 534.5,
        "INTERNAL", "LEICA_GR30_4.83_7.900", "LEIAR20_NONE",
        "ROBOT", "MAT100ITA_RECEIVER_ANTENNA_CLOCK",
        "https://network.igs.org/MAT100ITA",
    ),
}


PAIR_SPECS: Final = (
    ("WTZA_ONSA", "WTZA00DEU", "ONSA00SWE"),
    ("BRUX_ONSA", "BRUX00BEL", "ONSA00SWE"),
    ("WTZA_DLF1", "WTZA00DEU", "DLF100NLD"),
    ("BRUX_DLF1", "BRUX00BEL", "DLF100NLD"),
    ("WTZA_BRUX", "WTZA00DEU", "BRUX00BEL"),
    ("WTZA_KIRU", "WTZA00DEU", "KIRU00SWE"),
    ("KIRU_MAT1", "KIRU00SWE", "MAT100ITA"),
    ("WTZA_MAT1", "WTZA00DEU", "MAT100ITA"),
)


PRODUCT_ROLES: Final = {
    "qualification": (
        {
            "station_id": "KIRU00SWE",
            "name": "KIRU00SWE_R_20262140000_01D_30S_MO.crx.gz",
            "url": "https://igs.bkg.bund.de/root_ftp/IGS/obs/2026/214/KIRU00SWE_R_20262140000_01D_30S_MO.crx.gz",
            "head_status": 200,
            "head_content_length_bytes": 5_126_492,
        },
        {
            "station_id": "MAT100ITA",
            "name": "MAT100ITA_R_20262140000_01D_30S_MO.crx.gz",
            "url": "https://igs.bkg.bund.de/root_ftp/IGS/obs/2026/214/MAT100ITA_R_20262140000_01D_30S_MO.crx.gz",
            "head_status": 200,
            "head_content_length_bytes": 4_237_763,
        },
    ),
    "primary": (
        {
            "station_id": "KIRU00SWE",
            "name": "KIRU00SWE_R_20262150000_01D_30S_MO.crx.gz",
            "url": "https://igs.bkg.bund.de/root_ftp/IGS/obs/2026/215/KIRU00SWE_R_20262150000_01D_30S_MO.crx.gz",
            "head_status": 200,
            "head_content_length_bytes": 5_113_772,
        },
        {
            "station_id": "MAT100ITA",
            "name": "MAT100ITA_R_20262150000_01D_30S_MO.crx.gz",
            "url": "https://igs.bkg.bund.de/root_ftp/IGS/obs/2026/215/MAT100ITA_R_20262150000_01D_30S_MO.crx.gz",
            "head_status": 200,
            "head_content_length_bytes": 4_255_324,
        },
    ),
}


def review_navigation(navigation: Path) -> dict[str, object]:
    source = screen.validate_navigation(navigation)
    pair_results = [compile_pair(navigation, *spec) for spec in PAIR_SPECS]
    selected = select_candidate(pair_results)
    result = {
        "review_version": REVIEW_VERSION,
        "review_manifest_sha256": review_manifest_sha256(),
        "scope": "EXACT_BROADCAST_NAVIGATION_AND_HTTP_HEAD_DESCRIPTIONS_ONLY",
        "physical_question": (
            "CAN_ONE_NEW_TWO_STATION_GNSS_COORDINATE_REACH_A_MEASUREMENT_VALID_"
            "HELDOUT_ORBITAL_VERSUS_NULL_SCORE"
        ),
        "new_information": (
            "PASS_SPECIFIC_GEOMETRY_AND_PHYSICAL_MARGIN_FOR_AN_INDEPENDENT_"
            "QUALIFICATION_PRIMARY_VERTICAL"
        ),
        "navigation_source": source,
        "candidate_pairs": pair_results,
        "selected_candidate": selected,
        "product_roles": product_roles(),
        "role_policy": {
            "qualification": "STRUCTURE_ONLY_ON_DOY_214_BEFORE_ANY_PRIMARY_ACCESS",
            "primary": "DOY_215_REMAINS_UNOPENED_UNTIL_A_SEPARATE_FROZEN_PLAN",
            "same_station_hardware_across_days": True,
            "distinct_artifact_days": True,
            "closed_gold_nlib_artifacts_reused": False,
        },
        "measurement_access": {
            "observation_payload_bytes_accessed": 0,
            "observation_headers_accessed": 0,
            "observation_epochs_accessed": 0,
            "observation_fields_accessed": 0,
            "carrier_phase_values_accessed": 0,
            "snr_or_lli_values_accessed": 0,
        },
        "next_exact_blocker": (
            "QUALIFICATION_PRODUCT_FIELD_TOPOLOGY_AND_DECODER_NATIVE_"
            "CONTINUITY_UNPROVEN"
        ),
        "stop_condition": (
            "ABANDON_THIS_GNSS_ROUTE_IF_THE_DISTINCT_QUALIFICATION_PRODUCTS_DO_"
            "NOT_PROVE_THE_REQUIRED_SIGNAL_TOPOLOGY_AND_PARSER_CONTINUITY"
        ),
        "outcome": OUTCOME_READY if selected is not None else OUTCOME_NONE,
        "qualification_access_authorized": False,
        "primary_access_authorized": False,
        "prospective_plan_frozen": False,
        "new_gate_created": False,
    }
    strict_json(result)
    return result


def compile_pair(
    navigation: Path,
    pair_id: str,
    left_id: str,
    right_id: str,
) -> dict[str, object]:
    pair = (STATIONS[left_id], STATIONS[right_id])
    previous = screen.STATIONS
    screen.STATIONS = pair
    try:
        geometry = screen.screen_navigation(navigation)
        records = screen.parse_gps_navigation(navigation)
        epochs = screen.utc_grid(
            screen.WINDOW_START_UTC, screen.WINDOW_STOP_UTC, screen.GRID_STEP_S
        )
        epoch_index = {epoch: index for index, epoch in enumerate(epochs)}
        station_ecef = {
            station.station_id: screen.station_to_ecef(station) for station in pair
        }
        satellites = tuple(sorted(records))

        @lru_cache(maxsize=None)
        def positions(satellite: str, offset_s: float = 0.0) -> np.ndarray:
            shifted = tuple(epoch + timedelta(seconds=offset_s) for epoch in epochs)
            return np.asarray(
                [
                    screen.broadcast_ecef(
                        screen.select_ephemeris(records[satellite], epoch), epoch
                    )
                    for epoch in shifted
                ]
            )

        candidates = []
        for candidate in geometry["shortlist"]:
            compiled = envelope.compile_candidate(
                candidate,
                records,
                epochs,
                epoch_index,
                satellites,
                station_ecef,
                positions,
            )
            compiled["input_window"] = {
                "start_utc": candidate["start_utc"],
                "stop_utc": candidate["stop_utc"],
                "start_observation_epoch_gps": candidate[
                    "start_observation_epoch_gps"
                ],
                "stop_observation_epoch_gps": candidate[
                    "stop_observation_epoch_gps"
                ],
                "records": candidate["records"],
                "minimum_elevation_deg": candidate["minimum_elevation_deg"],
            }
            candidates.append(compiled)
    finally:
        screen.STATIONS = previous

    candidates.sort(
        key=lambda row: (
            -row["remaining_physical_margin_hz"],
            row["start_utc"],
            row["target"],
            row["reference"],
        )
    )
    calibration_known = all(station.antenna_calibration == "ROBOT" for station in pair)
    return {
        "pair_id": pair_id,
        "stations": [asdict(station) for station in pair],
        "candidate_windows": geometry["candidate_windows"],
        "candidate_envelopes": candidates,
        "antenna_calibration_provenance": (
            "ADMITTED_IGS_ROBOT" if calibration_known else "UNKNOWN"
        ),
        "pair_selection_state": (
            "ELIGIBLE_FOR_NAVIGATION_ONLY_SELECTION"
            if calibration_known
            else "EXCLUDED_ANTENNA_CALIBRATION_PROVENANCE_UNKNOWN"
        ),
    }


def select_candidate(pair_results: Sequence[dict[str, object]]) -> dict[str, object] | None:
    eligible = []
    for pair in pair_results:
        candidates = pair.get("candidate_envelopes", ())
        if pair.get("pair_selection_state") != "ELIGIBLE_FOR_NAVIGATION_ONLY_SELECTION":
            continue
        if not candidates or candidates[0]["remaining_physical_margin_hz"] <= 0:
            continue
        eligible.append(
            {
                "pair_id": pair["pair_id"],
                "stations": pair["stations"],
                "candidate": candidates[0],
            }
        )
    if not eligible:
        return None
    eligible.sort(
        key=lambda row: (
            -row["candidate"]["remaining_physical_margin_hz"], row["pair_id"]
        )
    )
    return eligible[0]


def product_roles() -> dict[str, list[dict[str, object]]]:
    return {
        role: [
            {
                **product,
                "sha256": None,
                "payload_opened": False,
                "header_opened": False,
                "head_is_not_field_topology_evidence": True,
            }
            for product in products
        ]
        for role, products in PRODUCT_ROLES.items()
    }


def review_manifest() -> dict[str, object]:
    return {
        "review_version": REVIEW_VERSION,
        "navigation_sha256": screen.NAVIGATION_SHA256,
        "screen_version": screen.SCREEN_VERSION,
        "envelope_version": envelope.COMPILER_VERSION,
        "stations": {key: asdict(value) for key, value in sorted(STATIONS.items())},
        "candidate_pairs": [list(spec) for spec in PAIR_SPECS],
        "product_roles": product_roles(),
        "selection_order": [
            "DOCUMENTED_ANTENNA_CALIBRATION_PROVENANCE",
            "POSITIVE_PAIRWISE_PHYSICAL_MARGIN",
            "MAXIMUM_REMAINING_PHYSICAL_MARGIN",
            "PAIR_ID_TIE_BREAK",
        ],
        "forbidden": [
            "RINEX_OBSERVATION_PAYLOAD_ACCESS",
            "OBSERVATION_HEADER_ACCESS",
            "TARGET_OR_SIGNAL_SELECTION_FROM_MEASUREMENTS",
            "REUSE_OR_RETRY_OF_CLOSED_GOLD_NLIB_PRIMARY",
            "PROSPECTIVE_PLAN_FREEZE",
            "PRIMARY_ACCESS_AUTHORITY",
            "NEW_GATE",
        ],
    }


def review_manifest_sha256() -> str:
    return sha256(strict_json(review_manifest()).encode("ascii")).hexdigest()


def strict_json(value: object) -> str:
    return json.dumps(
        value, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("navigation", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    payload = strict_json(review_navigation(arguments.navigation)) + "\n"
    if arguments.output is None:
        print(payload, end="")
    else:
        arguments.output.write_text(payload, encoding="ascii", newline="\n")
