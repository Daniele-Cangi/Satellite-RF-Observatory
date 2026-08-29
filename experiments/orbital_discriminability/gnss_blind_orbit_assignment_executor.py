"""One-shot executor for the frozen AMC blind-orbit primary.

This experiment-specific module materializes only the predeclared DOY226
product.  It hashes the complete compressed artifact before decoding, applies
the frozen structural and physical admission, and gives the sealed scorer one
unlabelled coordinate.  The opaque score receipt and its hash are persisted
before the identity mapping is read.  Observation values never leave RAM.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import gc
from hashlib import md5, sha256
from importlib import metadata
import json
from pathlib import Path
import platform
import subprocess
from typing import Any, Callable, Final, Mapping, Sequence
from xml.etree import ElementTree

import hatanaka
import numpy as np

from experiments.orbital_discriminability import gnss_observation_header as headers
from experiments.orbital_discriminability import (
    gnss_double_difference_envelope as inherited,
)
from experiments.orbital_discriminability import (
    gnss_phase_short_window_qualification as rinex,
)
from experiments.orbital_discriminability import (
    gnss_blind_orbit_assignment_plan as plan,
)
from experiments.orbital_discriminability import gnss_opaque_orbit_scorer as scorer


EXECUTOR_VERSION: Final = "gnss-blind-orbit-amc-doy226-one-shot-v1"
EXECUTOR_SEAL_NAME: Final = "GNSS_BLIND_ORBIT_ASSIGNMENT_EXECUTOR_SEAL.json"
AUTHORITY_MARKER_NAME: Final = "GNSS_BLIND_ORBIT_ASSIGNMENT_AUTHORITY_CONSUMED.json"
OPAQUE_SCORE_NAME: Final = "GNSS_BLIND_ORBIT_ASSIGNMENT_OPAQUE_SCORE.json"
OPAQUE_SCORE_HASH_NAME: Final = "GNSS_BLIND_ORBIT_ASSIGNMENT_OPAQUE_SCORE_HASH.json"
OUTCOME_NAME: Final = "GNSS_BLIND_ORBIT_ASSIGNMENT_PRIMARY_OUTCOME.json"
AUTHORITY_TOKEN: Final = "AUTHORIZE_AMC_DOY226_BLIND_PRIMARY_ONCE"

PLAN_RECEIPT_SHA256: Final = (
    "b35ccbee73762f7d9a8957f4d72c34ae684447a24fab055712708e064fbf3d9f"
)
PLAN_MANIFEST_SHA256: Final = (
    "f557d09596b1a11dad976aee61bc53d7271eeab1555ac45652404aa41e933e3c"
)
SCORER_SEAL_NAME: Final = "GNSS_BLIND_ORBIT_ASSIGNMENT_PREDICTION_SCORER_SEAL.json"
SCORER_SEAL_SHA256: Final = (
    "2403358fed46293a1c44a9a7576a52c4cac547507abec1da1be5db1c7ff711f4"
)
SCORER_SOURCE_SHA256: Final = (
    "ef064788296caaf0d1d48e2b25621ae99fb935c1a964ac5b9ffc17138a266dda"
)
SCORER_MANIFEST_SHA256: Final = (
    "f15c257561805f4a027a7c42c2664935517c6f5312483d0e30ccc5fdb3d90283"
)

SATELLITES: Final = (plan.TARGET, plan.REFERENCE)
CORE_PHASE: Final = ("L1C", "L2W")
SAME_PATH_CODE: Final = ("C1C", "C2W")
PRIMARY_DIRECTORY_COMPONENTS: Final = tuple(
    part for part in plan.PRIMARY_GSSC_DIRECTORY.split("/") if part
)
GSSC_WEB_ROOT: Final = plan.PRIMARY_GSSC_WEB_ROOT
MAX_TRANSPORT_ATTEMPTS: Final = 2
HTTP_TIMEOUT_S: Final = 120.0
MAX_COMPRESSED_BYTES: Final = 10_000_000
MAX_DIRECTORY_BYTES: Final = 5_000_000

SPEED_OF_LIGHT_M_S: Final = 299_792_458.0
GPS_L1_HZ: Final = 1_575_420_000.0
GPS_L2_HZ: Final = 1_227_600_000.0
LAMBDA_L1_M: Final = SPEED_OF_LIGHT_M_S / GPS_L1_HZ
LAMBDA_L2_M: Final = SPEED_OF_LIGHT_M_S / GPS_L2_HZ
RAW_START: Final = datetime(2026, 8, 14, 6, 14, 30, tzinfo=timezone.utc)
EVENT_TIME_LIMIT_S: Final = 15.0
GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M: Final = 0.09514683639918244
CODE_PHASE_PER_SATELLITE_PTP_LIMIT_M: Final = 1250.0


@dataclass(frozen=True, slots=True)
class ProductPlan:
    station: str
    name: str
    directory_components: tuple[str, ...]


PRIMARY: Final = ProductPlan(
    station=plan.STATION,
    name=plan.PRIMARY_PRODUCT,
    directory_components=PRIMARY_DIRECTORY_COMPONENTS,
)


@dataclass(slots=True)
class StationMeasurement:
    header: dict[str, object]
    phase_cycles: np.ndarray
    code_m: np.ndarray
    event_time_deviation_s: np.ndarray
    structural_counts: dict[str, int]

    def erase(self) -> None:
        self.phase_cycles.fill(0.0)
        self.code_m.fill(0.0)
        self.event_time_deviation_s.fill(0.0)


class BlindOrbitExecutorError(ValueError):
    """A frozen executor, plan, scorer, or receipt invariant changed."""


class BlindingInvalid(ValueError):
    """The scorer/reveal boundary no longer implements the frozen blindness."""


class PrimaryMeasurementInvalid(ValueError):
    """The observation failed a frozen measurement-validity clause."""


class PrimaryNotDetectable(ValueError):
    """The measurement is valid but cannot support the frozen comparison."""


class PrimaryDescriptionError(RuntimeError):
    """Software or descriptive state failed without a physical decision."""


class TransportInterruption(RuntimeError):
    """One pre-hash attempt did not yield a complete artifact."""


class PrimaryMaterializationError(RuntimeError):
    """The bounded pre-hash transport budget was exhausted."""

    def __init__(self, reason: str, receipt: Mapping[str, object]) -> None:
        super().__init__(reason)
        self.receipt = dict(receipt)


Materializer = Callable[[], tuple[bytearray, dict[str, object]]]


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


def _dependency_version(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "UNAVAILABLE"


def dependency_versions() -> dict[str, str]:
    return {
        "hatanaka": getattr(hatanaka, "__version__", "UNKNOWN"),
        "numpy": _dependency_version("numpy"),
        "python": platform.python_version(),
        "requests": _dependency_version("requests"),
    }


def _read_strict_object(path: Path) -> dict[str, object]:
    value = json.loads(
        Path(path).read_text(encoding="ascii"),
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )
    if not isinstance(value, dict):
        raise BlindOrbitExecutorError(f"FROZEN_ARTIFACT_NOT_OBJECT:{path.name}")
    return value


def _require_hash(root: Path, name: str, digest: str) -> Path:
    path = Path(root) / name
    if not path.is_file() or canonical_sha256(path) != digest:
        raise BlindOrbitExecutorError(f"FROZEN_ARTIFACT_CHANGED:{name}")
    return path


def expected_raw_gps_epochs() -> tuple[datetime, ...]:
    epochs = tuple(
        RAW_START + timedelta(seconds=index * plan.STEP_S)
        for index in range(plan.RAW_EPOCHS)
    )
    if epochs[-1] != datetime(2026, 8, 14, 7, 23, 30, tzinfo=timezone.utc):
        raise BlindOrbitExecutorError("FROZEN_GRID_CHANGED")
    return epochs


def _normalize(value: object) -> str:
    return " ".join(str(value).split())


def _required_phase_shift_records(rows: Sequence[object]) -> list[str]:
    result = []
    for value in rows:
        normalized = _normalize(value)
        if normalized.startswith("G L1C") or normalized.startswith("G L2W"):
            result.append(normalized)
    return result


def _expected_header_transform(root: Path) -> dict[str, object]:
    summary_path = _require_hash(
        root,
        plan.QUALIFICATION_SUMMARY_NAME,
        plan.QUALIFICATION_SUMMARY_SHA256,
    )
    summary = _read_strict_object(summary_path)
    header = summary.get("header")
    if not isinstance(header, Mapping):
        raise BlindOrbitExecutorError("QUALIFIED_HEADER_MISSING")
    if summary.get("full_joint_window") is not True:
        raise BlindOrbitExecutorError("QUALIFIED_WINDOW_CHANGED")
    result = {
        "marker_name": header.get("marker_name"),
        "receiver": header.get("receiver"),
        "antenna": header.get("antenna"),
        "receiver_clock_offset_applied": header.get("receiver_clock_offset_applied"),
        "required_phase_shift_records": _required_phase_shift_records(
            header.get("phase_shift_records", [])
        ),
        "applied_bias_records": list(header.get("applied_bias_records", [])),
        "scale_factor_records": [],
    }
    if result["required_phase_shift_records"] != ["G L1C", "G L2W"]:
        raise BlindOrbitExecutorError("QUALIFIED_PHASE_TRANSFORM_CHANGED")
    if result["applied_bias_records"]:
        raise BlindOrbitExecutorError("QUALIFIED_BIAS_TRANSFORM_CHANGED")
    if result["receiver_clock_offset_applied"] != 0:
        raise BlindOrbitExecutorError("QUALIFIED_CLOCK_TRANSFORM_CHANGED")
    strict_json(result)
    return result


def validate_frozen_inputs(root: Path) -> tuple[dict[str, object], dict[str, object]]:
    """Validate exact parents without reading the identity mapping content."""

    root = Path(root)
    receipt_path = _require_hash(root, plan.RECEIPT_NAME, PLAN_RECEIPT_SHA256)
    receipt = _read_strict_object(receipt_path)
    if receipt.get("outcome") != plan.OUTCOME:
        raise BlindOrbitExecutorError("PLAN_OUTCOME_CHANGED")
    if receipt.get("plan_manifest_sha256") != PLAN_MANIFEST_SHA256:
        raise BlindOrbitExecutorError("PLAN_MANIFEST_CHANGED")
    access = receipt.get("access_boundary")
    if not isinstance(access, Mapping) or any(access.values()):
        raise BlindOrbitExecutorError("PLAN_PRIMARY_BOUNDARY_CHANGED")
    _require_hash(root, plan.MAPPING_NAME, plan.MAPPING_SHA256)
    _require_hash(root, scorer.BUNDLE_NAME, scorer.BUNDLE_CANONICAL_SHA256)
    scorer_seal_path = _require_hash(root, SCORER_SEAL_NAME, SCORER_SEAL_SHA256)
    scorer_seal = _read_strict_object(scorer_seal_path)
    if scorer_seal.get("state") != "BLIND_ORBIT_PREDICTION_AND_SCORER_SEALED":
        raise BlindOrbitExecutorError("SCORER_SEAL_STATE_CHANGED")
    if scorer_seal.get("scorer_manifest_sha256") != SCORER_MANIFEST_SHA256:
        raise BlindOrbitExecutorError("SCORER_MANIFEST_CHANGED")
    scorer_info = scorer_seal.get("scorer")
    if not isinstance(scorer_info, Mapping):
        raise BlindOrbitExecutorError("SCORER_SEAL_SURFACE_CHANGED")
    if scorer_info.get("canonical_sha256") != SCORER_SOURCE_SHA256:
        raise BlindOrbitExecutorError("SCORER_SOURCE_BINDING_CHANGED")
    if canonical_sha256(Path(scorer.__file__)) != SCORER_SOURCE_SHA256:
        raise BlindOrbitExecutorError("SCORER_SOURCE_CHANGED")
    authority = scorer_seal.get("authority")
    if not isinstance(authority, Mapping) or any(
        authority.get(field) is not False
        for field in (
            "executor",
            "measurement_score",
            "observation_decode",
            "primary_access",
            "primary_materialization",
        )
    ):
        raise BlindOrbitExecutorError("SCORER_SEAL_GRANTED_AUTHORITY")
    if authority.get("separate_review_required") is not True:
        raise BlindOrbitExecutorError("SCORER_REVIEW_BOUNDARY_CHANGED")
    bundle = scorer.load_exact_bundle(root / scorer.BUNDLE_NAME)
    return bundle, _expected_header_transform(root)


def executor_manifest(root: Path) -> dict[str, object]:
    bundle, transform = validate_frozen_inputs(root)
    result = {
        "schema": "gnss-blind-orbit-assignment-executor-manifest-v1",
        "executor_version": EXECUTOR_VERSION,
        "physical_question": (
            "WHICH_FROZEN_OPAQUE_ORBIT_OR_AFFINE_NULL_BEST_EXPLAINS_ONE_"
            "HELDOUT_AMC_G22_MINUS_G30_COORDINATE"
        ),
        "product": {
            "station": PRIMARY.station,
            "logical_product": PRIMARY.name,
            "directory": "/" + "/".join(PRIMARY.directory_components),
            "product_existence": "UNKNOWN_UNQUERIED",
            "fallback": False,
        },
        "frozen_inputs": {
            "plan_receipt_sha256": PLAN_RECEIPT_SHA256,
            "mapping_sha256": plan.MAPPING_SHA256,
            "opaque_bundle_sha256": scorer.BUNDLE_CANONICAL_SHA256,
            "scorer_seal_sha256": SCORER_SEAL_SHA256,
            "scorer_source_sha256": SCORER_SOURCE_SHA256,
            "qualified_header_transform_sha256": sha256(
                strict_json(transform).encode("ascii")
            ).hexdigest(),
            "opaque_hypotheses": len(bundle["opaque_ids"]),
        },
        "grid": {
            "time_system": "GPS",
            "raw_start": plan.RAW_START_GPS,
            "heldout_start": plan.HELDOUT_START_GPS,
            "raw_stop": plan.RAW_STOP_GPS,
            "raw_epochs": plan.RAW_EPOCHS,
            "prefix_indices_inclusive": [0, plan.PREFIX_EPOCHS - 1],
            "heldout_indices_inclusive": [plan.PREFIX_EPOCHS, plan.RAW_EPOCHS - 1],
            "step_s": plan.STEP_S,
        },
        "measurement_packager": {
            "satellites": list(SATELLITES),
            "core_phase": list(CORE_PHASE),
            "same_path_code_witness": list(SAME_PATH_CODE),
            "output_to_scorer": "ONE_FINITE_UNLABELLED_COORDINATE_ARRAY",
            "may_select_model_or_score": False,
        },
        "admission": {
            "event_time_limit_s": EVENT_TIME_LIMIT_S,
            "geometry_free_second_difference_limit_m": (
                GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M
            ),
            "code_phase_witness_per_satellite_peak_to_peak_limit_m": (
                CODE_PHASE_PER_SATELLITE_PTP_LIMIT_M
            ),
            "complete_139_epoch_window_required": True,
        },
        "receipt_order": [
            "ONE_SHOT_AUTHORITY_MARKER",
            "COMPLETE_ARTIFACT_HASH",
            "MEASUREMENT_ADMISSION",
            "OPAQUE_SCORE_RECEIPT",
            "OPAQUE_SCORE_RECEIPT_HASH",
            "MAPPING_REVEAL",
            "FINAL_OUTCOME",
        ],
        "transport": {
            "maximum_attempts_before_complete_hash": MAX_TRANSPORT_ATTEMPTS,
            "retry_reasons": ["TIMEOUT", "TRANSPORT_INTERRUPTION"],
            "retry_after_complete_hash_or_decode": False,
            "maximum_compressed_bytes": MAX_COMPRESSED_BYTES,
        },
        "persistence": {
            "compressed_rinex": 0,
            "decoded_rinex": 0,
            "observation_values": 0,
            "opaque_score_and_aggregate_receipts_only": True,
        },
        "access_at_freeze": {
            "network_requests": 0,
            "product_locators_queried": 0,
            "primary_headers": 0,
            "primary_payload_bytes": 0,
            "primary_values": 0,
            "measurement_scores": 0,
        },
        "live_execution_authorized": False,
        "new_gate": False,
        "generic_framework": False,
    }
    strict_json(result)
    return result


def manifest_sha256(root: Path) -> str:
    return sha256(strict_json(executor_manifest(root)).encode("ascii")).hexdigest()


def build_executor_seal(root: Path) -> dict[str, object]:
    root = Path(root)
    result = {
        "schema": "gnss-blind-orbit-assignment-executor-seal-v1",
        "state": "BLIND_ORBIT_PRIMARY_EXECUTOR_FROZEN_UNOPENED",
        "source_commit": _git_commit(),
        "source_sha256": source_sha256(),
        "manifest_sha256": manifest_sha256(root),
        "dependencies": dependency_versions(),
        "frozen_inputs": executor_manifest(root)["frozen_inputs"],
        "authority": {
            "live_execution_authorized_by_seal": False,
            "separate_one_use_authority_required": True,
        },
        "access_at_seal": executor_manifest(root)["access_at_freeze"],
        "stop": "STOP_BEFORE_PRIMARY_ACCESS_FOR_REVIEW",
    }
    strict_json(result)
    return result


def validate_executor_seal(
    root: Path, seal_path: Path, expected_sha256: str
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    if len(expected_sha256) != 64 or canonical_sha256(seal_path) != expected_sha256:
        raise BlindOrbitExecutorError("EXECUTOR_SEAL_SHA256_CHANGED")
    seal = _read_strict_object(seal_path)
    if seal.get("state") != "BLIND_ORBIT_PRIMARY_EXECUTOR_FROZEN_UNOPENED":
        raise BlindOrbitExecutorError("EXECUTOR_SEAL_STATE_CHANGED")
    if seal.get("source_sha256") != source_sha256():
        raise BlindOrbitExecutorError("EXECUTOR_SOURCE_CHANGED")
    if seal.get("manifest_sha256") != manifest_sha256(root):
        raise BlindOrbitExecutorError("EXECUTOR_MANIFEST_CHANGED")
    if seal.get("dependencies") != dependency_versions():
        raise BlindOrbitExecutorError("EXECUTOR_DEPENDENCIES_CHANGED")
    authority = seal.get("authority")
    if not isinstance(authority, Mapping) or (
        authority.get("live_execution_authorized_by_seal") is not False
    ):
        raise BlindOrbitExecutorError("EXECUTOR_SEAL_GRANTED_LIVE_AUTHORITY")
    access = seal.get("access_at_seal")
    if not isinstance(access, Mapping) or any(access.values()):
        raise BlindOrbitExecutorError("EXECUTOR_SEAL_USED_PRIMARY")
    bundle, transform = validate_frozen_inputs(root)
    expected_transform_hash = sha256(strict_json(transform).encode("ascii")).hexdigest()
    if (
        seal.get("frozen_inputs", {}).get("qualified_header_transform_sha256")
        != expected_transform_hash
    ):
        raise BlindOrbitExecutorError("QUALIFIED_HEADER_TRANSFORM_CHANGED")
    return seal, bundle, transform


def _requests_module() -> Any:
    try:
        import requests
    except Exception as exc:  # pragma: no cover - dependency description path
        raise PrimaryDescriptionError("REQUESTS_UNAVAILABLE") from exc
    return requests


def _bounded_content(response: Any, maximum: int, label: str) -> bytes:
    try:
        data = response.content
    except Exception as exc:
        raise TransportInterruption(f"{label}_READ_FAILED") from exc
    if len(data) > maximum:
        raise PrimaryDescriptionError(f"{label}_SIZE_LIMIT")
    return data


def _raise_transport_status(response: Any, label: str) -> None:
    try:
        response.raise_for_status()
    except Exception as exc:
        raise TransportInterruption(f"{label}_HTTP_FAILURE") from exc


def _new_gssc_session() -> Any:
    requests = _requests_module()
    try:
        session = requests.Session()
        response = session.post(
            GSSC_WEB_ROOT + "loginok.html",
            data={
                "username": "anonymous",
                "password": "",
                "username_val": "anonymous",
                "password_val": "",
            },
            headers={"User-Agent": "Satellite-RF-Observatory/blind-orbit-primary"},
            timeout=HTTP_TIMEOUT_S,
        )
        _raise_transport_status(response, "GSSC_LOGIN")
        _bounded_content(response, 100_000, "GSSC_LOGIN_RESPONSE")
        return session
    except (PrimaryDescriptionError, TransportInterruption):
        raise
    except Exception as exc:
        raise TransportInterruption("GSSC_LOGIN_TRANSPORT_INTERRUPTION") from exc


def _product_metadata(directory_xml: bytes) -> dict[str, object]:
    try:
        root = ElementTree.fromstring(directory_xml)
    except ElementTree.ParseError as exc:
        raise PrimaryDescriptionError("GSSC_DIRECTORY_XML_INVALID") from exc
    expected_directory = "/" + "/".join(PRIMARY.directory_components)
    nowdir = root.findtext("nowdir", default="")
    if nowdir != expected_directory:
        raise PrimaryDescriptionError(f"GSSC_DIRECTORY_CHANGED:{nowdir}")
    matches = [
        row
        for row in root.findall("./dirdata/rowdata")
        if row.findtext("name", default="") == PRIMARY.name
    ]
    if len(matches) != 1:
        raise PrimaryDescriptionError(f"GSSC_PRODUCT_MATCH_COUNT:{len(matches)}")
    row = matches[0]
    if row.findtext("dir", default="") != "0":
        raise PrimaryDescriptionError("GSSC_PRODUCT_IS_NOT_FILE")
    try:
        size = int(row.findtext("size", default="-1"))
    except ValueError as exc:
        raise PrimaryDescriptionError("GSSC_PRODUCT_SIZE_INVALID") from exc
    if not 0 < size <= MAX_COMPRESSED_BYTES:
        raise PrimaryDescriptionError("GSSC_PRODUCT_SIZE_OUT_OF_BOUND")
    return {
        "directory": nowdir,
        "name": PRIMARY.name,
        "bytes": size,
        "modified": row.findtext("date", default=""),
        "md5": row.findtext("md5", default="").lower(),
    }


def _navigate_gssc(session: Any) -> dict[str, object]:
    try:
        for index, component in enumerate(PRIMARY.directory_components):
            requested = f"/{component}" if index == 0 else component
            response = session.post(
                GSSC_WEB_ROOT + "chdir.html",
                data={"dir": requested},
                headers={"User-Agent": "Satellite-RF-Observatory/blind-orbit-primary"},
                timeout=HTTP_TIMEOUT_S,
            )
            _raise_transport_status(response, "GSSC_CHDIR")
            result = _bounded_content(response, 10_000, "GSSC_CHDIR_RESPONSE")
            if result.strip() != b"Operation successful!":
                raise PrimaryDescriptionError(f"GSSC_CHDIR_FAILED:{component}")
        response = session.get(
            GSSC_WEB_ROOT + "dir.html",
            headers={"User-Agent": "Satellite-RF-Observatory/blind-orbit-primary"},
            timeout=HTTP_TIMEOUT_S,
        )
        _raise_transport_status(response, "GSSC_DIRECTORY")
        return _product_metadata(
            _bounded_content(response, MAX_DIRECTORY_BYTES, "GSSC_DIRECTORY_RESPONSE")
        )
    except (PrimaryDescriptionError, TransportInterruption):
        raise
    except Exception as exc:
        raise TransportInterruption("GSSC_DIRECTORY_TRANSPORT_INTERRUPTION") from exc


def _download_gssc(session: Any, directory: Mapping[str, object]) -> bytearray:
    payload = bytearray()
    try:
        response = session.get(
            GSSC_WEB_ROOT + "?download&filename=" + PRIMARY.name,
            headers={"User-Agent": "Satellite-RF-Observatory/blind-orbit-primary"},
            timeout=HTTP_TIMEOUT_S,
            stream=True,
        )
        _raise_transport_status(response, "GSSC_DOWNLOAD")
        for block in response.iter_content(chunk_size=1024 * 1024):
            if block:
                payload.extend(block)
            if len(payload) > MAX_COMPRESSED_BYTES:
                payload[:] = b"\x00" * len(payload)
                raise PrimaryDescriptionError("PRIMARY_COMPRESSED_SIZE_LIMIT")
    except (PrimaryDescriptionError, TransportInterruption):
        raise
    except Exception as exc:
        raise TransportInterruption("GSSC_DOWNLOAD_TRANSPORT_INTERRUPTION") from exc
    if len(payload) != int(directory["bytes"]):
        payload[:] = b"\x00" * len(payload)
        raise TransportInterruption("GSSC_COMPLETE_SIZE_MISMATCH")
    if payload[:2] != b"\x1f\x8b":
        payload[:] = b"\x00" * len(payload)
        raise TransportInterruption("GSSC_RESPONSE_NOT_GZIP")
    actual_md5 = md5(payload, usedforsecurity=False).hexdigest()
    directory_md5 = str(directory["md5"])
    if len(directory_md5) == 32 and directory_md5 != actual_md5:
        payload[:] = b"\x00" * len(payload)
        raise TransportInterruption("GSSC_DIRECTORY_MD5_MISMATCH")
    return payload


def materialize_gssc() -> tuple[bytearray, dict[str, object]]:
    failures: list[str] = []
    for attempt in range(1, MAX_TRANSPORT_ATTEMPTS + 1):
        session: Any | None = None
        payload = bytearray()
        try:
            session = _new_gssc_session()
            directory = _navigate_gssc(session)
            payload = _download_gssc(session, directory)
            return payload, {
                "station": PRIMARY.station,
                "product": PRIMARY.name,
                "transport": "GSSC_DOCUMENTED_ANONYMOUS_WEB_SESSION",
                "attempts": attempt,
                "complete_file_bytes": len(payload),
                "complete_file_sha256": sha256(payload).hexdigest(),
                "complete_file_md5": md5(payload, usedforsecurity=False).hexdigest(),
                "gssc_directory_bytes": directory["bytes"],
                "gssc_directory_md5": directory["md5"],
                "gssc_directory_modified": directory["modified"],
                "hash_before_decompression_header_or_record_decode": True,
            }
        except PrimaryDescriptionError:
            payload[:] = b"\x00" * len(payload)
            raise
        except (TransportInterruption, TimeoutError, OSError) as exc:
            payload[:] = b"\x00" * len(payload)
            failures.append(f"{type(exc).__name__}:{exc}")
        finally:
            if session is not None:
                try:
                    session.close()
                except Exception:
                    pass
    receipt = {
        "station": PRIMARY.station,
        "product": PRIMARY.name,
        "attempts": MAX_TRANSPORT_ATTEMPTS,
        "complete_file_bytes": None,
        "complete_file_sha256": None,
        "failures": failures,
        "retry_after_hash_or_decode": False,
    }
    raise PrimaryMaterializationError(
        "PRIMARY_ARTIFACT_MATERIALIZATION_FAILED", receipt
    )


def decompress_in_memory(payload: bytearray) -> bytearray:
    try:
        decoded = hatanaka.decompress(bytes(payload), strict=True)
    except (hatanaka.HatanakaException, ValueError) as exc:
        raise PrimaryMeasurementInvalid("HATANAKA_DECOMPRESSION_FAILED") from exc
    except Exception as exc:
        raise PrimaryDescriptionError("HATANAKA_DECODER_SOFTWARE_FAILURE") from exc
    if not isinstance(decoded, bytes):
        raise PrimaryDescriptionError("HATANAKA_DECODER_OUTPUT_TYPE_CHANGED")
    return bytearray(decoded)


def validate_materialized_artifact(
    payload: bytearray, artifact: Mapping[str, object]
) -> None:
    """Recompute the complete-file binding before any decode can occur."""

    if not isinstance(payload, bytearray):
        raise PrimaryDescriptionError("PRIMARY_BUFFER_NOT_ERASABLE")
    if artifact.get("station") != PRIMARY.station:
        raise PrimaryDescriptionError("PRIMARY_STATION_RECEIPT_CHANGED")
    if artifact.get("product") != PRIMARY.name:
        raise PrimaryDescriptionError("PRIMARY_PRODUCT_RECEIPT_CHANGED")
    try:
        attempts = int(artifact["attempts"])
        declared_bytes = int(artifact["complete_file_bytes"])
    except (KeyError, TypeError, ValueError) as exc:
        raise PrimaryDescriptionError("PRIMARY_ARTIFACT_RECEIPT_INVALID") from exc
    if not 1 <= attempts <= MAX_TRANSPORT_ATTEMPTS:
        raise PrimaryDescriptionError("PRIMARY_TRANSPORT_ATTEMPTS_INVALID")
    if declared_bytes != len(payload):
        raise PrimaryDescriptionError("PRIMARY_COMPLETE_BYTE_COUNT_CHANGED")
    actual_sha256 = sha256(payload).hexdigest()
    if artifact.get("complete_file_sha256") != actual_sha256:
        raise PrimaryDescriptionError("PRIMARY_COMPLETE_SHA256_CHANGED")


def _validate_header(
    parsed: Mapping[str, object], expected: Mapping[str, object]
) -> dict[str, object]:
    if not 3.0 <= float(parsed["rinex_version"]) < 5.0:
        raise PrimaryMeasurementInvalid("RINEX_VERSION_NOT_EXPLICIT")
    if _normalize(parsed["marker_name"]) != _normalize(expected["marker_name"]):
        raise PrimaryMeasurementInvalid("MARKER_IDENTITY_MISMATCH")
    if float(parsed["interval_s"]) != plan.STEP_S:
        raise PrimaryMeasurementInvalid("INTERVAL_CHANGED")
    first_info = parsed["time_of_first_observation"]
    last_info = parsed["time_of_last_observation"]
    if first_info["time_system"] != "GPS" or last_info["time_system"] != "GPS":
        raise PrimaryMeasurementInvalid("OBSERVATION_TIME_SYSTEM_NOT_GPS")
    first = headers.parse_utc(first_info["utc_like_epoch"])
    last = headers.parse_utc(last_info["utc_like_epoch"])
    epochs = expected_raw_gps_epochs()
    if first > epochs[0] or last < epochs[-1]:
        raise PrimaryMeasurementInvalid("FROZEN_WINDOW_NOT_COVERED")
    for section in ("receiver", "antenna"):
        actual_section = parsed[section]
        expected_section = expected[section]
        for key in ("serial", "type", "version_or_radome"):
            if _normalize(actual_section.get(key, "")) != _normalize(
                expected_section.get(key, "")
            ):
                raise PrimaryMeasurementInvalid(
                    f"{section.upper()}_{key.upper()}_CHANGED"
                )
    gps_types = tuple(parsed["observable_types"].get("G", ()))
    missing = sorted(set(CORE_PHASE + SAME_PATH_CODE) - set(gps_types))
    if missing:
        raise PrimaryMeasurementInvalid(
            f"REQUIRED_SIGNAL_FAMILY_NOT_DECLARED:{','.join(missing)}"
        )
    if list(parsed.get("scale_factor_records", ())) != expected["scale_factor_records"]:
        raise PrimaryMeasurementInvalid("UNSUPPORTED_SCALE_FACTOR_RECORD")
    phase_records = _required_phase_shift_records(parsed.get("phase_shift_records", ()))
    if phase_records != expected["required_phase_shift_records"]:
        raise PrimaryMeasurementInvalid("REQUIRED_PHASE_SHIFT_TRANSFORM_CHANGED")
    if list(parsed.get("applied_bias_records", ())) != expected["applied_bias_records"]:
        raise PrimaryMeasurementInvalid("APPLIED_BIAS_TRANSFORM_CHANGED")
    if (
        parsed["receiver_clock_offset_applied"]
        != expected["receiver_clock_offset_applied"]
    ):
        raise PrimaryMeasurementInvalid("RECEIVER_CLOCK_TRANSFORM_CHANGED")
    return {
        "station": PRIMARY.station,
        "rinex_version": float(parsed["rinex_version"]),
        "marker_name": parsed["marker_name"],
        "receiver": parsed["receiver"],
        "antenna": parsed["antenna"],
        "interval_s": float(parsed["interval_s"]),
        "time_of_first_observation": first_info,
        "time_of_last_observation": last_info,
        "receiver_clock_offset_applied": parsed["receiver_clock_offset_applied"],
        "required_phase_shift_records": phase_records,
        "gps_observables": list(gps_types),
        "full_frozen_window_covered": True,
    }


def _nearest_grid_index(epoch: datetime) -> tuple[int, float]:
    epochs = expected_raw_gps_epochs()
    index = min(
        range(len(epochs)),
        key=lambda candidate: (
            abs((epoch - epochs[candidate]).total_seconds()),
            candidate,
        ),
    )
    deviation = (epoch - epochs[index]).total_seconds()
    if abs(deviation) > EVENT_TIME_LIMIT_S:
        raise PrimaryNotDetectable("EVENT_TIME_BOUND_EXCEEDED")
    return index, float(deviation)


def _read_window_records(
    reader: rinex._LineReader,
    system_types: Mapping[str, Sequence[str]],
) -> tuple[dict[tuple[int, str], rinex._Record], dict[int, int], dict[int, float]]:
    epochs = expected_raw_gps_epochs()
    start = epochs[0] - timedelta(seconds=EVENT_TIME_LIMIT_S)
    stop = epochs[-1] + timedelta(seconds=EVENT_TIME_LIMIT_S)
    records: dict[tuple[int, str], rinex._Record] = {}
    flags: dict[int, int] = {}
    deviations: dict[int, float] = {}
    while True:
        line = reader.readline()
        if not line:
            break
        if not line.startswith(b">"):
            if line.strip():
                raise PrimaryMeasurementInvalid("RECORD_INVALID:NON_EPOCH_LINE")
            continue
        try:
            epoch, flag, satellite_count = rinex._parse_epoch(line)
        except rinex.QualificationFailure as exc:
            raise PrimaryMeasurementInvalid(str(exc)) from exc
        in_window = start <= epoch <= stop
        grid_index: int | None = None
        if in_window:
            grid_index, deviation = _nearest_grid_index(epoch)
            if grid_index in flags:
                raise PrimaryMeasurementInvalid("RECORD_INVALID:DUPLICATE_GRID_EPOCH")
            flags[grid_index] = flag
            deviations[grid_index] = deviation
        if flag in {2, 3, 4, 5}:
            for _ in range(satellite_count):
                if not reader.readline():
                    raise PrimaryMeasurementInvalid(
                        "RECORD_INVALID:TRUNCATED_SPECIAL_EVENT"
                    )
            continue
        if flag == 6:
            for _ in range(satellite_count):
                try:
                    rinex._read_record(reader, system_types)
                except rinex.QualificationFailure as exc:
                    raise PrimaryMeasurementInvalid(str(exc)) from exc
            continue
        if flag not in {0, 1}:
            raise PrimaryMeasurementInvalid(f"RECORD_INVALID:EPOCH_FLAG_{flag}")
        for _ in range(satellite_count):
            try:
                satellite, record = rinex._read_record(reader, system_types)
            except rinex.QualificationFailure as exc:
                raise PrimaryMeasurementInvalid(str(exc)) from exc
            if grid_index is None or satellite not in SATELLITES:
                continue
            key = grid_index, satellite
            if key in records:
                raise PrimaryMeasurementInvalid(
                    "RECORD_INVALID:DUPLICATE_SATELLITE_RECORD"
                )
            records[key] = record
    return records, flags, deviations


def _parse_scalar(field: bytes, label: str) -> float:
    try:
        value = float(field[:14].strip().replace(b"D", b"E"))
    except ValueError as exc:
        raise PrimaryMeasurementInvalid(f"RECORD_INVALID:{label}_SCALAR") from exc
    if not np.isfinite(value):
        raise PrimaryMeasurementInvalid(f"RECORD_INVALID:NONFINITE_{label}")
    return value


def scan_decoded(
    decoded: bytearray, expected_transform: Mapping[str, object]
) -> StationMeasurement:
    reader = rinex._LineReader(decoded)
    try:
        header_lines = rinex._read_header(reader)
        parsed = headers.parse_header_lines(header_lines)
    except (rinex.QualificationFailure, headers.HeaderAdmissionError) as exc:
        raise PrimaryMeasurementInvalid(f"HEADER_INVALID:{exc}") from exc
    except Exception as exc:
        raise PrimaryDescriptionError(
            f"HEADER_DESCRIPTION_ERROR:{type(exc).__name__}:{exc}"
        ) from exc
    header = _validate_header(parsed, expected_transform)
    system_types = {
        system: tuple(values) for system, values in parsed["observable_types"].items()
    }
    gps_types = system_types["G"]
    indices = {
        observable: gps_types.index(observable)
        for observable in CORE_PHASE + SAME_PATH_CODE
    }
    records, flags, deviations = _read_window_records(reader, system_types)
    phase_cycles = np.full((plan.RAW_EPOCHS, 2, 2), np.nan, dtype=np.float64)
    code_m = np.full((plan.RAW_EPOCHS, 2, 2), np.nan, dtype=np.float64)
    event_time = np.full(plan.RAW_EPOCHS, np.nan, dtype=np.float64)
    counts = {"PRESENT": 0, "BLANK": 0, "TRAILING_FIELD_OMITTED": 0}
    for row, epoch in enumerate(expected_raw_gps_epochs()):
        if flags.get(row) != 0:
            raise PrimaryMeasurementInvalid(
                f"EPOCH_ABSENT_OR_FLAGGED:{epoch.isoformat()}:{flags.get(row)}"
            )
        event_time[row] = deviations[row]
        for satellite_index, satellite in enumerate(SATELLITES):
            record = records.get((row, satellite))
            if record is None:
                raise PrimaryMeasurementInvalid(
                    f"SATELLITE_RECORD_ABSENT:{epoch.isoformat()}:{satellite}"
                )
            for observable_index, observable in enumerate(CORE_PHASE):
                field_index = indices[observable]
                if field_index >= record.field_count:
                    counts["TRAILING_FIELD_OMITTED"] += 1
                    raise PrimaryMeasurementInvalid(
                        f"TRAILING_FIELD_OMITTED:{satellite}:{observable}"
                    )
                field = record.fields[field_index]
                if not field[:14].strip():
                    counts["BLANK"] += 1
                    raise PrimaryMeasurementInvalid(
                        f"FIELD_BLANK:{satellite}:{observable}"
                    )
                if rinex._parse_lli(field) != "ZERO_OR_BLANK":
                    raise PrimaryMeasurementInvalid(
                        f"NONZERO_OR_INVALID_LLI:{satellite}:{observable}"
                    )
                phase_cycles[row, satellite_index, observable_index] = _parse_scalar(
                    field, "PHASE"
                )
                counts["PRESENT"] += 1
            for observable_index, observable in enumerate(SAME_PATH_CODE):
                field_index = indices[observable]
                if field_index >= record.field_count:
                    counts["TRAILING_FIELD_OMITTED"] += 1
                    raise PrimaryMeasurementInvalid(
                        f"TRAILING_FIELD_OMITTED:{satellite}:{observable}"
                    )
                field = record.fields[field_index]
                if not field[:14].strip():
                    counts["BLANK"] += 1
                    raise PrimaryMeasurementInvalid(
                        f"FIELD_BLANK:{satellite}:{observable}"
                    )
                code_m[row, satellite_index, observable_index] = _parse_scalar(
                    field, "CODE"
                )
                counts["PRESENT"] += 1
    if not np.all(np.isfinite(phase_cycles)) or not np.all(np.isfinite(code_m)):
        raise PrimaryMeasurementInvalid("REQUIRED_MEASUREMENT_NONFINITE")
    return StationMeasurement(header, phase_cycles, code_m, event_time, counts)


def measurement_coordinate(
    scan: StationMeasurement,
) -> tuple[np.ndarray, dict[str, object]]:
    alpha, beta = inherited.ionosphere_free_coefficients()
    geometry_links = []
    witness_links = []
    phase_if = np.empty((plan.RAW_EPOCHS, 2), dtype=np.float64)
    code_if = np.empty((plan.RAW_EPOCHS, 2), dtype=np.float64)
    try:
        for satellite_index, satellite in enumerate(SATELLITES):
            geometry_free = (
                LAMBDA_L1_M * scan.phase_cycles[:, satellite_index, 0]
                - LAMBDA_L2_M * scan.phase_cycles[:, satellite_index, 1]
            )
            second = np.diff(geometry_free, n=2)
            maximum = float(np.max(np.abs(second)))
            violations = int(
                np.count_nonzero(
                    np.abs(second) > GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M
                )
            )
            geometry_links.append(
                {
                    "satellite": satellite,
                    "evaluated_second_differences": int(second.size),
                    "maximum_absolute_second_difference_m": maximum,
                    "violations": violations,
                }
            )
            geometry_free.fill(0.0)
            second.fill(0.0)
            if violations:
                raise PrimaryMeasurementInvalid(
                    f"GEOMETRY_FREE_PHASE_HEALTH_FAILED:{satellite}:{maximum}"
                )
            phase_if[:, satellite_index] = (
                alpha * LAMBDA_L1_M * scan.phase_cycles[:, satellite_index, 0]
                + beta * LAMBDA_L2_M * scan.phase_cycles[:, satellite_index, 1]
            )
            code_if[:, satellite_index] = (
                alpha * scan.code_m[:, satellite_index, 0]
                + beta * scan.code_m[:, satellite_index, 1]
            )
            witness = phase_if[:, satellite_index] - code_if[:, satellite_index]
            witness -= witness[0]
            peak_to_peak = float(np.ptp(witness))
            witness_links.append(
                {
                    "satellite": satellite,
                    "full_window_peak_to_peak_m": peak_to_peak,
                    "limit_m": CODE_PHASE_PER_SATELLITE_PTP_LIMIT_M,
                    "state": (
                        "SATISFIED"
                        if peak_to_peak <= CODE_PHASE_PER_SATELLITE_PTP_LIMIT_M
                        else "UNSATISFIED"
                    ),
                }
            )
            witness.fill(0.0)
        failed_witness = next(
            (row for row in witness_links if row["state"] == "UNSATISFIED"),
            None,
        )
        if failed_witness is not None:
            raise PrimaryNotDetectable(
                "SAME_PATH_CODE_PHASE_WITNESS_OVER_LIMIT:"
                f"{failed_witness['satellite']}"
            )
        coordinate = phase_if[:, 0] - phase_if[:, 1]
        coordinate -= coordinate[0]
        if coordinate.shape != (plan.RAW_EPOCHS,) or not np.all(
            np.isfinite(coordinate)
        ):
            coordinate.fill(0.0)
            raise PrimaryMeasurementInvalid("PRIMARY_COORDINATE_INVALID")
        admission = {
            "header": scan.header,
            "structural_counts": scan.structural_counts,
            "event_time": {
                "state": "SATISFIED",
                "maximum_absolute_deviation_s": float(
                    np.max(np.abs(scan.event_time_deviation_s))
                ),
                "limit_s": EVENT_TIME_LIMIT_S,
            },
            "core_phase_and_lli": "SATISFIED",
            "geometry_free_phase_health": {
                "state": "SATISFIED",
                "limit_m": GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M,
                "links": geometry_links,
            },
            "same_path_code_phase_witness": {
                "state": "SATISFIED",
                "links": witness_links,
            },
            "raw_epochs": plan.RAW_EPOCHS,
        }
        strict_json(admission)
        return coordinate, admission
    finally:
        phase_if.fill(0.0)
        code_if.fill(0.0)


def _write_pretty_json(path: Path, value: object) -> None:
    Path(path).write_text(
        strict_json(value, pretty=True) + "\n", encoding="ascii", newline="\n"
    )


def _write_pretty_json_exclusive(path: Path, value: object) -> None:
    with Path(path).open("x", encoding="ascii", newline="\n") as stream:
        stream.write(strict_json(value, pretty=True) + "\n")


def _write_canonical_json_exclusive(path: Path, value: object) -> None:
    with Path(path).open("xb") as stream:
        stream.write(strict_json(value).encode("ascii"))


def _persist_opaque_score(
    output: Path, receipt: Mapping[str, object]
) -> tuple[Path, str, Path]:
    score_path = output / OPAQUE_SCORE_NAME
    hash_path = output / OPAQUE_SCORE_HASH_NAME
    _write_canonical_json_exclusive(score_path, receipt)
    receipt_hash = canonical_sha256(score_path)
    if receipt_hash != scorer.score_receipt_sha256(receipt):
        raise BlindingInvalid("OPAQUE_SCORE_HASH_MISMATCH")
    _write_pretty_json_exclusive(
        hash_path,
        {
            "schema": "gnss-opaque-orbit-score-hash-receipt-v1",
            "state": "OPAQUE_SCORE_RECEIPT_HASH_PERSISTED_BEFORE_MAPPING_REVEAL",
            "score_receipt_filename": OPAQUE_SCORE_NAME,
            "score_receipt_sha256": receipt_hash,
            "mapping_revealed": False,
        },
    )
    return score_path, receipt_hash, hash_path


def reveal_mapping(
    root: Path,
    score_receipt: Mapping[str, object],
    score_path: Path,
    score_hash_path: Path,
    expected_score_sha256: str,
) -> dict[str, object]:
    if (
        not score_path.is_file()
        or canonical_sha256(score_path) != expected_score_sha256
    ):
        raise BlindingInvalid("OPAQUE_SCORE_NOT_IMMUTABLY_PERSISTED")
    hash_receipt = _read_strict_object(score_hash_path)
    if (
        hash_receipt.get("state")
        != "OPAQUE_SCORE_RECEIPT_HASH_PERSISTED_BEFORE_MAPPING_REVEAL"
        or hash_receipt.get("score_receipt_sha256") != expected_score_sha256
        or hash_receipt.get("mapping_revealed") is not False
    ):
        raise BlindingInvalid("OPAQUE_SCORE_HASH_RECEIPT_INVALID")
    mapping_path = _require_hash(root, plan.MAPPING_NAME, plan.MAPPING_SHA256)
    mapping = _read_strict_object(mapping_path)
    rows = mapping.get("mapping")
    if not isinstance(rows, list) or len(rows) != 6:
        raise BlindingInvalid("MAPPING_ROWS_INVALID")
    opaque_outcome = score_receipt.get("opaque_outcome")
    best_id = score_receipt.get("best_opaque_id")
    if opaque_outcome == "AMBIGUOUS":
        return {
            "outcome": "AMBIGUOUS",
            "best_opaque_id": best_id,
            "revealed_model": None,
            "revealed_model_class": None,
        }
    if opaque_outcome != "OPAQUE_HYPOTHESIS_PREFERRED" or not isinstance(best_id, str):
        raise BlindingInvalid("OPAQUE_SCORE_OUTCOME_INVALID")
    matches = [row for row in rows if row.get("opaque_id") == best_id]
    if len(matches) != 1:
        raise BlindingInvalid("OPAQUE_WINNER_MAPPING_INVALID")
    row = matches[0]
    model = str(row.get("model"))
    model_class = str(row.get("model_class"))
    if model_class == "NON_ORBITAL_NULL" and model == "PREFIX_AFFINE_ONLY":
        outcome = "FROZEN_AFFINE_NULL_PREFERRED"
    elif model_class == "ORBITAL_CANDIDATE" and model == "G22_RELATIVE_TO_G30":
        outcome = "BOUNDED_TRUE_ORBIT_PREFERRED"
    elif model_class == "ORBITAL_CANDIDATE" and model.endswith("_RELATIVE_TO_G30"):
        outcome = "BOUNDED_ALTERNATIVE_ORBIT_PREFERRED"
    else:
        raise BlindingInvalid("MAPPING_MODEL_CLASS_INVALID")
    return {
        "outcome": outcome,
        "best_opaque_id": best_id,
        "revealed_model": model,
        "revealed_model_class": model_class,
    }


def _failure_outcome(state: str, reason: str, artifact: object) -> dict[str, object]:
    descriptive = state in {
        "PRIMARY_ARTIFACT_MATERIALIZATION_FAILED",
        "PRIMARY_DESCRIPTION_ERROR",
        "BLINDING_INVALID",
    }
    return {
        "schema": "gnss-blind-orbit-assignment-primary-outcome-v1",
        "outcome": state,
        "physical_outcome": None if descriptive else state,
        "reason": reason,
        "artifact": artifact,
        "measurement_admission": "NOT_EVALUATED",
        "heldout_comparison": "NOT_EVALUATED",
        "identity_reveal_performed": False,
        "observation_values_persisted": 0,
    }


def run_once(
    output_directory: Path,
    authority_token: str,
    expected_seal_sha256: str,
    executor_seal_path: Path,
    *,
    materializer: Materializer = materialize_gssc,
) -> dict[str, object]:
    if authority_token != AUTHORITY_TOKEN:
        raise PermissionError("AMC_DOY226_BLIND_PRIMARY_AUTHORITY_REQUIRED")
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    paths = {
        output / name
        for name in (
            AUTHORITY_MARKER_NAME,
            OPAQUE_SCORE_NAME,
            OPAQUE_SCORE_HASH_NAME,
            OUTCOME_NAME,
        )
    }
    if any(path.exists() for path in paths):
        raise PermissionError("AMC_DOY226_BLIND_PRIMARY_AUTHORITY_ALREADY_CONSUMED")
    root = Path(__file__).resolve().parent
    seal, bundle, expected_transform = validate_executor_seal(
        root, executor_seal_path, expected_seal_sha256
    )
    marker = {
        "schema": "gnss-blind-orbit-primary-authority-consumed-v1",
        "state": "ONE_SHOT_AUTHORITY_CONSUMED_BEFORE_NETWORK",
        "executor_seal_sha256": expected_seal_sha256,
        "source_commit": seal["source_commit"],
        "network_requests_before_marker": 0,
        "product_locators_queried_before_marker": 0,
        "primary_headers_before_marker": 0,
        "primary_payload_bytes_before_marker": 0,
        "primary_values_before_marker": 0,
    }
    _write_pretty_json_exclusive(output / AUTHORITY_MARKER_NAME, marker)
    compressed: bytearray | None = None
    decoded: bytearray | None = None
    scan: StationMeasurement | None = None
    coordinate: np.ndarray | None = None
    artifact: dict[str, object] | None = None
    try:
        compressed, artifact = materializer()
        validate_materialized_artifact(compressed, artifact)
        decoded = decompress_in_memory(compressed)
        scan = scan_decoded(decoded, expected_transform)
        coordinate, admission = measurement_coordinate(scan)
        score_receipt = scorer.score(coordinate, bundle)
        score_path, score_hash, score_hash_path = _persist_opaque_score(
            output, score_receipt
        )
        reveal = reveal_mapping(
            root,
            score_receipt,
            score_path,
            score_hash_path,
            score_hash,
        )
        outcome = {
            "schema": "gnss-blind-orbit-assignment-primary-outcome-v1",
            "executor_version": EXECUTOR_VERSION,
            "outcome": reveal["outcome"],
            "executor_seal_sha256": expected_seal_sha256,
            "source_commit": seal["source_commit"],
            "source_sha256": seal["source_sha256"],
            "plan_receipt_sha256": PLAN_RECEIPT_SHA256,
            "opaque_bundle_sha256": scorer.BUNDLE_CANONICAL_SHA256,
            "scorer_seal_sha256": SCORER_SEAL_SHA256,
            "artifact": artifact,
            "measurement_admission": admission,
            "opaque_score": {
                "receipt_filename": OPAQUE_SCORE_NAME,
                "receipt_sha256": score_hash,
                "opaque_outcome": score_receipt["opaque_outcome"],
                "best_opaque_id": score_receipt["best_opaque_id"],
                "runner_up_opaque_id": score_receipt["runner_up_opaque_id"],
                "preference_margin_m": score_receipt["preference_margin_m"],
                "pairwise_guard_m": score_receipt["pairwise_guard_m"],
                "observed_coordinate_sha256": score_receipt[
                    "observed_coordinate_sha256"
                ],
                "observed_values_persisted": 0,
            },
            "identity_reveal": {
                "performed_after_opaque_score_receipt_hash": True,
                "mapping_sha256": plan.MAPPING_SHA256,
                **reveal,
            },
            "observation_access": {
                "products": 1,
                "headers": 1,
                "compressed_bytes_in_ram": len(compressed),
                "decoded_bytes_in_ram": len(decoded),
                "phase_scalars_parsed_in_ram": plan.RAW_EPOCHS * 2 * 2,
                "code_scalars_parsed_in_ram": plan.RAW_EPOCHS * 2 * 2,
                "observation_values_persisted": 0,
            },
            "persistence": {
                "compressed_rinex": 0,
                "decoded_rinex": 0,
                "observation_values": 0,
                "aggregate_receipts_only": True,
            },
            "retry": {
                "transport_attempts_before_hash": artifact["attempts"],
                "retry_after_complete_hash": False,
                "retry_after_decode": False,
                "alternate_product_station_date_window_threshold_or_null": False,
            },
            "claim_scope": (
                "BOUNDED_ORBIT_ASSIGNMENT_PREFERRED_WITHIN_FROZEN_CANDIDATE_SET"
                if reveal["outcome"] == "BOUNDED_TRUE_ORBIT_PREFERRED"
                else "NO_POSITIVE_G22_ORBIT_ASSIGNMENT_CLAIM"
            ),
        }
    except PrimaryMaterializationError as exc:
        outcome = _failure_outcome(
            "PRIMARY_ARTIFACT_MATERIALIZATION_FAILED", str(exc), exc.receipt
        )
    except PrimaryNotDetectable as exc:
        outcome = _failure_outcome("NOT_DETECTABLE", str(exc), artifact)
    except PrimaryMeasurementInvalid as exc:
        outcome = _failure_outcome("MEASUREMENT_INVALID", str(exc), artifact)
    except BlindingInvalid as exc:
        outcome = _failure_outcome("BLINDING_INVALID", str(exc), artifact)
    except Exception as exc:
        outcome = _failure_outcome(
            "PRIMARY_DESCRIPTION_ERROR", f"{type(exc).__name__}:{exc}", artifact
        )
    finally:
        if coordinate is not None:
            coordinate.fill(0.0)
        if scan is not None:
            scan.erase()
        for payload in (decoded, compressed):
            if payload is not None:
                payload[:] = b"\x00" * len(payload)
        gc.collect()
    strict_json(outcome)
    _write_pretty_json(output / OUTCOME_NAME, outcome)
    return outcome


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-executor-seal", action="store_true")
    parser.add_argument("--execute-live", action="store_true")
    parser.add_argument("--authority", default="")
    parser.add_argument("--executor-seal-sha256", default="")
    parser.add_argument("--executor-seal", type=Path)
    parser.add_argument(
        "--output-directory", type=Path, default=Path(__file__).resolve().parent
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    if args.write_executor_seal:
        output = args.output_directory / EXECUTOR_SEAL_NAME
        if output.exists():
            raise SystemExit("EXECUTOR_SEAL_ALREADY_EXISTS")
        _write_pretty_json(output, build_executor_seal(root))
        print(
            strict_json(
                {
                    "outcome": "BLIND_ORBIT_PRIMARY_EXECUTOR_FROZEN_UNOPENED",
                    "primary_observation_access": 0,
                    "live_execution_authorized": False,
                }
            )
        )
        return
    if not args.execute_live or args.executor_seal is None:
        raise SystemExit("OFFLINE_EXECUTOR_FREEZE_OR_LIVE_AUTHORITY_REQUIRED")
    result = run_once(
        args.output_directory,
        args.authority,
        args.executor_seal_sha256,
        args.executor_seal,
    )
    print(
        strict_json(
            {
                "outcome": result.get("outcome"),
                "outcome_written": True,
            }
        )
    )


if __name__ == "__main__":
    main()
