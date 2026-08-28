"""Sealed one-shot executor for the prospective PIE DOY223 observation.

This experiment-specific module binds the already frozen plan and prediction
curves.  Importing it, building its manifest, and writing its executor seal
perform no network request.  A later execution requires a separately reviewed
seal hash and one-use authority token; observation arrays remain in RAM and
are erased after an aggregate outcome is written.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta
import gc
from hashlib import md5, sha256
from importlib import metadata
import json
from math import sqrt
from pathlib import Path
import platform
import subprocess
from typing import Any, Callable, Final, Mapping, Sequence
from xml.etree import ElementTree

import hatanaka
import numpy as np

from experiments.orbital_discriminability import (
    gnss_observation_header as headers,
)
from experiments.orbital_discriminability import (
    gnss_double_difference_envelope as inherited,
)
from experiments.orbital_discriminability import (
    gnss_phase_short_window_qualification as rinex,
)
from experiments.orbital_discriminability import (
    gnss_pie_observer_predictions as prediction,
)
from experiments.orbital_discriminability import (
    gnss_pie_observer_primary_plan as plan,
)
from experiments.orbital_discriminability import (
    gnss_pie_observer_qualification as qualified,
)


EXECUTOR_VERSION: Final = "pie-g22-g30-doy223-one-shot-executor-v1"
EXECUTOR_SEAL_NAME: Final = "PIE_OBSERVER_PRIMARY_EXECUTOR_SEAL.json"
OUTCOME_NAME: Final = "PIE_OBSERVER_PRIMARY_OUTCOME.json"
AUTHORITY_MARKER_NAME: Final = "PIE_OBSERVER_PRIMARY_AUTHORITY_CONSUMED.json"
AUTHORITY_TOKEN: Final = "AUTHORIZE_PIE_DOY223_PRIMARY_ONCE"

PREDICTIONS_SHA256: Final = (
    "a86a360fcbf9e1aa05e112bae1e2d1158b729f6e2fe9b4418a89883c72aacbc9"
)
PREDICTION_SEAL_SHA256: Final = (
    "446b65682cf9bfe7eac5d4fe63a1c709dc0ebaf9f75a681214f925b0f111e4e9"
)

SATELLITES: Final = (plan.TARGET, plan.REFERENCE)
CORE_PHASE: Final = ("L1C", "L2W")
SAME_PATH_CODE: Final = ("C1C", "C2W")
HYPOTHESES: Final = prediction.HYPOTHESES
PREFERRED_OUTCOMES: Final = {
    "ORBITAL_G22": "PIE_HELD_OUT_ORBITAL_MODEL_PREFERRED",
    "FROZEN_AFFINE_NULL": "FROZEN_AFFINE_NULL_PREFERRED",
    "WRONG_ORBIT_G01": "WRONG_ORBIT_G01_PREFERRED",
    "WRONG_ORBIT_G14": "WRONG_ORBIT_G14_PREFERRED",
    "WRONG_ORBIT_G17": "WRONG_ORBIT_G17_PREFERRED",
}

PRIMARY_DIRECTORY_COMPONENTS: Final = ("gnss", "data", "daily", "2026", "223")
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


class PieExecutorError(ValueError):
    """A frozen executor, plan, prediction, or state invariant changed."""


class PrimaryMeasurementInvalid(ValueError):
    """The observation failed a frozen measurement-validity clause."""


class PrimaryNotDetectable(ValueError):
    """The measurement is valid but cannot support the frozen comparison."""


class PrimaryDescriptionError(RuntimeError):
    """Software or descriptive state failed without a physical decision."""


class TransportInterruption(RuntimeError):
    """One pre-hash transport attempt did not yield a complete artifact."""


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
    payload = Path(path).read_bytes().replace(bytes((13, 10)), bytes((10,)))
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


def _read_strict_json(path: Path) -> dict[str, object]:
    value = json.loads(
        Path(path).read_text(encoding="utf-8"),
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )
    if not isinstance(value, dict):
        raise PieExecutorError(f"FROZEN_ARTIFACT_NOT_OBJECT:{Path(path).name}")
    return value


def _require_hash(root: Path, name: str, digest: str) -> Path:
    path = Path(root) / name
    if not path.is_file() or canonical_sha256(path) != digest:
        raise PieExecutorError(f"FROZEN_ARTIFACT_CHANGED:{name}")
    return path


def expected_raw_gps_epochs() -> tuple[datetime, ...]:
    return prediction.expected_raw_gps_epochs()


def _required_phase_shift_records(rows: Sequence[object]) -> list[str]:
    result = []
    for value in rows:
        normalized = " ".join(str(value).split())
        if normalized.startswith("G L1C") or normalized.startswith("G L2W"):
            result.append(normalized)
    return result


def _expected_header_transform(root: Path) -> dict[str, object]:
    summary_path = _require_hash(
        root,
        plan.QUALIFICATION_SUMMARY_NAME,
        plan.QUALIFICATION_SUMMARY_SHA256,
    )
    summary = _read_strict_json(summary_path)
    header = summary.get("header")
    if not isinstance(header, Mapping):
        raise PieExecutorError("QUALIFIED_HEADER_MISSING")
    if summary.get("full_joint_window") is not True:
        raise PieExecutorError("QUALIFIED_WINDOW_CHANGED")
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
        raise PieExecutorError("QUALIFIED_PHASE_TRANSFORM_CHANGED")
    if result["applied_bias_records"] or result["receiver_clock_offset_applied"] != 0:
        raise PieExecutorError("QUALIFIED_RECEIVER_TRANSFORM_CHANGED")
    strict_json(result)
    return result


def validate_frozen_inputs(
    root: Path,
) -> tuple[dict[str, np.ndarray], dict[str, object]]:
    root = Path(root)
    prediction.verify_plan(root)
    prediction_path = _require_hash(
        root, prediction.PREDICTIONS_NAME, PREDICTIONS_SHA256
    )
    seal_path = _require_hash(root, prediction.SEAL_NAME, PREDICTION_SEAL_SHA256)
    value = _read_strict_json(prediction_path)
    curves = prediction.validate_predictions(value, root)
    seal = _read_strict_json(seal_path)
    if seal.get("state") != "PIE_OBSERVER_PRIMARY_PREDICTION_FROZEN":
        raise PieExecutorError("PREDICTION_SEAL_STATE_CHANGED")
    if seal.get("predictions", {}).get("canonical_sha256") != PREDICTIONS_SHA256:
        raise PieExecutorError("PREDICTION_SEAL_BINDING_CHANGED")
    authority = seal.get("authority", {})
    if not isinstance(authority, Mapping) or any(
        authority.get(field) is not False
        for field in (
            "primary_access_authorized_by_seal",
            "executor_authorized_by_seal",
        )
    ):
        raise PieExecutorError("PREDICTION_SEAL_GRANTED_ACCESS")
    primary = seal.get("primary", {})
    if (
        not isinstance(primary, Mapping)
        or primary.get("station") != PRIMARY.station
        or primary.get("logical_product") != PRIMARY.name
        or any(
            int(primary.get(field, -1)) != 0
            for field in ("headers_opened", "payload_bytes", "observation_values")
        )
    ):
        raise PieExecutorError("PRIMARY_BOUNDARY_CHANGED")
    return curves, _expected_header_transform(root)


def executor_manifest(root: Path) -> dict[str, object]:
    curves, transform = validate_frozen_inputs(root)
    try:
        result = {
            "schema": "pie-observer-primary-executor-manifest-v1",
            "executor_version": EXECUTOR_VERSION,
            "physical_question": plan.plan(root)["physical_question"],
            "new_information": (
                "ONE_SEPARATELY_AUTHORIZED_EXECUTION_CAN_TEST_WHETHER_THE_"
                "FROZEN_PIE_HELDOUT_COORDINATE_PREFERS_THE_ORBITAL_MODEL"
            ),
            "product": {
                "station": PRIMARY.station,
                "logical_product": PRIMARY.name,
                "transport": "GSSC_DOCUMENTED_ANONYMOUS_WEB_SESSION_ONLY",
                "directory": "/" + "/".join(PRIMARY.directory_components),
                "fallback": False,
                "complete_hash_unknown_until_authorized_materialization": True,
            },
            "frozen_inputs": {
                "plan_manifest_sha256": prediction.FROZEN_PLAN_MANIFEST_SHA256,
                "prediction_sha256": PREDICTIONS_SHA256,
                "prediction_seal_sha256": PREDICTION_SEAL_SHA256,
                "curve_set_sha256": str(
                    _read_strict_json(Path(root) / prediction.PREDICTIONS_NAME)[
                        "curve_set_sha256"
                    ]
                ),
                "qualified_header_transform": transform,
            },
            "grid": prediction.compiler_manifest(root)["grid"],
            "signals": {
                "satellites": list(SATELLITES),
                "core_phase": list(CORE_PHASE),
                "same_path_code_witness": list(SAME_PATH_CODE),
                "optional_signal_strength_persisted": False,
            },
            "measurement_admission": plan.plan(root)["admission"],
            "scoring": {
                **plan.plan(root)["scoring"],
                "heldout_raw_indices_inclusive": [79, 138],
                "pairwise_decision_guard_m": plan.REVISED_PAIRWISE_GUARD_M,
                "fit_or_projection": "NONE",
            },
            "transport": {
                "maximum_attempts_before_complete_hash": MAX_TRANSPORT_ATTEMPTS,
                "retry_reasons": ["TIMEOUT", "TRANSPORT_INTERRUPTION"],
                "hash_before_decompression_header_or_record_decode": True,
                "retry_after_complete_hash": False,
                "retry_after_decode": False,
                "maximum_compressed_bytes": MAX_COMPRESSED_BYTES,
            },
            "one_shot": {
                "authority_marker_written_before_network": True,
                "existing_marker_or_outcome_refuses": True,
                "endpoint_date_feature_threshold_substitution": False,
            },
            "persistence": {
                "compressed_rinex": 0,
                "decoded_rinex": 0,
                "phase_code_or_signal_values": 0,
                "aggregate_receipt_only": True,
            },
            "access_at_freeze": {
                "network_requests": 0,
                "primary_headers": 0,
                "primary_payload_bytes": 0,
                "primary_values": 0,
                "orbital_scores": 0,
            },
            "live_execution_authorized": False,
            "new_gate": False,
            "generic_framework": False,
        }
        strict_json(result)
        return result
    finally:
        for curve in curves.values():
            curve.fill(0.0)


def manifest_sha256(root: Path) -> str:
    return sha256(strict_json(executor_manifest(root)).encode("ascii")).hexdigest()


def build_executor_seal(root: Path) -> dict[str, object]:
    root = Path(root)
    curves, transform = validate_frozen_inputs(root)
    try:
        result = {
            "schema": "pie-observer-primary-executor-seal-v1",
            "state": "PIE_OBSERVER_PRIMARY_EXECUTOR_FROZEN_UNOPENED",
            "source_commit": _git_commit(),
            "source_sha256": source_sha256(),
            "manifest_sha256": manifest_sha256(root),
            "dependencies": dependency_versions(),
            "plan_manifest_sha256": prediction.FROZEN_PLAN_MANIFEST_SHA256,
            "prediction_sha256": PREDICTIONS_SHA256,
            "prediction_seal_sha256": PREDICTION_SEAL_SHA256,
            "qualified_header_transform_sha256": sha256(
                strict_json(transform).encode("ascii")
            ).hexdigest(),
            "product": executor_manifest(root)["product"],
            "authority": {
                "live_execution_authorized_by_seal": False,
                "separate_review_and_one_use_token_required": True,
            },
            "access_at_seal": executor_manifest(root)["access_at_freeze"],
            "stop": "STOP_BEFORE_PRIMARY_ACCESS_FOR_SEPARATE_REVIEW",
        }
        strict_json(result)
        return result
    finally:
        for curve in curves.values():
            curve.fill(0.0)


def validate_executor_seal(
    root: Path, seal_path: Path, expected_sha256: str
) -> tuple[dict[str, object], dict[str, np.ndarray], dict[str, object]]:
    if len(expected_sha256) != 64 or canonical_sha256(seal_path) != expected_sha256:
        raise PieExecutorError("EXECUTOR_SEAL_SHA256_CHANGED")
    seal = _read_strict_json(seal_path)
    if seal.get("state") != "PIE_OBSERVER_PRIMARY_EXECUTOR_FROZEN_UNOPENED":
        raise PieExecutorError("EXECUTOR_SEAL_STATE_CHANGED")
    if seal.get("source_sha256") != source_sha256():
        raise PieExecutorError("EXECUTOR_SOURCE_CHANGED")
    if seal.get("manifest_sha256") != manifest_sha256(root):
        raise PieExecutorError("EXECUTOR_MANIFEST_CHANGED")
    if seal.get("dependencies") != dependency_versions():
        raise PieExecutorError("EXECUTOR_DEPENDENCIES_CHANGED")
    if seal.get("authority", {}).get("live_execution_authorized_by_seal") is not False:
        raise PieExecutorError("EXECUTOR_SEAL_GRANTED_LIVE_AUTHORITY")
    if any(seal.get("access_at_seal", {}).values()):
        raise PieExecutorError("EXECUTOR_SEAL_USED_PRIMARY")
    curves, transform = validate_frozen_inputs(root)
    expected_transform_hash = sha256(strict_json(transform).encode("ascii")).hexdigest()
    if seal.get("qualified_header_transform_sha256") != expected_transform_hash:
        for curve in curves.values():
            curve.fill(0.0)
        raise PieExecutorError("QUALIFIED_HEADER_TRANSFORM_CHANGED")
    return seal, curves, transform


def _requests_module() -> Any:
    return qualified._requests_module()


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
            headers={"User-Agent": "Satellite-RF-Observatory/PIE-primary"},
            timeout=HTTP_TIMEOUT_S,
        )
        _raise_transport_status(response, "GSSC_LOGIN")
        _bounded_content(response, 100_000, "GSSC_LOGIN_RESPONSE")
        return session
    except PrimaryDescriptionError:
        raise
    except TransportInterruption:
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
                headers={"User-Agent": "Satellite-RF-Observatory/PIE-primary"},
                timeout=HTTP_TIMEOUT_S,
            )
            _raise_transport_status(response, "GSSC_CHDIR")
            result = _bounded_content(response, 10_000, "GSSC_CHDIR_RESPONSE")
            if result.strip() != b"Operation successful!":
                raise PrimaryDescriptionError(f"GSSC_CHDIR_FAILED:{component}")
        response = session.get(
            GSSC_WEB_ROOT + "dir.html",
            headers={"User-Agent": "Satellite-RF-Observatory/PIE-primary"},
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
    try:
        response = session.get(
            GSSC_WEB_ROOT + "?download&filename=" + PRIMARY.name,
            headers={"User-Agent": "Satellite-RF-Observatory/PIE-primary"},
            timeout=HTTP_TIMEOUT_S,
            stream=True,
        )
        _raise_transport_status(response, "GSSC_DOWNLOAD")
        payload = bytearray()
        for block in response.iter_content(chunk_size=1024 * 1024):
            if block:
                payload.extend(block)
            if len(payload) > MAX_COMPRESSED_BYTES:
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
                "preexisting_cddis_description_used_as_identity": False,
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
        return bytearray(hatanaka.decompress(bytes(payload), strict=True))
    except Exception as exc:
        raise PrimaryMeasurementInvalid("HATANAKA_DECOMPRESSION_FAILED") from exc


def _normalize(value: object) -> str:
    return " ".join(str(value).split())


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
    scale = list(parsed.get("scale_factor_records", ()))
    if scale != expected["scale_factor_records"]:
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
    if abs(deviation) > plan.MAXIMUM_EVENT_TIME_ERROR_S:
        raise PrimaryNotDetectable("EVENT_TIME_BOUND_EXCEEDED")
    return index, float(deviation)


def _read_window_records(
    reader: rinex._LineReader,
    system_types: Mapping[str, Sequence[str]],
) -> tuple[
    dict[tuple[int, str], rinex._Record],
    dict[int, int],
    dict[int, float],
]:
    epochs = expected_raw_gps_epochs()
    start = epochs[0] - timedelta(seconds=plan.MAXIMUM_EVENT_TIME_ERROR_S)
    stop = epochs[-1] + timedelta(seconds=plan.MAXIMUM_EVENT_TIME_ERROR_S)
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
                    np.abs(second) > plan.GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M
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
            witness -= witness[plan.ANCHOR_INDEX]
            peak_to_peak = float(np.ptp(witness))
            witness_links.append(
                {
                    "satellite": satellite,
                    "full_window_peak_to_peak_m": peak_to_peak,
                    "limit_m": plan.CODE_PHASE_PER_SATELLITE_PTP_LIMIT_M,
                    "state": (
                        "SATISFIED"
                        if peak_to_peak <= plan.CODE_PHASE_PER_SATELLITE_PTP_LIMIT_M
                        else "UNSATISFIED"
                    ),
                }
            )
            witness.fill(0.0)
        failed_witness = next(
            (row for row in witness_links if row["state"] == "UNSATISFIED"), None
        )
        if failed_witness is not None:
            raise PrimaryNotDetectable(
                "SAME_PATH_CODE_PHASE_WITNESS_OVER_LIMIT:"
                f"{failed_witness['satellite']}"
            )
        coordinate = phase_if[:, 0] - phase_if[:, 1]
        coordinate -= coordinate[plan.ANCHOR_INDEX]
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
                "limit_s": plan.MAXIMUM_EVENT_TIME_ERROR_S,
            },
            "core_phase_and_lli": "SATISFIED",
            "geometry_free_phase_health": {
                "state": "SATISFIED",
                "limit_m": plan.GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M,
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


def score_coordinate(
    observed_m: Sequence[float], curves: Mapping[str, Sequence[float]]
) -> dict[str, object]:
    observed = np.asarray(observed_m, dtype=np.float64)
    normalized = {
        name: np.asarray(values, dtype=np.float64) for name, values in curves.items()
    }
    if observed.shape != (plan.RAW_EPOCHS,) or not np.all(np.isfinite(observed)):
        raise PrimaryMeasurementInvalid("OBSERVED_COORDINATE_INVALID")
    if set(normalized) != set(HYPOTHESES) or any(
        values.shape != observed.shape or not np.all(np.isfinite(values))
        for values in normalized.values()
    ):
        raise PieExecutorError("FROZEN_HYPOTHESIS_CURVES_INVALID")
    scores = []
    for name in sorted(HYPOTHESES):
        residual = observed - normalized[name]
        heldout = residual[plan.HELDOUT_START_INDEX :]
        scores.append(
            {
                "hypothesis": name,
                "heldout_peak_to_peak_m": float(np.ptp(heldout)),
                "heldout_rms_m": float(sqrt(float(np.mean(heldout**2)))),
            }
        )
        residual.fill(0.0)
    scores.sort(
        key=lambda row: (
            float(row["heldout_peak_to_peak_m"]),
            float(row["heldout_rms_m"]),
            str(row["hypothesis"]),
        )
    )
    best, runner_up = scores[:2]
    preference_margin = float(runner_up["heldout_peak_to_peak_m"]) - float(
        best["heldout_peak_to_peak_m"]
    )
    outcome = (
        PREFERRED_OUTCOMES[str(best["hypothesis"])]
        if preference_margin > plan.REVISED_PAIRWISE_GUARD_M
        else "AMBIGUOUS"
    )
    result = {
        "outcome": outcome,
        "heldout_comparison": {
            "state": "EVALUATED",
            "raw_indices_inclusive": [79, 138],
            "preference_guard_m": plan.REVISED_PAIRWISE_GUARD_M,
            "best_hypothesis": best["hypothesis"],
            "runner_up_hypothesis": runner_up["hypothesis"],
            "preference_margin_m": preference_margin,
            "scores": scores,
            "nuisance_parameters_fit": 0,
        },
    }
    strict_json(result)
    return result


def _write_json(path: Path, value: object) -> None:
    Path(path).write_text(
        strict_json(value, pretty=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_json_exclusive(path: Path, value: object) -> None:
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(strict_json(value, pretty=True) + "\n")


def run_once(
    output_directory: Path,
    authority_token: str,
    expected_seal_sha256: str,
    executor_seal_path: Path,
    *,
    materializer: Materializer = materialize_gssc,
) -> dict[str, object]:
    if authority_token != AUTHORITY_TOKEN:
        raise PermissionError("PIE_DOY223_PRIMARY_AUTHORITY_REQUIRED")
    output = Path(output_directory)
    outcome_path = output / OUTCOME_NAME
    marker_path = output / AUTHORITY_MARKER_NAME
    if outcome_path.exists() or marker_path.exists():
        raise PermissionError("PIE_DOY223_PRIMARY_AUTHORITY_ALREADY_CONSUMED")
    root = Path(__file__).resolve().parent
    seal, curves, expected_transform = validate_executor_seal(
        root, executor_seal_path, expected_seal_sha256
    )
    marker = {
        "schema": "pie-observer-primary-authority-consumed-v1",
        "state": "ONE_SHOT_AUTHORITY_CONSUMED_BEFORE_NETWORK",
        "executor_seal_sha256": expected_seal_sha256,
        "source_commit": seal["source_commit"],
        "network_requests_before_marker": 0,
        "primary_headers_before_marker": 0,
        "primary_payload_bytes_before_marker": 0,
        "primary_values_before_marker": 0,
    }
    _write_json_exclusive(marker_path, marker)
    compressed: bytearray | None = None
    decoded: bytearray | None = None
    scan: StationMeasurement | None = None
    coordinate: np.ndarray | None = None
    artifact: dict[str, object] | None = None
    try:
        compressed, artifact = materializer()
        if not artifact.get("complete_file_sha256"):
            raise PieExecutorError("COMPLETE_HASH_REQUIRED_BEFORE_DECODE")
        decoded = decompress_in_memory(compressed)
        scan = scan_decoded(decoded, expected_transform)
        coordinate, admission = measurement_coordinate(scan)
        score = score_coordinate(coordinate, curves)
        outcome = {
            "schema": "pie-observer-primary-outcome-v1",
            "executor_version": EXECUTOR_VERSION,
            "outcome": score["outcome"],
            "executor_seal_sha256": expected_seal_sha256,
            "source_commit": seal["source_commit"],
            "source_sha256": seal["source_sha256"],
            "plan_manifest_sha256": prediction.FROZEN_PLAN_MANIFEST_SHA256,
            "prediction_sha256": PREDICTIONS_SHA256,
            "artifact": artifact,
            "measurement_admission": admission,
            "score": score,
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
                "aggregate_admission_and_score_receipt_only": True,
            },
            "retry": {
                "transport_attempts_before_hash": artifact["attempts"],
                "retry_after_complete_hash": False,
                "retry_after_decode": False,
                "new_window_endpoint_feature_threshold_or_null": False,
            },
            "claim_scope": (
                "HELD_OUT_STATION_CONFIRMED_FOR_THIS_ORBIT_SIGNAL_WINDOW"
                if score["outcome"] == "PIE_HELD_OUT_ORBITAL_MODEL_PREFERRED"
                else "NO_POSITIVE_PIE_ORBITAL_CLAIM"
            ),
        }
    except PrimaryMaterializationError as exc:
        outcome = {
            "schema": "pie-observer-primary-outcome-v1",
            "execution_state": "PRIMARY_ARTIFACT_MATERIALIZATION_FAILED",
            "physical_outcome": None,
            "reason": str(exc),
            "artifact": exc.receipt,
            "heldout_comparison": "NOT_EVALUATED",
            "observation_values_persisted": 0,
        }
    except PrimaryNotDetectable as exc:
        outcome = {
            "schema": "pie-observer-primary-outcome-v1",
            "outcome": "NOT_DETECTABLE",
            "reason": str(exc),
            "artifact": artifact,
            "heldout_comparison": "NOT_EVALUATED",
            "observation_values_persisted": 0,
        }
    except PrimaryMeasurementInvalid as exc:
        outcome = {
            "schema": "pie-observer-primary-outcome-v1",
            "outcome": "MEASUREMENT_INVALID",
            "reason": str(exc),
            "artifact": artifact,
            "heldout_comparison": "NOT_EVALUATED",
            "observation_values_persisted": 0,
        }
    except Exception as exc:
        outcome = {
            "schema": "pie-observer-primary-outcome-v1",
            "execution_state": "PRIMARY_DESCRIPTION_ERROR",
            "physical_outcome": None,
            "reason": f"{type(exc).__name__}:{exc}",
            "artifact": artifact,
            "heldout_comparison": "NOT_EVALUATED",
            "observation_values_persisted": 0,
        }
    finally:
        if coordinate is not None:
            coordinate.fill(0.0)
        if scan is not None:
            scan.erase()
        for payload in (decoded, compressed):
            if payload is not None:
                payload[:] = b"\x00" * len(payload)
        for curve in curves.values():
            curve.fill(0.0)
        gc.collect()
    strict_json(outcome)
    _write_json(outcome_path, outcome)
    return outcome


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-executor-seal", action="store_true")
    parser.add_argument("--execute-live", action="store_true")
    parser.add_argument("--authority", default="")
    parser.add_argument("--executor-seal-sha256", default="")
    parser.add_argument("--executor-seal", type=Path)
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path(__file__).resolve().parent,
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    if args.write_executor_seal:
        _write_json(
            args.output_directory / EXECUTOR_SEAL_NAME, build_executor_seal(root)
        )
        print(
            strict_json(
                {
                    "outcome": "PIE_OBSERVER_PRIMARY_EXECUTOR_FROZEN_UNOPENED",
                    "primary_observation_access": 0,
                    "live_execution_authorized": False,
                }
            )
        )
        return
    if not args.execute_live or args.executor_seal is None:
        raise SystemExit("OFFLINE_EXECUTOR_FREEZE_OR_SEPARATE_LIVE_AUTHORITY_REQUIRED")
    result = run_once(
        args.output_directory,
        args.authority,
        args.executor_seal_sha256,
        args.executor_seal,
    )
    print(
        strict_json(
            {
                "outcome": result.get("outcome", result.get("execution_state")),
                "outcome_written": True,
            }
        )
    )


if __name__ == "__main__":
    main()
