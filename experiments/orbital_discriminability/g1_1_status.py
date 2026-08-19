"""Gate G1.1: one bounded metadata/status-only qualification session."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
import re
from typing import Callable, Mapping, Sequence
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from experiments.live_instrument.models import strict_json_value


class G11Outcome(str, Enum):
    MODEL_METADATA_UNAVAILABLE = "MODEL_METADATA_UNAVAILABLE"
    CAPABILITY_DISCOVERY_UNAVAILABLE = "CAPABILITY_DISCOVERY_UNAVAILABLE"
    NO_CAPABILITY_DISCOVERED = "NO_CAPABILITY_DISCOVERED"
    CAPABILITY_QUALIFICATION_INCOMPLETE = "CAPABILITY_QUALIFICATION_INCOMPLETE"
    NO_CAPABILITY_ADMITTED = "NO_CAPABILITY_ADMITTED"
    CAPABILITY_DESCRIPTIONS_MATERIALIZED = "CAPABILITY_DESCRIPTIONS_MATERIALIZED"


class FetchState(str, Enum):
    SUCCESS = "SUCCESS"
    TRANSPORT_ERROR = "TRANSPORT_ERROR"
    PROTOCOL_ERROR = "PROTOCOL_ERROR"
    DESCRIPTION_ERROR = "DESCRIPTION_ERROR"
    INTERACTION_REQUIRED = "INTERACTION_REQUIRED"


class DescriptionState(str, Enum):
    DESCRIPTION_COMPLETE_FOR_G1 = "DESCRIPTION_COMPLETE_FOR_G1"
    DESCRIPTION_INSUFFICIENT = "DESCRIPTION_INSUFFICIENT"
    QUALIFICATION_ERROR = "QUALIFICATION_ERROR"


TRANSMITTER_URL = "https://db.satnogs.org/api/transmitters/?format=json"
CELESTRAK_TEMPLATE = (
    "https://celestrak.org/NORAD/elements/gp.php?CATNR={norad}&FORMAT=JSON"
)
DIRECTORY_URL = "http://rx.kiwisdr.com"
USER_AGENT = "Satellite-RF-Observatory-Gate-G1.1/1.0 status-only"


@dataclass(frozen=True, slots=True)
class G11StatusPlan:
    transmitter_url: str = TRANSMITTER_URL
    celestrak_template: str = CELESTRAK_TEMPLATE
    directory_url: str = DIRECTORY_URL
    minimum_carrier_hz: float = 1_000_000.0
    maximum_carrier_hz: float = 30_000_000.0
    maximum_model_candidates: int = 5
    maximum_directory_endpoints: int = 20
    maximum_element_age_s: float = 259_200.0
    request_timeout_s: float = 15.0
    maximum_transmitter_bytes: int = 8 * 1024 * 1024
    maximum_directory_bytes: int = 1024 * 1024
    maximum_description_bytes: int = 256 * 1024
    retry_count: int = 0

    def validate(self) -> None:
        if self.transmitter_url != TRANSMITTER_URL:
            raise ValueError("Gate G1.1 transmitter route changed")
        if self.celestrak_template != CELESTRAK_TEMPLATE:
            raise ValueError("Gate G1.1 orbital route changed")
        if self.directory_url != DIRECTORY_URL:
            raise ValueError("Gate G1.1 directory route changed")
        if not 0.0 < self.minimum_carrier_hz < self.maximum_carrier_hz:
            raise ValueError("invalid frozen carrier interval")
        if not 1 <= self.maximum_model_candidates <= 5:
            raise ValueError("Gate G1.1 allows at most five model candidates")
        if not 1 <= self.maximum_directory_endpoints <= 20:
            raise ValueError("Gate G1.1 allows at most twenty endpoint descriptions")
        if min(
            self.maximum_element_age_s,
            self.request_timeout_s,
            self.maximum_transmitter_bytes,
            self.maximum_directory_bytes,
            self.maximum_description_bytes,
        ) <= 0:
            raise ValueError("Gate G1.1 budgets must be positive")
        if self.retry_count != 0:
            raise ValueError("Gate G1.1 freezes zero retry")

    @property
    def plan_hash(self) -> str:
        self.validate()
        return _hash_json(asdict(self))


@dataclass(frozen=True, slots=True)
class HTTPResponse:
    status_code: int
    final_url: str
    body: bytes


@dataclass(frozen=True, slots=True)
class FetchReceipt:
    requested_url: str
    final_url: str | None
    state: str
    status_code: int | None
    body_sha256: str | None
    byte_count: int
    error_class: str | None
    detail: str


@dataclass(frozen=True, slots=True)
class TransmitterCandidate:
    norad_cat_id: int
    sat_id: str
    carrier_hz: float
    description: str
    mode: str | None
    metadata_updated: str


@dataclass(frozen=True, slots=True)
class ModelCandidateReceipt:
    norad_cat_id: int
    object_name: str
    carrier_hz: float
    transmitter_description: str
    transmitter_updated: str
    element_epoch: str
    element_age_s: float
    element_sha256: str


@dataclass(frozen=True, slots=True)
class StatusAssessment:
    endpoint: str
    state: str
    status_sha256: str | None
    hardware_root: str
    coordinates: tuple[float, float] | None
    described_band_hz: tuple[float, float] | None
    missing_g1_fields: tuple[str, ...]
    hints: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class G11StatusResult:
    outcome: str
    plan_hash: str
    evaluated_at: str
    transmitter_candidate_count: int
    model_candidates: tuple[ModelCandidateReceipt, ...]
    directory_interaction_required: bool
    endpoint_candidate_count: int
    status_request_count: int
    status_assessments: tuple[StatusAssessment, ...]
    fetch_receipts: tuple[FetchReceipt, ...]
    statement: str
    authorized_claims: tuple[str, ...]
    unauthorized_claims: tuple[str, ...]
    raw_rf_activity: str = "ZERO"
    retries_used: int = 0

    def strict_json(self) -> str:
        return json.dumps(
            strict_json_value(asdict(self)),
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )


Fetcher = Callable[[str, float, int], HTTPResponse]


def run_status_only(
    plan: G11StatusPlan,
    *,
    fetcher: Fetcher,
    evaluated_at: datetime,
) -> G11StatusResult:
    """Execute one zero-retry descriptive session and stop before RF."""

    plan.validate()
    now = _utc(evaluated_at)
    receipts: list[FetchReceipt] = []

    transmitter_receipt, transmitter_body = _fetch(
        plan.transmitter_url,
        plan.maximum_transmitter_bytes,
        plan,
        fetcher,
    )
    receipts.append(transmitter_receipt)
    if transmitter_body is None:
        return _result(
            G11Outcome.MODEL_METADATA_UNAVAILABLE,
            plan,
            now,
            (),
            (),
            receipts,
            "the transmitter metadata route did not materialize a valid response",
        )
    try:
        transmitter_items = _json_array(transmitter_body)
        transmitter_candidates = select_transmitter_candidates(transmitter_items, plan)
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        receipts[-1] = _description_error(receipts[-1], error)
        return _result(
            G11Outcome.MODEL_METADATA_UNAVAILABLE,
            plan,
            now,
            (),
            (),
            receipts,
            "the transmitter response was not a valid bounded candidate description",
        )

    models: list[ModelCandidateReceipt] = []
    for candidate in transmitter_candidates:
        url = plan.celestrak_template.format(norad=candidate.norad_cat_id)
        receipt, body = _fetch(
            url,
            plan.maximum_description_bytes,
            plan,
            fetcher,
        )
        receipts.append(receipt)
        if body is None:
            continue
        try:
            items = _json_array(body)
            if len(items) != 1:
                raise ValueError("CelesTrak response must contain exactly one element set")
            item = items[0]
            epoch = _parse_utc(str(item["EPOCH"]))
            age_s = (now - epoch).total_seconds()
            if age_s < 0.0 or age_s > plan.maximum_element_age_s:
                raise ValueError("element epoch lies outside the frozen freshness interval")
            models.append(
                ModelCandidateReceipt(
                    norad_cat_id=candidate.norad_cat_id,
                    object_name=str(item["OBJECT_NAME"]),
                    carrier_hz=candidate.carrier_hz,
                    transmitter_description=candidate.description,
                    transmitter_updated=candidate.metadata_updated,
                    element_epoch=epoch.isoformat(),
                    element_age_s=float(age_s),
                    element_sha256=sha256(body).hexdigest(),
                )
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            receipts[-1] = _description_error(receipts[-1], error)

    if not models:
        return _result(
            G11Outcome.MODEL_METADATA_UNAVAILABLE,
            plan,
            now,
            transmitter_candidates,
            (),
            receipts,
            "no HF transmitter candidate retained a fresh current orbital element set",
        )

    directory_receipt, directory_body = _fetch(
        plan.directory_url,
        plan.maximum_directory_bytes,
        plan,
        fetcher,
    )
    receipts.append(directory_receipt)
    if directory_body is None:
        return _result(
            G11Outcome.CAPABILITY_DISCOVERY_UNAVAILABLE,
            plan,
            now,
            transmitter_candidates,
            models,
            receipts,
            "the public capability directory route was unavailable",
        )
    try:
        text = directory_body.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        receipts[-1] = _description_error(receipts[-1], error)
        return _result(
            G11Outcome.CAPABILITY_DISCOVERY_UNAVAILABLE,
            plan,
            now,
            transmitter_candidates,
            models,
            receipts,
            "the capability directory was not valid UTF-8 descriptive content",
        )
    if _interaction_required(text):
        receipts[-1] = FetchReceipt(
            **{
                **asdict(receipts[-1]),
                "state": FetchState.INTERACTION_REQUIRED.value,
                "detail": "directory requires a user gesture and custom authorization header",
            }
        )
        return _result(
            G11Outcome.CAPABILITY_DISCOVERY_UNAVAILABLE,
            plan,
            now,
            transmitter_candidates,
            models,
            receipts,
            "the directory requires interactive authorization; Gate G1.1 did not replay or bypass it",
            interaction_required=True,
        )

    endpoints = _directory_endpoints(text, plan.maximum_directory_endpoints)
    if not endpoints:
        return _result(
            G11Outcome.NO_CAPABILITY_DISCOVERED,
            plan,
            now,
            transmitter_candidates,
            models,
            receipts,
            "the valid non-interactive directory contained no endpoint descriptions",
        )

    assessments: list[StatusAssessment] = []
    qualification_error = False
    for endpoint in endpoints:
        status_url = f"{endpoint}/status"
        receipt, body = _fetch(
            status_url,
            plan.maximum_description_bytes,
            plan,
            fetcher,
        )
        receipts.append(receipt)
        if body is None:
            qualification_error = True
            assessments.append(_status_error(endpoint))
            continue
        try:
            status = _parse_status(body)
            assessments.append(_assess_status(endpoint, body, status))
        except (TypeError, ValueError, UnicodeDecodeError) as error:
            receipts[-1] = _description_error(receipts[-1], error)
            qualification_error = True
            assessments.append(_status_error(endpoint))

    complete = tuple(
        item
        for item in assessments
        if item.state == DescriptionState.DESCRIPTION_COMPLETE_FOR_G1.value
    )
    if qualification_error:
        outcome = G11Outcome.CAPABILITY_QUALIFICATION_INCOMPLETE
        statement = (
            "at least one discovered capability could not be described; no global "
            "absence or rejection claim is authorized"
        )
    elif len(complete) < 2:
        outcome = G11Outcome.NO_CAPABILITY_ADMITTED
        statement = (
            "status descriptions were reachable but fewer than two materialized "
            "the fields required to enter pass-specific G1 admission"
        )
    else:
        outcome = G11Outcome.CAPABILITY_DESCRIPTIONS_MATERIALIZED
        statement = (
            "at least two descriptions contain the fields required for a later "
            "pass-specific G1 evaluation; no pair is admitted yet"
        )
    return _result(
        outcome,
        plan,
        now,
        transmitter_candidates,
        models,
        receipts,
        statement,
        endpoint_count=len(endpoints),
        assessments=tuple(assessments),
    )


def select_transmitter_candidates(
    items: Sequence[object],
    plan: G11StatusPlan,
) -> tuple[TransmitterCandidate, ...]:
    by_norad: dict[int, TransmitterCandidate] = {}
    for raw in items:
        if not isinstance(raw, Mapping):
            continue
        try:
            description = str(raw.get("description") or "")
            lowered = description.lower()
            if not any(token in lowered for token in ("beacon", "telemetry", "tlm", "sounder")):
                continue
            if raw.get("alive") is not True or raw.get("status") != "active":
                continue
            if raw.get("unconfirmed") is not False or raw.get("downlink_high") is not None:
                continue
            carrier = float(raw["downlink_low"])
            if not plan.minimum_carrier_hz <= carrier <= plan.maximum_carrier_hz:
                continue
            norad = int(raw["norad_cat_id"])
            candidate = TransmitterCandidate(
                norad,
                str(raw.get("sat_id") or ""),
                carrier,
                description,
                str(raw["mode"]) if raw.get("mode") is not None else None,
                str(raw.get("updated") or ""),
            )
        except (KeyError, TypeError, ValueError):
            continue
        existing = by_norad.get(norad)
        if existing is None or _transmitter_rank(candidate) > _transmitter_rank(existing):
            by_norad[norad] = candidate
    ordered = sorted(
        by_norad.values(),
        key=lambda item: (item.metadata_updated, item.norad_cat_id),
        reverse=True,
    )
    return tuple(ordered[: plan.maximum_model_candidates])


def urlopen_fetch(url: str, timeout_s: float, maximum_bytes: int) -> HTTPResponse:
    request = Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json,text/plain,text/html"},
    )
    try:
        with urlopen(request, timeout=timeout_s) as response:
            body = response.read(maximum_bytes + 1)
            if len(body) > maximum_bytes:
                raise ValueError("response exceeds the frozen byte limit")
            return HTTPResponse(
                int(getattr(response, "status", 200)),
                str(response.geturl()),
                body,
            )
    except HTTPError as error:
        body = error.read(maximum_bytes + 1)
        if len(body) > maximum_bytes:
            raise ValueError("error response exceeds the frozen byte limit") from error
        return HTTPResponse(int(error.code), str(error.geturl()), body)


def _fetch(
    url: str,
    maximum_bytes: int,
    plan: G11StatusPlan,
    fetcher: Fetcher,
) -> tuple[FetchReceipt, bytes | None]:
    try:
        response = fetcher(url, plan.request_timeout_s, maximum_bytes)
        body_hash = sha256(response.body).hexdigest()
        if len(response.body) > maximum_bytes:
            raise ValueError("response exceeds the frozen byte limit")
        if not 200 <= response.status_code < 300:
            return (
                FetchReceipt(
                    url,
                    response.final_url,
                    FetchState.PROTOCOL_ERROR.value,
                    response.status_code,
                    body_hash,
                    len(response.body),
                    "HTTPStatusError",
                    f"HTTP status {response.status_code}",
                ),
                None,
            )
        return (
            FetchReceipt(
                url,
                response.final_url,
                FetchState.SUCCESS.value,
                response.status_code,
                body_hash,
                len(response.body),
                None,
                "bounded descriptive response materialized",
            ),
            response.body,
        )
    except ValueError as error:
        return (
            FetchReceipt(
                url,
                None,
                FetchState.DESCRIPTION_ERROR.value,
                None,
                None,
                0,
                type(error).__name__,
                str(error),
            ),
            None,
        )
    except Exception as error:
        return (
            FetchReceipt(
                url,
                None,
                FetchState.TRANSPORT_ERROR.value,
                None,
                None,
                0,
                type(error).__name__,
                str(error),
            ),
            None,
        )


def _result(
    outcome: G11Outcome,
    plan: G11StatusPlan,
    now: datetime,
    transmitter_candidates: Sequence[TransmitterCandidate],
    models: Sequence[ModelCandidateReceipt],
    receipts: Sequence[FetchReceipt],
    statement: str,
    *,
    interaction_required: bool = False,
    endpoint_count: int = 0,
    assessments: tuple[StatusAssessment, ...] = (),
) -> G11StatusResult:
    result = G11StatusResult(
        outcome=outcome.value,
        plan_hash=plan.plan_hash,
        evaluated_at=now.isoformat(),
        transmitter_candidate_count=len(transmitter_candidates),
        model_candidates=tuple(models),
        directory_interaction_required=interaction_required,
        endpoint_candidate_count=endpoint_count,
        status_request_count=len(assessments),
        status_assessments=assessments,
        fetch_receipts=tuple(receipts),
        statement=statement,
        authorized_claims=(
            "descriptive routes and their exact bounded response hashes were evaluated",
            "no receiver data stream was requested",
        ),
        unauthorized_claims=(
            "no Internet RF capability exists",
            "no satellite signal exists",
            "a transmitter is currently emitting",
            "a candidate orbit has been observed or identified",
        ),
    )
    result.strict_json()
    return result


def _directory_endpoints(text: str, maximum: int) -> tuple[str, ...]:
    endpoints: set[str] = set()
    for raw in re.findall(r"https?://[^\s<>\"']+", text):
        parsed = urlparse(raw.rstrip("/),;"))
        if parsed.scheme != "http" or parsed.hostname is None or parsed.username is not None:
            continue
        port = parsed.port or 80
        if not 1 <= port <= 65535:
            continue
        endpoints.add(f"http://{parsed.hostname.lower()}:{port}")
    return tuple(sorted(endpoints, key=lambda value: sha256(value.encode()).hexdigest())[:maximum])


def _interaction_required(text: str) -> bool:
    lowered = text.lower()
    return (
        "x-kiwi-auth" in lowered
        and ("play_button_click_cb" in lowered or "onclick" in lowered)
    )


def _assess_status(
    endpoint: str,
    body: bytes,
    status: Mapping[str, str],
) -> StatusAssessment:
    missing = (
        "future_pass_availability_guarantee",
        "frequency_feature_resolution_bound",
        "sample_event_time_semantics_and_error",
        "sample_sequence_continuity_and_gap_bound",
        "antenna_to_feature_transform_ledger",
        "same_path_orbital_feature_witnesses",
    )
    location = _status_location(status)
    band = _status_band(status)
    hints = tuple(
        (key, status[key])
        for key in ("name", "gps_good", "ext_api", "users")
        if key in status
    )
    return StatusAssessment(
        endpoint=endpoint,
        state=DescriptionState.DESCRIPTION_INSUFFICIENT.value,
        status_sha256=sha256(body).hexdigest(),
        hardware_root=f"kiwi:{urlparse(endpoint).hostname}:{urlparse(endpoint).port}",
        coordinates=location,
        described_band_hz=band,
        missing_g1_fields=missing,
        hints=hints,
    )


def _status_error(endpoint: str) -> StatusAssessment:
    return StatusAssessment(
        endpoint,
        DescriptionState.QUALIFICATION_ERROR.value,
        None,
        f"kiwi:{urlparse(endpoint).hostname}:{urlparse(endpoint).port}",
        None,
        None,
        (),
        (),
    )


def _parse_status(body: bytes) -> dict[str, str]:
    text = body.decode("utf-8", errors="strict")
    result: dict[str, str] = {}
    for token in text.replace("\n", " ").split():
        if "=" in token:
            key, value = token.split("=", 1)
            result[key] = value
    if not result:
        raise ValueError("status response contains no key/value description")
    return result


def _status_location(status: Mapping[str, str]) -> tuple[float, float] | None:
    for key in ("gps", "loc", "location"):
        numbers = re.findall(r"[-+]?\d+(?:\.\d+)?", status.get(key, ""))
        if len(numbers) >= 2:
            latitude, longitude = float(numbers[0]), float(numbers[1])
            if -90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0:
                return latitude, longitude
    return None


def _status_band(status: Mapping[str, str]) -> tuple[float, float] | None:
    value = status.get("bands") or status.get("band")
    if not value:
        return None
    numbers = re.findall(r"\d+(?:\.\d+)?", value)
    if len(numbers) < 2:
        return None
    low, high = float(numbers[0]), float(numbers[1])
    if "mhz" in value.lower():
        low *= 1_000_000.0
        high *= 1_000_000.0
    if 0.0 <= low < high:
        return low, high
    return None


def _json_array(body: bytes) -> list[object]:
    value = json.loads(body.decode("utf-8", errors="strict"))
    if not isinstance(value, list):
        raise ValueError("response must be a JSON array")
    return value


def _description_error(receipt: FetchReceipt, error: Exception) -> FetchReceipt:
    return FetchReceipt(
        receipt.requested_url,
        receipt.final_url,
        FetchState.DESCRIPTION_ERROR.value,
        receipt.status_code,
        receipt.body_sha256,
        receipt.byte_count,
        type(error).__name__,
        str(error),
    )


def _transmitter_rank(candidate: TransmitterCandidate) -> tuple[int, str, float]:
    lowered = candidate.description.lower()
    priority = 2 if "beacon" in lowered else 1
    return priority, candidate.metadata_updated, -candidate.carrier_hz


def _parse_utc(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    result = datetime.fromisoformat(normalized)
    # CelesTrak OMM JSON serializes EPOCH as UTC without a numeric suffix.
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return _utc(result)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Gate G1.1 requires timezone-aware datetimes")
    return value.astimezone(timezone.utc)


def _hash_json(value: object) -> str:
    encoded = json.dumps(
        strict_json_value(value),
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()
