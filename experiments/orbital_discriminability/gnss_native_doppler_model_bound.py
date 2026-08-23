"""Navigation-only G15/G22 broadcast model-bound audit.

The input surface contains three exact-hash BRDM navigation products.  RINEX
observation products, carrier phase, Doppler, SNR, and receiver diagnostics are
deliberately outside this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import gzip
from hashlib import sha256
import importlib.metadata
import json
from pathlib import Path
from typing import Final, Sequence

import numpy as np

from experiments.orbital_discriminability import gnss_double_difference_screen as screen
from experiments.orbital_discriminability import gnss_native_doppler_transfer as transfer


MODEL_BOUND_VERSION: Final = "gnss-native-doppler-broadcast-model-bound-v1"
PLAN_NAME: Final = "GNSS_NATIVE_DOPPLER_MODEL_BOUND_PLAN.md"
PLAN_SHA256: Final = "2ef0cab5802f28c43dbf2ccff982f0ac1304650303f8281f75d20978e80a268d"
ORBITALITY_RECEIPT_NAME: Final = "GNSS_NATIVE_DOPPLER_ORBITALITY_RECEIPT.json"
ORBITALITY_RECEIPT_SHA256: Final = (
    "036413c60dc10f7a0ca41810904b3b081def91288b7b6247522938e005e3d225"
)
TRANSFER_RECEIPT_NAME: Final = "GNSS_NATIVE_DOPPLER_TRANSFER_RECEIPT.json"
TRANSFER_RECEIPT_SHA256: Final = (
    "16e15a2e91712429ebb27f374558d2ab04e1a28b5e376a6317c753ed47055ebb"
)
TARGETS: Final = ("G15", "G22")
RECORDS: Final = 380
STEP_S: Final = 30.0
LEGACY_INTEGRITY_SCALE: Final = 4.42

# RINEX 3.05 A6 nominal metre values produced from the LNAV URA index.
URA_NOMINAL_M_BY_INDEX: Final = (
    2.0, 2.8, 4.0, 5.7, 8.0, 11.3, 16.0, 32.0,
    64.0, 128.0, 256.0, 512.0, 1024.0, 2048.0, 4096.0, 8192.0,
)
# IS-GPS-200N 20.3.3.3.1.3 upper edges. Index 15 has no finite bound.
URA_UPPER_M_BY_INDEX: Final = (
    2.4, 3.4, 4.85, 6.85, 9.65, 13.65, 24.0, 48.0,
    96.0, 192.0, 384.0, 768.0, 1536.0, 3072.0, 6144.0, None,
)


@dataclass(frozen=True, slots=True)
class NavigationProduct:
    doy: int
    name: str
    bytes: int
    sha256: str
    compressed_bytes: int
    compressed_sha256: str
    url: str

    @property
    def compressed_name(self) -> str:
        return self.name + ".gz"


NAVIGATION_PRODUCTS: Final = (
    NavigationProduct(
        219,
        "BRDM00DLR_S_20262190000_01D_MN.rnx",
        8_383_950,
        "8d5126ae5a7a8ad1e718c11a1c575c0961de1c57845ca15da4081e65e5709b5d",
        1_391_036,
        "12246e0e614f0a16c9bd7329ddd637fb541d478160d944131023aa9faeffcc3d",
        "https://igs.bkg.bund.de/root_ftp/IGS/BRDC/2026/219/BRDM00DLR_S_20262190000_01D_MN.rnx.gz",
    ),
    NavigationProduct(
        220,
        "BRDM00DLR_S_20262200000_01D_MN.rnx",
        8_285_778,
        "8ac8cd5327b84295436875b57cd88f6d7a45fa666acc5094be13fe56990d0df3",
        1_373_719,
        "13993e96bebf24c5bc515ac2a0f75170804e41bc3aadf066a9ec1b4e41c34b32",
        "https://igs.bkg.bund.de/root_ftp/IGS/BRDC/2026/220/BRDM00DLR_S_20262200000_01D_MN.rnx.gz",
    ),
    NavigationProduct(
        221,
        "BRDM00DLR_S_20262210000_01D_MN.rnx",
        8_350_983,
        "4154a7de011292d188a7e3abe1898bc6e19490e9550771c076165df8331f39ed",
        1_392_968,
        "57dd413d0673311cb1813d0c14322edbb43f72636e8be547a8f3f30983c78b08",
        "https://igs.bkg.bund.de/root_ftp/IGS/BRDC/2026/221/BRDM00DLR_S_20262210000_01D_MN.rnx.gz",
    ),
)


class ModelBoundAuditError(ValueError):
    """Frozen authority, navigation metadata, or admission is invalid."""


def bytes_sha256(value: bytes) -> str:
    return sha256(value).hexdigest()


def file_sha256(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def strict_json(value: object) -> str:
    _validate_standard_json(value)
    return json.dumps(
        value, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    )


def _validate_standard_json(value: object) -> None:
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float:
        if not np.isfinite(value):
            raise ValueError("NONFINITE_JSON_SCALAR")
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _validate_standard_json(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if type(key) is not str:
                raise TypeError("NONSTRING_JSON_KEY")
            _validate_standard_json(item)
        return
    raise TypeError(f"NONSTANDARD_JSON_SCALAR:{type(value).__name__}")


def load_exact(root: Path, name: str, expected_sha256: str) -> dict[str, object]:
    path = Path(root) / name
    if not path.is_file() or file_sha256(path) != expected_sha256:
        raise ModelBoundAuditError(f"FROZEN_LINEAGE_MISMATCH:{name}")
    try:
        return json.loads(
            path.read_text(encoding="ascii"),
            parse_constant=lambda item: (_ for _ in ()).throw(ValueError(item)),
        )
    except (UnicodeError, ValueError, TypeError) as exc:
        raise ModelBoundAuditError(f"INVALID_STRICT_JSON:{name}") from exc


def parse_all_gps_navigation(raw: bytes) -> dict[str, tuple[screen.GpsEphemeris, ...]]:
    try:
        lines = raw.decode("ascii").splitlines()
    except UnicodeError as exc:
        raise ModelBoundAuditError("NAVIGATION_NOT_ASCII") from exc
    try:
        start = next(
            index for index, line in enumerate(lines) if "END OF HEADER" in line
        ) + 1
    except StopIteration as exc:
        raise ModelBoundAuditError("RINEX_HEADER_INCOMPLETE") from exc
    records: dict[str, list[screen.GpsEphemeris]] = {}
    for index in range(start, len(lines)):
        if not lines[index].startswith("G"):
            continue
        if index + 7 >= len(lines):
            raise ModelBoundAuditError("TRUNCATED_GPS_NAVIGATION_RECORD")
        try:
            record = screen.parse_gps_record(lines[index : index + 8])
        except (ValueError, IndexError) as exc:
            raise ModelBoundAuditError("INVALID_GPS_NAVIGATION_RECORD") from exc
        if record.satellite in TARGETS:
            records.setdefault(record.satellite, []).append(record)
    if set(records) != set(TARGETS):
        raise ModelBoundAuditError("G15_G22_RECORDS_MISSING")
    return {
        satellite: tuple(sorted(values, key=lambda item: item.toc_gps))
        for satellite, values in records.items()
    }


def select_latest_record(
    records: Sequence[screen.GpsEphemeris], model_utc: datetime
) -> tuple[screen.GpsEphemeris, float]:
    gps_epoch = model_utc + timedelta(seconds=screen.GPS_UTC_OFFSET_S)
    eligible = [record for record in records if record.toc_gps <= gps_epoch]
    if not eligible:
        raise ModelBoundAuditError("NO_EPHEMERIS_AT_OR_BEFORE_EPOCH")
    selected = eligible[-1]
    age_s = float((gps_epoch - selected.toc_gps).total_seconds())
    if not np.isfinite(age_s) or age_s < 0.0 or age_s > screen.MAX_EPHEMERIS_AGE_S:
        raise ModelBoundAuditError("EPHEMERIS_AGE_OUTSIDE_FROZEN_LIMIT")
    if selected.sv_health != 0:
        raise ModelBoundAuditError("SELECTED_EPHEMERIS_UNHEALTHY")
    if selected.fit_interval_h is None or not np.isfinite(selected.fit_interval_h):
        raise ModelBoundAuditError("EPHEMERIS_FIT_INTERVAL_UNKNOWN")
    if selected.fit_interval_h <= 0.0 or age_s > selected.fit_interval_h * 3600.0:
        raise ModelBoundAuditError("EPHEMERIS_OUTSIDE_DECLARED_FIT_INTERVAL")
    return selected, age_s


def ura_index_from_rinex_nominal(value_m: float) -> int:
    if not np.isfinite(value_m) or value_m <= 0.0:
        raise ModelBoundAuditError("INVALID_RINEX_SV_ACCURACY")
    matches = [
        index
        for index, nominal in enumerate(URA_NOMINAL_M_BY_INDEX)
        if abs(value_m - nominal) <= 1e-6
    ]
    if len(matches) != 1 or matches[0] == 15:
        raise ModelBoundAuditError("RINEX_SV_ACCURACY_HAS_NO_FINITE_URA_BOUND")
    return matches[0]


def integrity_interval_m(nominal_m: float) -> tuple[int, float, float]:
    index = ura_index_from_rinex_nominal(nominal_m)
    upper_m = URA_UPPER_M_BY_INDEX[index]
    if upper_m is None:
        raise ModelBoundAuditError("RINEX_SV_ACCURACY_HAS_NO_FINITE_URA_BOUND")
    return index, float(upper_m), float(LEGACY_INTEGRITY_SCALE * upper_m)


def exact_grid(candidate: dict[str, object]) -> tuple[datetime, ...]:
    start = datetime.fromisoformat(
        str(candidate["start_model_epoch_utc"]).replace("Z", "+00:00")
    )
    stop = datetime.fromisoformat(
        str(candidate["stop_model_epoch_utc"]).replace("Z", "+00:00")
    )
    epochs = tuple(start + timedelta(seconds=index * STEP_S) for index in range(RECORDS))
    if epochs[-1] != stop or int(candidate["records"]) != RECORDS:
        raise ModelBoundAuditError("FROZEN_HEADER_GRID_CHANGED")
    return epochs


def audit_selected_records(
    records: dict[str, tuple[screen.GpsEphemeris, ...]],
    epochs: Sequence[datetime],
) -> tuple[list[dict[str, object]], float]:
    rows: list[dict[str, object]] = []
    maximum_interval_m = 0.0
    for satellite in TARGETS:
        selections = [select_latest_record(records[satellite], epoch) for epoch in epochs]
        selected_records = [item[0] for item in selections]
        ages = [item[1] for item in selections]
        accuracy_rows = [
            integrity_interval_m(float(record.sv_accuracy_m))
            for record in selected_records
        ]
        maximum_interval_m = max(maximum_interval_m, max(item[2] for item in accuracy_rows))
        unique_records = {
            (
                record.toc_gps.isoformat(),
                float(record.iode),
                float(record.sv_accuracy_m),
                float(record.fit_interval_h),
            )
            for record in selected_records
        }
        rows.append(
            {
                "satellite": satellite,
                "epochs_selected": len(selected_records),
                "selected_health_values": sorted({record.sv_health for record in selected_records}),
                "unique_selected_records": len(unique_records),
                "unique_iode_values": sorted({float(record.iode) for record in selected_records}),
                "fit_interval_h_values": sorted(
                    {float(record.fit_interval_h) for record in selected_records}
                ),
                "maximum_ephemeris_age_s": float(max(ages)),
                "rinex_nominal_sv_accuracy_m_values": sorted(
                    {float(record.sv_accuracy_m) for record in selected_records}
                ),
                "ura_index_values": sorted({item[0] for item in accuracy_rows}),
                "ura_category_upper_m_values": sorted({item[1] for item in accuracy_rows}),
                "legacy_integrity_interval_m_values": sorted({item[2] for item in accuracy_rows}),
            }
        )
    return rows, float(maximum_interval_m)


def validate_and_decompress(root: Path, product: NavigationProduct) -> tuple[bytes, dict[str, object]]:
    path = Path(root) / product.compressed_name
    if not path.is_file():
        raise ModelBoundAuditError(f"NAVIGATION_PRODUCT_MISSING:{product.compressed_name}")
    compressed = path.read_bytes()
    if len(compressed) != product.compressed_bytes or bytes_sha256(compressed) != product.compressed_sha256:
        raise ModelBoundAuditError(f"COMPRESSED_NAVIGATION_IDENTITY_MISMATCH:{product.compressed_name}")
    try:
        raw = gzip.decompress(compressed)
    except (OSError, EOFError) as exc:
        raise ModelBoundAuditError(f"NAVIGATION_DECOMPRESSION_FAILED:{product.compressed_name}") from exc
    if len(raw) != product.bytes or bytes_sha256(raw) != product.sha256:
        raise ModelBoundAuditError(f"NAVIGATION_IDENTITY_MISMATCH:{product.name}")
    return raw, {
        "name": product.name,
        "bytes": len(raw),
        "sha256": product.sha256,
        "compressed_name": product.compressed_name,
        "compressed_bytes": len(compressed),
        "compressed_sha256": product.compressed_sha256,
        "semantics": "BROADCAST_EPHEMERIS_MODEL_NOT_RECEIVER_OBSERVATION",
    }


def compiler_manifest() -> dict[str, object]:
    return {
        "version": MODEL_BOUND_VERSION,
        "plan_sha256": PLAN_SHA256,
        "compiler_source_sha256": file_sha256(Path(__file__)),
        "dependencies": {"numpy": importlib.metadata.version("numpy")},
        "lineage": {
            "orbitality_receipt_sha256": ORBITALITY_RECEIPT_SHA256,
            "transfer_receipt_sha256": TRANSFER_RECEIPT_SHA256,
        },
        "selection": {
            "satellites": list(TARGETS),
            "epochs": RECORDS,
            "step_s": STEP_S,
            "latest_record_at_or_before_epoch": True,
            "unhealthy_records_not_discarded_before_selection": True,
            "maximum_age_s": screen.MAX_EPHEMERIS_AGE_S,
            "known_positive_fit_interval_required": True,
        },
        "model_interval": {
            "state": "MODELED_INTERVAL_WITH_LEGACY_INTEGRITY_ASSURANCE",
            "formula": "4.42*UPPER_EDGE_OF_SELECTED_LNAV_URA_CATEGORY",
            "legacy_integrity_scale": LEGACY_INTEGRITY_SCALE,
            "rinex_field_is_nominal_ura_m_not_index": True,
            "index_15_refused": True,
            "deterministic_mathematical_worst_case_claimed": False,
            "pure_orbit_only_error_claimed": False,
            "overlap_with_other_sis_terms_subtracted": False,
        },
        "references": {
            "rinex_3_05": "https://files.igs.org/pub/data/format/rinex305.pdf",
            "is_gps_200n": "https://archive.gps.gov/technical/icwg/IS-GPS-200N.pdf",
        },
        "observation_access_forbidden": True,
        "new_gate_created": False,
    }


def compiler_manifest_sha256() -> str:
    return sha256(strict_json(compiler_manifest()).encode("ascii")).hexdigest()


def verify_parent_navigation_specs(orbitality: dict[str, object]) -> None:
    sources = orbitality.get("navigation_sources")
    if not isinstance(sources, list):
        raise ModelBoundAuditError("PARENT_NAVIGATION_SOURCES_MISSING")
    by_doy = {int(source["name"][16:19]): source for source in sources}
    for product in NAVIGATION_PRODUCTS:
        source = by_doy.get(product.doy)
        expected = {
            "name": product.name,
            "bytes": product.bytes,
            "sha256": product.sha256,
            "compressed_bytes": product.compressed_bytes,
            "compressed_sha256": product.compressed_sha256,
            "url": product.url,
            "semantics": "BROADCAST_EPHEMERIS_MODEL_NOT_RECEIVER_OBSERVATION",
        }
        if source != expected:
            raise ModelBoundAuditError(f"PARENT_NAVIGATION_SPEC_CHANGED:DOY{product.doy}")


def compile_model_bound(root: Path, navigation_root: Path) -> dict[str, object]:
    root = Path(root)
    if file_sha256(root / PLAN_NAME) != PLAN_SHA256:
        raise ModelBoundAuditError("FROZEN_PLAN_MISMATCH")
    orbitality = load_exact(root, ORBITALITY_RECEIPT_NAME, ORBITALITY_RECEIPT_SHA256)
    frozen_transfer = load_exact(root, TRANSFER_RECEIPT_NAME, TRANSFER_RECEIPT_SHA256)
    if orbitality.get("outcome") != "NATIVE_DOPPLER_ORBITALITY_GEOMETRY_SHORTLIST_READY":
        raise ModelBoundAuditError("ORBITALITY_SHORTLIST_NOT_READY")
    if frozen_transfer.get("outcome") != "NATIVE_DOPPLER_TRANSFER_RULE_FROZEN_MODEL_BOUND_REQUIRED":
        raise ModelBoundAuditError("TRANSFER_RULE_NOT_FROZEN")
    verify_parent_navigation_specs(orbitality)
    shortlist = orbitality.get("shortlist")
    transfer_audits = frozen_transfer.get("candidate_audits")
    if not isinstance(shortlist, list) or not isinstance(transfer_audits, list):
        raise ModelBoundAuditError("FROZEN_CANDIDATES_MISSING")
    candidates = {int(item["doy"]): item for item in shortlist}
    budgets = {int(item["doy"]): item for item in transfer_audits}
    rows: list[dict[str, object]] = []
    all_admitted = True
    for product in NAVIGATION_PRODUCTS:
        candidate = candidates.get(product.doy)
        budget = budgets.get(product.doy)
        if candidate is None or budget is None:
            raise ModelBoundAuditError(f"FROZEN_CANDIDATE_MISSING:DOY{product.doy}")
        raw, artifact = validate_and_decompress(navigation_root, product)
        records = parse_all_gps_navigation(raw)
        epochs = exact_grid(candidate)
        satellites, modeled_interval_m = audit_selected_records(records, epochs)
        maximum_admissible_m = float(
            budget["maximum_admissible_broadcast_orbit_per_link_path_bound_m"]
        )
        fixed_path_m = float(budget["fixed_non_orbit_path_bound_m"])
        coefficient = float(budget["path_projection_hz_per_m"])
        geometry_margin_hz = float(budget["geometry_margin_after_clock_hz"])
        physical_envelope_hz = coefficient * (fixed_path_m + modeled_interval_m)
        pairwise_guard_hz = transfer.PAIRWISE_MULTIPLIER * (
            transfer.DEVELOPMENT_ENVELOPE_HZ + physical_envelope_hz
        )
        remaining_margin_hz = geometry_margin_hz - pairwise_guard_hz
        admitted = modeled_interval_m <= maximum_admissible_m and remaining_margin_hz > 0.0
        all_admitted = all_admitted and admitted
        rows.append(
            {
                "prospective_role": candidate["prospective_role"],
                "doy": product.doy,
                "artifact": artifact,
                "grid": {
                    "start_model_epoch_utc": candidate["start_model_epoch_utc"],
                    "stop_model_epoch_utc": candidate["stop_model_epoch_utc"],
                    "epochs": len(epochs),
                    "step_s": STEP_S,
                },
                "satellite_audits": satellites,
                "broadcast_model_interval": {
                    "state": "MODELED_INTERVAL_WITH_LEGACY_INTEGRITY_ASSURANCE",
                    "per_link_path_bound_m": modeled_interval_m,
                    "maximum_admissible_per_link_path_bound_m": maximum_admissible_m,
                    "admitted": admitted,
                },
                "physical_envelope_hz": float(physical_envelope_hz),
                "pairwise_guard_hz": float(pairwise_guard_hz),
                "remaining_margin_hz": float(remaining_margin_hz),
            }
        )
    outcome = (
        "NATIVE_DOPPLER_BROADCAST_MODEL_BOUND_ADMITTED"
        if all_admitted
        else "NATIVE_DOPPLER_BROADCAST_MODEL_BOUND_EXCEEDS_MARGIN"
    )
    result = {
        "outcome": outcome,
        "version": MODEL_BOUND_VERSION,
        "compiler_manifest_sha256": compiler_manifest_sha256(),
        "compiler_manifest": compiler_manifest(),
        "candidate_audits": rows,
        "model_admission": {
            "state": "MODELED_INTERVAL_WITH_LEGACY_INTEGRITY_ASSURANCE",
            "all_candidates_admitted": all_admitted,
            "unresolved_as_zero": False,
        },
        "authority": {
            "primary_plan_frozen": False,
            "primary_observation_access_authorized": False,
            "reserve_observation_access_authorized": False,
        },
        "observation_access": {
            "products_opened": 0,
            "headers_opened": 0,
            "bytes_opened": 0,
            "numeric_values_decoded": 0,
        },
        "claim_scope": "NAVIGATION_ONLY_BROADCAST_SIS_MODEL_BOUND",
        "next_exact_blocker": (
            "FREEZE_EXACT_DOY219_PROSPECTIVE_EVALUATOR_AND_SEPARATE_OBSERVATION_AUTHORITY"
            if all_admitted
            else "BROADCAST_MODEL_INTERVAL_EXCEEDS_FROZEN_PHYSICAL_MARGIN"
        ),
        "new_gate_created": False,
    }
    strict_json(result)
    return result


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("navigation_root", type=Path)
    parser.add_argument(
        "--receipt-root", type=Path, default=Path(__file__).resolve().parent
    )
    args = parser.parse_args()
    print(strict_json(compile_model_bound(args.receipt_root, args.navigation_root)))


if __name__ == "__main__":
    main()
