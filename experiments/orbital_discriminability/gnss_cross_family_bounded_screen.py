"""Bounded metadata/orbit-only screen for one cross-family GNSS observer.

The five station roots are frozen before any observation-product access.  The
compiler accepts only the three previously frozen broadcast-navigation files;
it has no observation locator, header, decoder, carrier-phase or value input.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from hashlib import sha256
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
from typing import Final, Mapping

import numpy as np

from experiments.orbital_discriminability import (
    gnss_observer_transfer_geometry as inherited,
)


SCREEN_VERSION: Final = "gnss-cross-family-bounded-screen-v1"
RECEIPT_NAME: Final = "GNSS_CROSS_FAMILY_BOUNDED_SCREEN_RECEIPT.json"
OUTCOME_SHORTLISTED: Final = "CROSS_FAMILY_GEOMETRY_SHORTLISTED"
OUTCOME_NONE: Final = "NO_CROSS_FAMILY_GEOMETRY_SHORTLISTED"

TARGET: Final = inherited.TARGET
REFERENCE: Final = inherited.REFERENCE
NAVIGATION_CANDIDATES: Final = inherited.NAVIGATION_CANDIDATES
SHORTLIST_SIZE: Final = 3
POST_AMC_REVIEW_NAME: Final = "POST_AMC_NEXT_INFORMATION_REVIEW.md"
POST_AMC_REVIEW_SHA256: Final = (
    "6fb55c9b0fa4f454ca35bd00d7c1a1a0306f4ab110e0fac3e2ba2087296f5bd1"
)


@dataclass(frozen=True, slots=True)
class CandidateRoot:
    station_id: str
    latitude_deg: float
    longitude_deg: float
    height_m: float
    domes: str
    receiver: str
    receiver_serial: str
    receiver_firmware: str
    receiver_effective: str
    receiver_family: str
    antenna: str
    antenna_serial: str
    antenna_effective: str
    frequency_standard: str
    frequency_standard_effective: str
    site_log_prepared: str
    station_page_url: str
    station_log_url: str
    station_log_bytes: int
    station_log_sha256: str
    metadata_state: str
    geometry_evaluated: bool
    admission_state: str
    exact_blocker: str


CANDIDATES: Final = (
    CandidateRoot(
        "WES200USA",
        42.61333611111111,
        -71.49332777777778,
        85.0,
        "40440S020",
        "TRIMBLE ALLOY",
        "6026R40020",
        "6.50",
        "2026-07-15T23:59Z",
        "TRIMBLE_ALLOY",
        "TWIVC6150 SCIS",
        "202109220003",
        "2023-08-14T18:00Z",
        "EXTERNAL_H_MASER_10_MHZ",
        "2021-02-26/OPEN",
        "2026-07-20",
        "https://network.igs.org/WES200USA",
        "https://network.igs.org/api/public/download/WES200USA.log?lower_case=1",
        45_228,
        "3afc9bfee52fe06e76cda8dbb2a75bcb4f68bbbb44f5e44b0ebb9c62f2115d76",
        "OFFICIAL_SITE_LOG_HASHED",
        True,
        "CAPABILITY_REJECTED_SIGNAL_PRODUCT_SEMANTICS",
        "KNOWN_RINEX2_FEED_DOES_NOT_ESTABLISH_EXPLICIT_L1C_L2W_IDENTITY",
    ),
    CandidateRoot(
        "WTZR00DEU",
        49.14419722222222,
        12.878908333333333,
        666.0,
        "14201M010",
        "LEICA GR50",
        "1831551",
        "4.50/7.710",
        "2021-05-18T12:30Z",
        "LEICA_GR50",
        "LEIAR25.R3 LEIT",
        "10020031",
        "2010-06-30T08:00Z",
        "EXTERNAL_H_MASER_EFOS18_5_MHZ",
        "2013-05-13/OPEN",
        "2023-10-30",
        "https://network.igs.org/WTZR00DEU",
        "https://network.igs.org/api/public/download/WTZR00DEU.log?lower_case=1",
        55_377,
        "56e0fcfc69d28596d92bedc523c7b077646521e775b403e35c39488183565ca7",
        "OFFICIAL_SITE_LOG_HASHED",
        True,
        "METADATA_ADMITTED_GEOMETRY_ONLY",
        "OBSERVATION_PRODUCT_SIGNAL_FIELDS_AND_WINDOW_COVERAGE_UNKNOWN_NOT_QUERIED",
    ),
    CandidateRoot(
        "ZIMM00CHE",
        46.87709444444444,
        7.465272222222222,
        956.4,
        "14001M004",
        "LEICA GR50",
        "1873172",
        "4.90/7.905",
        "2026-05-07T08:25Z",
        "LEICA_GR50",
        "TRM29659.00 NONE",
        "99390",
        "1999-07-02T00:00Z",
        "INTERNAL",
        "1993-05-01/OPEN",
        "2026-05-07",
        "https://network.igs.org/ZIMM00CHE",
        "https://network.igs.org/api/public/download/ZIMM00CHE.log?lower_case=1",
        25_157,
        "d016f9dcc105aa2dfe3ed5f65f1813fa94ce29dd84b63091a565f39bc553080f",
        "OFFICIAL_SITE_LOG_HASHED",
        True,
        "METADATA_ADMITTED_GEOMETRY_ONLY",
        "OBSERVATION_PRODUCT_SIGNAL_FIELDS_AND_WINDOW_COVERAGE_UNKNOWN_NOT_QUERIED",
    ),
    CandidateRoot(
        "TSKB00JPN",
        36.10568055555556,
        140.08749722222223,
        67.3,
        "21730S005",
        "TRIMBLE ALLOY",
        "6032R40037",
        "6.15",
        "2022-10-18T00:00Z",
        "TRIMBLE_ALLOY",
        "AOAD/M_T DOME",
        "312",
        "2017-05-17T08:20Z",
        "EXTERNAL_CESIUM_10_MHZ",
        "2017-04-24/OPEN",
        "2022-10-18",
        "https://network.igs.org/TSKB00JPN",
        "https://network.igs.org/api/public/download/TSKB00JPN.log?lower_case=1",
        24_508,
        "0aefc2404998f6e283267dc56007eb440efa6f1e9d5eaf39c120e6014092781e",
        "OFFICIAL_SITE_LOG_HASHED",
        True,
        "METADATA_ADMITTED_GEOMETRY_ONLY",
        "OBSERVATION_PRODUCT_SIGNAL_FIELDS_AND_WINDOW_COVERAGE_UNKNOWN_NOT_QUERIED",
    ),
    CandidateRoot(
        "HOB200AUS",
        -42.804705555555555,
        147.43873611111112,
        41.0,
        "50116M004",
        "SEPT POLARX5",
        "3012296",
        "5.7.0",
        "2026-07-31T02:49Z",
        "SEPTENTRIO_POLARX5",
        "LEIAR25.R4 NONE",
        "726829",
        "2021-12-17T00:00Z",
        "EXTERNAL_H_MASER_10_MHZ",
        "2023-03-27/OPEN",
        "2026-07-31",
        "https://network.igs.org/HOB200AUS",
        "https://network.igs.org/api/public/download/HOB200AUS.log?lower_case=1",
        27_585,
        "bc5d67bc3f01b72b649295c5b491f8ebdad7cc1b3d12fc0076da9e128c496760",
        "OFFICIAL_SITE_LOG_HASHED",
        False,
        "CAPABILITY_REJECTED_RECEIVER_FAMILY",
        "SEPTENTRIO_POLARX5_DOES_NOT_TEST_CROSS_RECEIVER_FAMILY_TRANSFER",
    ),
)


class CrossFamilyScreenError(ValueError):
    """A frozen authority, bounded scope or numerical invariant changed."""


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
    return sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


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


def validate_scope(root: Path) -> None:
    ids = tuple(candidate.station_id for candidate in CANDIDATES)
    if ids != (
        "WES200USA",
        "WTZR00DEU",
        "ZIMM00CHE",
        "TSKB00JPN",
        "HOB200AUS",
    ):
        raise CrossFamilyScreenError("CANDIDATE_SCOPE_CHANGED")
    if len(CANDIDATES) > 5:
        raise CrossFamilyScreenError("BOUNDED_ROOT_LIMIT_EXCEEDED")
    if set(ids) & {"GOLD00USA", "NLIB00USA", "ALGO00CAN", "MDO100USA"}:
        raise CrossFamilyScreenError("CONSUMED_ROOT_REENTERED")
    review = Path(root) / POST_AMC_REVIEW_NAME
    if not review.is_file() or canonical_sha256(review) != POST_AMC_REVIEW_SHA256:
        raise CrossFamilyScreenError("POST_AMC_REVIEW_CHANGED")


def manifest(root: Path | None = None) -> dict[str, object]:
    base = Path(__file__).resolve().parent if root is None else Path(root)
    validate_scope(base)
    value = {
        "schema": "gnss-cross-family-bounded-screen-manifest-v1",
        "screen_version": SCREEN_VERSION,
        "physical_question": (
            "DOES_G22_MINUS_G30_ORBITAL_DISCRIMINABILITY_SURVIVE_AT_ONE_"
            "OBSERVER_WITH_A_RECEIVER_FAMILY_DISTINCT_FROM_THE_CONSUMED_SEPTENTRIO_PATH"
        ),
        "new_information": (
            "WHICH_PREDECLARED_NON_SEPTENTRIO_ROOT_HAS_POSITIVE_HELDOUT_"
            "GEOMETRY_BEFORE_ANY_OBSERVATION_PRODUCT_IS_OPENED"
        ),
        "why_existing_experiment_cannot_answer": (
            "AMC_AND_PIE_USED_SEPTENTRIO_RECEIVERS_AND_WES_WAS_REFUSED_FOR_"
            "AMBIGUOUS_SIGNAL_PRODUCT_SEMANTICS"
        ),
        "minimum_experiment": (
            "FIVE_PREDECLARED_OFFICIAL_SITE_LOGS_AND_THREE_ALREADY_FROZEN_"
            "BROADCAST_ORBIT_DAYS_WITH_ZERO_OBSERVATION_ACCESS"
        ),
        "stop_condition": (
            "STOP_WITH_AT_MOST_THREE_GEOMETRY_POSITIVE_NON_SEPTENTRIO_ROOTS_"
            "OR_NO_CROSS_FAMILY_GEOMETRY"
        ),
        "review_authority": {
            "filename": POST_AMC_REVIEW_NAME,
            "canonical_sha256": POST_AMC_REVIEW_SHA256,
        },
        "candidate_roots": [asdict(candidate) for candidate in CANDIDATES],
        "candidate_scope_predeclared": True,
        "candidate_limit": 5,
        "candidate_navigation": [
            asdict(candidate) for candidate in NAVIGATION_CANDIDATES
        ],
        "coordinate_and_nulls": inherited.manifest()["coordinate"],
        "visibility": inherited.manifest()["visibility"],
        "physical_envelope": inherited.manifest()["physical_envelope"],
        "selection_rule": [
            "RECEIVER_FAMILY_NOT_SEPTENTRIO_POLARX5",
            "NO_PRIOR_TYPED_CAPABILITY_REJECTION",
            "STRICT_POSITIVE_REMAINING_PHYSICAL_MARGIN",
            "BEST_DATE_WINDOW_PER_DISTINCT_ROOT",
            "MAXIMUM_REMAINING_PHYSICAL_MARGIN",
            "MAXIMUM_MINIMUM_MODEL_ELEVATION",
        ],
        "observation_boundary": {
            "product_locators": 0,
            "products_discovered": 0,
            "headers": 0,
            "payload_bytes": 0,
            "values": 0,
            "decoder_present": False,
        },
        "prospective_plan_frozen": False,
        "primary_selected": False,
        "new_gate": False,
        "generic_framework": False,
    }
    strict_json(value)
    return value


def manifest_sha256(root: Path | None = None) -> str:
    return sha256(strict_json(manifest(root)).encode("ascii")).hexdigest()


def _eligible(candidate: CandidateRoot) -> bool:
    return (
        candidate.geometry_evaluated
        and candidate.admission_state == "METADATA_ADMITTED_GEOMETRY_ONLY"
    )


def compile_screen(payloads: Mapping[int, bytes], root: Path) -> dict[str, object]:
    validate_scope(root)
    records_by_doy, navigation_authority = inherited._parse_navigation_payloads(
        payloads
    )
    cases: list[dict[str, object]] = []
    for navigation_candidate in NAVIGATION_CANDIDATES:
        day_cache: dict[tuple[str, float], np.ndarray] = {}
        for observer in CANDIDATES:
            if not observer.geometry_evaluated:
                continue
            row = inherited.compile_station_day(
                navigation_candidate,
                records_by_doy[navigation_candidate.doy],
                observer,  # structural CandidateStation protocol
                day_cache,
            )
            row["receiver_family"] = observer.receiver_family
            row["metadata_admission_state"] = observer.admission_state
            row["capability_blocker"] = observer.exact_blocker
            cases.append(row)
        for values in day_cache.values():
            values.fill(0.0)

    best_windows = [
        case["best_window"]
        for case in cases
        if case["best_window"] is not None
    ]
    geometry_ranking = inherited.rank_distinct_observers(best_windows)
    eligible_ids = {
        candidate.station_id for candidate in CANDIDATES if _eligible(candidate)
    }
    shortlist = [
        row for row in geometry_ranking if row["station_id"] in eligible_ids
    ][:SHORTLIST_SIZE]
    result = {
        "schema": "gnss-cross-family-bounded-screen-receipt-v1",
        "screen_version": SCREEN_VERSION,
        "source_commit": _git_commit(),
        "source_sha256": source_sha256(),
        "dependencies": dependency_versions(),
        "manifest_sha256": manifest_sha256(root),
        "metadata_authority": [asdict(candidate) for candidate in CANDIDATES],
        "navigation": navigation_authority,
        "case_results": cases,
        "geometry_ranking_including_prior_refusal": geometry_ranking,
        "cross_family_shortlist": shortlist,
        "recommended_qualification_root": (
            shortlist[0]["station_id"] if shortlist else None
        ),
        "outcome": OUTCOME_SHORTLISTED if shortlist else OUTCOME_NONE,
        "observation_access": {
            "product_locators": 0,
            "products_discovered": 0,
            "headers": 0,
            "payload_bytes": 0,
            "values": 0,
        },
        "qualification_artifact_selected": False,
        "primary_selected": False,
        "prospective_plan_frozen": False,
        "exact_remaining_blocker": (
            "ONE_DISTINCT_QUALIFICATION_ARTIFACT_MUST_PROVE_RINEX3_L1C_L2W_"
            "LLI_C1C_C2W_FULL_WINDOW_AND_RECEIVER_CONFIGURATION_CONTINUITY"
            if shortlist
            else "NO_GEOMETRY_POSITIVE_CROSS_FAMILY_ROOT"
        ),
        "next_maximum": (
            "REVIEW_BEFORE_ONE_ROOT_ONE_QUALIFICATION_ARTIFACT_DISCOVERY"
            if shortlist
            else "STOP_TRADITIONAL_GNSS_REPLICATION"
        ),
        "stop": "NO_OBSERVATION_PRODUCT_DISCOVERY_OR_ACCESS",
        "new_gate_created": False,
    }
    strict_json(result)
    return result


def _write_json(path: Path, value: object) -> None:
    if Path(path).exists():
        raise CrossFamilyScreenError("SCREEN_RECEIPT_ALREADY_EXISTS")
    Path(path).write_bytes((strict_json(value, pretty=True) + "\n").encode("ascii"))


def main() -> None:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--navigation-gzip", type=Path, action="append", required=True
    )
    parser.add_argument("--output", type=Path, default=root / RECEIPT_NAME)
    args = parser.parse_args()
    supplied = {path.name: path for path in args.navigation_gzip}
    expected = {candidate.name: candidate for candidate in NAVIGATION_CANDIDATES}
    if len(supplied) != len(args.navigation_gzip) or set(supplied) != set(expected):
        raise SystemExit("SUPPLY_EXACTLY_THE_THREE_FROZEN_NAVIGATION_PRODUCTS")
    payloads = {
        expected[name].doy: path.read_bytes() for name, path in supplied.items()
    }
    try:
        receipt = compile_screen(payloads, root)
    finally:
        payloads.clear()
    _write_json(args.output, receipt)
    print(strict_json(receipt))


if __name__ == "__main__":
    main()
