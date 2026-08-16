"""Gate F2.2: one frozen multipath bootstrap and at most one A->B->A.

This is a disposable vertical runner. It does not scan, persist endpoints, or
turn listings into RF evidence. All discovery and RF artifacts remain in RAM;
only strict JSON receipts and hashes cross the descriptive boundary.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from hashlib import sha256
from pathlib import Path
import re
import subprocess
import time
from typing import Callable, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from . import kiwi_gate_f2 as f2
from . import kiwi_probe as kiwi
from .models import emit_jsonl, strict_json_value


PRIMARY_LISTING = "https://kiwisdr.com/.public/"
FALLBACK_LISTING = "https://kiwisdr.com/public/"
DISCOVERY_BUDGET_S = 90.0
DISCOVERY_TIMEOUT_S = 8.0
RANKING_POLICY_VERSION = "gate-f2-lexicographic-falsification-v1"
QUALIFICATION_POLICY_VERSION = "gate-f2.2-direct-stream-retune-v1"
FREQUENCY_POLICY_VERSION = "gate-f2-targetless-waterfall-centers-v1"


class BootstrapOrigin(str, Enum):
    PROVIDER_LISTING = "PROVIDER_LISTING"
    LISTING_TRANSPORT_FALLBACK = "LISTING_TRANSPORT_FALLBACK"
    SESSION_AFFORDANCE = "SESSION_AFFORDANCE"


@dataclass(frozen=True, slots=True)
class SessionAffordance:
    endpoint: kiwi.KiwiEndpoint
    provenance: tuple[str, ...]


SESSION_AFFORDANCES = (
    SessionAffordance(
        kiwi.KiwiEndpoint("hooksiel", "dl1bajkiwisdr.ddns.net", 8074),
        ("tracked:experiments/live_instrument/kiwi_probe.py", "tracked:experiments/live_instrument/kiwi_prospective.py"),
    ),
    SessionAffordance(
        kiwi.KiwiEndpoint("doncaster", "g0ghk.uk", 8050),
        ("tracked:experiments/live_instrument/kiwi_probe.py", "tracked:experiments/live_instrument/kiwi_prospective.py"),
    ),
    SessionAffordance(
        kiwi.KiwiEndpoint("n8ga-ohio", "hill.n8ga.org", 8073),
        ("tracked:experiments/live_instrument/kiwi_gate_e.py", "frozen-gate-e:a0838a1"),
    ),
    SessionAffordance(
        kiwi.KiwiEndpoint("blair-washington", "kiwisdr2blair.ddns.net", 8073),
        ("tracked:experiments/live_instrument/kiwi_gate_e.py", "frozen-gate-e:a0838a1"),
    ),
    SessionAffordance(
        kiwi.KiwiEndpoint("kfs-california", "kiwisdr.kfsdr.com", 8074),
        ("tracked:experiments/live_instrument/kiwi_gate_e.py", "frozen-gate-e:a0838a1"),
    ),
    SessionAffordance(
        kiwi.KiwiEndpoint("va6ok-alberta", "va6ok.ddns.net", 8073),
        ("tracked:experiments/live_instrument/kiwi_gate_e.py", "frozen-gate-e:a0838a1"),
    ),
)


@dataclass(frozen=True, slots=True)
class BootstrapPathPlan:
    path_id: str
    bootstrap_origin: BootstrapOrigin
    provider: str
    inventory_root: str
    transport_route: str
    access_mode: str

    def __post_init__(self) -> None:
        if not all((self.path_id, self.provider, self.inventory_root, self.transport_route, self.access_mode)):
            raise ValueError("bootstrap path lineage cannot be empty")


@dataclass(frozen=True, slots=True)
class BootstrapPlanReceipt:
    started_at: datetime
    budget_s: float
    discovery_paths: tuple[BootstrapPathPlan, ...]
    path_order_or_concurrency: str
    retry_budget: int
    session_affordance_hash: str
    ranking_policy_version: str
    qualification_policy_version: str
    frequency_policy_version: str
    gate_f2_runtime_commit: str
    transform_versions: tuple[str, ...]
    mother_plan_hash: str

    def __post_init__(self) -> None:
        f2._utc(self.started_at)
        if self.budget_s != DISCOVERY_BUDGET_S:
            raise ValueError("Gate F2.2 discovery budget is frozen at 90 seconds")
        if not 1 <= len(self.discovery_paths) <= 3:
            raise ValueError("Gate F2.2 allows one to three frozen discovery paths")
        if len({path.path_id for path in self.discovery_paths}) != len(self.discovery_paths):
            raise ValueError("bootstrap path ids must be unique")
        if self.path_order_or_concurrency != "CONCURRENT_FROZEN_SET":
            raise ValueError("Gate F2.2 path scheduling must be frozen as concurrent")
        if self.retry_budget != 1:
            raise ValueError("Gate F2.2 allows at most one retry per transport path")
        if re.fullmatch(r"[0-9a-f]{64}", self.session_affordance_hash) is None:
            raise ValueError("session affordance hash must be SHA-256")
        if re.fullmatch(r"[0-9a-f]{40}", self.gate_f2_runtime_commit) is None:
            raise ValueError("Gate F2 runtime commit must be a full Git commit")
        if not self.ranking_policy_version or not self.qualification_policy_version or not self.frequency_policy_version:
            raise ValueError("bootstrap plan must freeze ranking, qualification and frequency policies")
        if not self.transform_versions or not self.mother_plan_hash:
            raise ValueError("bootstrap plan must freeze transforms and the mother plan")
        roots = {
            path.bootstrap_origin: path.inventory_root for path in self.discovery_paths
        }
        if roots.get(BootstrapOrigin.PROVIDER_LISTING) != roots.get(BootstrapOrigin.LISTING_TRANSPORT_FALLBACK):
            raise ValueError("primary and fallback listing must retain their shared inventory root")

    @property
    def plan_hash(self) -> str:
        return f2._hash(asdict(self))


@dataclass(frozen=True, slots=True)
class CandidateReceipt:
    endpoint: kiwi.KiwiEndpoint
    endpoint_identity: str
    bootstrap_origin: BootstrapOrigin
    inventory_root: str
    listing_transport: str
    discovery_receipt_hash: str
    discovered_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        if self.endpoint_identity != endpoint_identity(self.endpoint):
            raise ValueError("candidate endpoint identity is not canonical")
        if re.fullmatch(r"[0-9a-f]{64}", self.discovery_receipt_hash) is None:
            raise ValueError("candidate must bind to an atomic discovery receipt")
        if f2._utc(self.expires_at) <= f2._utc(self.discovered_at):
            raise ValueError("candidate receipt TTL must be positive")

    @property
    def receipt_hash(self) -> str:
        return f2._hash(asdict(self))


@dataclass(frozen=True, slots=True)
class DeduplicatedCandidate:
    endpoint: kiwi.KiwiEndpoint
    endpoint_identity: str
    all_bootstrap_origins: tuple[BootstrapOrigin, ...]
    inventory_roots: tuple[str, ...]
    listing_transports: tuple[str, ...]
    candidate_receipt_hashes: tuple[str, ...]
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class PathExecution:
    path: BootstrapPathPlan
    receipts: tuple[f2.DiscoveryReceipt, ...]
    candidates: tuple[kiwi.KiwiEndpoint, ...]


def endpoint_identity(endpoint: kiwi.KiwiEndpoint) -> str:
    return f"{endpoint.host.lower()}:{endpoint.port}"


def session_affordance_hash(affordances: Sequence[SessionAffordance] = SESSION_AFFORDANCES) -> str:
    payload = tuple(
        {
            "endpoint": asdict(item.endpoint),
            "provenance": item.provenance,
        }
        for item in sorted(affordances, key=lambda value: endpoint_identity(value.endpoint))
    )
    return f2._hash(payload)


def runtime_commit() -> str:
    repository = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    commit = completed.stdout.strip().lower()
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise RuntimeError("could not resolve a full Gate F2 runtime commit")
    dirty = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    if dirty.strip():
        raise RuntimeError("Gate F2.2 refuses network execution from an uncommitted worktree")
    return commit


def build_bootstrap_plan(
    mother: f2.MotherPlan,
    *,
    started_at: datetime,
    gate_f2_runtime_commit: str,
) -> BootstrapPlanReceipt:
    paths = (
        BootstrapPathPlan(
            "A-primary-official",
            BootstrapOrigin.PROVIDER_LISTING,
            "KiwiSDR official public listing",
            "kiwisdr-public-registry",
            PRIMARY_LISTING,
            "public HTTPS GET",
        ),
        BootstrapPathPlan(
            "B-fallback-official",
            BootstrapOrigin.LISTING_TRANSPORT_FALLBACK,
            "KiwiSDR official public listing",
            "kiwisdr-public-registry",
            FALLBACK_LISTING,
            "public HTTPS GET fallback transport",
        ),
        BootstrapPathPlan(
            "C-frozen-session-affordances",
            BootstrapOrigin.SESSION_AFFORDANCE,
            "frozen prior receipts",
            "session-affordance:tracked-receipts",
            "session://frozen-prior-receipts",
            "finite preauthorized in-memory affordance set",
        ),
    )
    return BootstrapPlanReceipt(
        f2._utc(started_at),
        DISCOVERY_BUDGET_S,
        paths,
        "CONCURRENT_FROZEN_SET",
        1,
        session_affordance_hash(),
        RANKING_POLICY_VERSION,
        QUALIFICATION_POLICY_VERSION,
        FREQUENCY_POLICY_VERSION,
        gate_f2_runtime_commit,
        (
            f2.TRANSFORM_VERSION,
            f"kiwi-server:{f2.KIWI_SERVER_COMMIT}",
            f"kiwiclient:{f2.KIWI_CLIENT_COMMIT}",
        ),
        mother.plan_hash,
    )


def _error_receipt(
    path: BootstrapPathPlan,
    mother: f2.MotherPlan,
    started: datetime,
    completed: datetime,
    status: f2.DiscoveryResponseStatus,
    error: Exception,
    retry_index: int,
    *,
    response_hash: str | None = None,
) -> f2.DiscoveryReceipt:
    return f2.DiscoveryReceipt(
        path.provider,
        path.inventory_root,
        path.transport_route,
        path.access_mode,
        started,
        completed,
        status,
        0,
        response_hash,
        type(error).__name__,
        str(error),
        retry_index,
        completed + timedelta(seconds=mother.offer_ttl_s),
    )


def _listing_attempt(
    path: BootstrapPathPlan,
    mother: f2.MotherPlan,
    *,
    retry_index: int,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> f2.DiscoveryAttempt:
    started = f2._utc(now())
    try:
        request = Request(path.transport_route, headers={"User-Agent": "Satellite-RF-Observatory-Gate-F2.2/0.1"})
        with urlopen(request, timeout=DISCOVERY_TIMEOUT_S) as response:
            payload = response.read()
            status_code = getattr(response, "status", 200)
        completed = f2._utc(now())
        response_hash = sha256(payload).hexdigest()
        if status_code is not None and not 200 <= int(status_code) < 300:
            error = RuntimeError(f"HTTP status {status_code}")
            return f2.DiscoveryAttempt(
                _error_receipt(
                    path, mother, started, completed,
                    f2.DiscoveryResponseStatus.PROTOCOL_ERROR, error, retry_index,
                    response_hash=response_hash,
                ),
                (),
            )
        try:
            text = payload.decode("utf-8", errors="strict")
            candidates = f2._parse_directory_endpoints(text, mother)
        except Exception as error:
            return f2.DiscoveryAttempt(
                _error_receipt(
                    path, mother, started, completed,
                    f2.DiscoveryResponseStatus.DESCRIPTION_ERROR, error, retry_index,
                    response_hash=response_hash,
                ),
                (),
            )
        result_status = (
            f2.DiscoveryResponseStatus.VALID_CANDIDATE_RESULT
            if candidates
            else f2.DiscoveryResponseStatus.VALID_EMPTY_RESULT
        )
        receipt = f2.DiscoveryReceipt(
            path.provider,
            path.inventory_root,
            path.transport_route,
            path.access_mode,
            started,
            completed,
            result_status,
            len(candidates),
            response_hash,
            None,
            None,
            retry_index,
            completed + timedelta(seconds=mother.offer_ttl_s),
        )
        return f2.DiscoveryAttempt(receipt, candidates)
    except HTTPError as error:
        completed = f2._utc(now())
        try:
            payload = error.read()
        except Exception:
            payload = None
        receipt = _error_receipt(
            path, mother, started, completed,
            f2.DiscoveryResponseStatus.PROTOCOL_ERROR, error, retry_index,
            response_hash=sha256(payload).hexdigest() if payload is not None else None,
        )
        return f2.DiscoveryAttempt(receipt, ())
    except (URLError, OSError, TimeoutError) as error:
        completed = f2._utc(now())
        return f2.DiscoveryAttempt(
            _error_receipt(
                path, mother, started, completed,
                f2.DiscoveryResponseStatus.TRANSPORT_ERROR, error, retry_index,
            ),
            (),
        )
    except Exception as error:
        completed = f2._utc(now())
        return f2.DiscoveryAttempt(
            _error_receipt(
                path, mother, started, completed,
                f2.DiscoveryResponseStatus.DESCRIPTION_ERROR, error, retry_index,
            ),
            (),
        )


def _session_attempt(
    path: BootstrapPathPlan,
    mother: f2.MotherPlan,
    *,
    retry_index: int,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> f2.DiscoveryAttempt:
    started = f2._utc(now())
    candidates = tuple(item.endpoint for item in SESSION_AFFORDANCES)
    completed = f2._utc(now())
    status = (
        f2.DiscoveryResponseStatus.VALID_CANDIDATE_RESULT
        if candidates
        else f2.DiscoveryResponseStatus.VALID_EMPTY_RESULT
    )
    receipt = f2.DiscoveryReceipt(
        path.provider,
        path.inventory_root,
        path.transport_route,
        path.access_mode,
        started,
        completed,
        status,
        len(candidates),
        session_affordance_hash(),
        None,
        None,
        retry_index,
        completed + timedelta(seconds=mother.offer_ttl_s),
    )
    return f2.DiscoveryAttempt(receipt, candidates)


def _execute_path(
    path: BootstrapPathPlan,
    mother: f2.MotherPlan,
    deadline_monotonic: float,
) -> PathExecution:
    receipts: list[f2.DiscoveryReceipt] = []
    for retry_index in range(2):
        if path.bootstrap_origin is BootstrapOrigin.SESSION_AFFORDANCE:
            attempt = _session_attempt(path, mother, retry_index=retry_index)
        elif time.monotonic() >= deadline_monotonic:
            now = datetime.now(timezone.utc)
            error = TimeoutError("frozen 90-second discovery budget exhausted")
            attempt = f2.DiscoveryAttempt(
                _error_receipt(
                    path, mother, now, now,
                    f2.DiscoveryResponseStatus.TRANSPORT_ERROR, error, retry_index,
                ),
                (),
            )
        else:
            attempt = _listing_attempt(path, mother, retry_index=retry_index)
        receipts.append(attempt.receipt)
        if attempt.receipt.successful:
            return PathExecution(path, tuple(receipts), attempt.candidates)
        if retry_index >= 1 or path.bootstrap_origin is BootstrapOrigin.SESSION_AFFORDANCE:
            break
    return PathExecution(path, tuple(receipts), ())


def execute_bootstrap(
    plan: BootstrapPlanReceipt,
    mother: f2.MotherPlan,
    *,
    sink: Callable[[str], None],
) -> tuple[
    tuple[f2.DiscoveryReceipt, ...],
    tuple[CandidateReceipt, ...],
    tuple[DeduplicatedCandidate, ...],
]:
    deadline = time.monotonic() + plan.budget_s
    executions: list[PathExecution] = []
    with ThreadPoolExecutor(max_workers=len(plan.discovery_paths)) as pool:
        futures = [pool.submit(_execute_path, path, mother, deadline) for path in plan.discovery_paths]
        for future in as_completed(futures):
            executions.append(future.result())
    executions.sort(key=lambda item: item.path.path_id)

    discovery_receipts: list[f2.DiscoveryReceipt] = []
    candidate_receipts: list[CandidateReceipt] = []
    for execution in executions:
        for receipt in execution.receipts:
            discovery_receipts.append(receipt)
            emit_jsonl(
                "gate_f2_2_discovery_receipt",
                {
                    "path_id": execution.path.path_id,
                    "bootstrap_origin": execution.path.bootstrap_origin,
                    "receipt": receipt,
                },
                sink=sink,
            )
        if not execution.candidates:
            continue
        receipt = execution.receipts[-1]
        receipt_hash = f2._hash(asdict(receipt))
        for endpoint in execution.candidates:
            candidate = CandidateReceipt(
                endpoint,
                endpoint_identity(endpoint),
                execution.path.bootstrap_origin,
                execution.path.inventory_root,
                execution.path.transport_route,
                receipt_hash,
                receipt.completed_at,
                receipt.expires_at,
            )
            candidate_receipts.append(candidate)
            emit_jsonl("gate_f2_2_candidate_receipt", candidate, sink=sink)

    grouped: dict[str, list[CandidateReceipt]] = {}
    for candidate in candidate_receipts:
        grouped.setdefault(candidate.endpoint_identity, []).append(candidate)
    deduplicated: list[DeduplicatedCandidate] = []
    for identity, items in sorted(grouped.items()):
        endpoint = sorted(items, key=lambda item: (item.endpoint.name, item.endpoint.host, item.endpoint.port))[0].endpoint
        merged = DeduplicatedCandidate(
            endpoint,
            identity,
            tuple(sorted({item.bootstrap_origin for item in items}, key=lambda item: item.value)),
            tuple(sorted({item.inventory_root for item in items})),
            tuple(sorted({item.listing_transport for item in items})),
            tuple(sorted(item.receipt_hash for item in items)),
            min(item.expires_at for item in items),
        )
        deduplicated.append(merged)
        emit_jsonl("gate_f2_2_candidate_deduplicated", merged, sink=sink)
    return tuple(discovery_receipts), tuple(candidate_receipts), tuple(deduplicated)


def _qualification_scout_plan(mother: f2.MotherPlan, center_hz: float) -> kiwi.ScoutPlan:
    return kiwi.ScoutPlan(
        center_frequencies_hz=(center_hz,),
        scout_duration_s=mother.qualification_duration_s,
        nperseg=mother.nperseg,
        noverlap=mother.noverlap,
        region_shapes=((3, 2),),
        null_shift_count=1,
        significance_alpha=1.0,
        max_gps_solution_age_s=mother.maximum_gps_solution_age_s,
        max_arrival_latency_s=mother.maximum_arrival_latency_s,
        min_overlap_s=min(1.5, mother.qualification_duration_s / 2.0),
    )


def _audit_summary(capture: kiwi.KiwiCapture, audit: kiwi.CaptureAudit, artifact_hash: str) -> dict[str, object]:
    return {
        "endpoint_identity": endpoint_identity(capture.endpoint),
        "artifact_hash": artifact_hash,
        "byte_count": sum(block.samples.nbytes for block in capture.blocks),
        "event_start": capture.event_start,
        "event_end": capture.event_end,
        "declared_tuning_hz": capture.center_frequency_hz,
        "sample_rate_hz": capture.sample_rate_hz,
        "usable": audit.usable,
        "reasons": audit.reasons,
        "sequence_gap_count": audit.sequence_gap_count,
        "timestamp_gap_count": audit.timestamp_gap_count,
        "dropped_block_count": audit.dropped_block_count,
        "overflow_count": sum(block.adc_overflow for block in capture.blocks),
        "continuous_duration_s": audit.overlap_ready_duration_s,
        "sample_rate_drift_ppm": audit.sample_rate_drift_ppm,
        "arrival_latency_p95_s": audit.arrival_latency_p95_s,
        "gps_solution_age_max_s": audit.gps_solution_age_max_s,
        "transform_version": f2.TRANSFORM_VERSION,
    }


def _successful_path_count(receipts: Sequence[f2.DiscoveryReceipt]) -> int:
    return len({
        (receipt.provider, receipt.inventory_root, receipt.transport_route)
        for receipt in receipts
        if receipt.successful
    })


def _run_qualification_and_experiment(
    mother: f2.MotherPlan,
    discovery_receipts: tuple[f2.DiscoveryReceipt, ...],
    candidate_receipts: tuple[CandidateReceipt, ...],
    candidates: tuple[DeduplicatedCandidate, ...],
    *,
    overall_deadline: float,
    sink: Callable[[str], None],
) -> f2.GateF2Result:
    endpoints = tuple(item.endpoint for item in candidates)
    successful_paths = _successful_path_count(discovery_receipts)
    provenance = {item.endpoint_identity: item for item in candidates}
    candidate_hashes = tuple(item.receipt_hash for item in candidate_receipts)
    descriptions = f2.qualify_endpoint_descriptions(endpoints, mother)
    for description in descriptions:
        lineage = provenance[endpoint_identity(description.endpoint)]
        direct_valid = description.state is f2.CapabilityState.CAPABILITY_QUALIFIED
        emit_jsonl(
            "gate_f2_2_direct_probe",
            {
                "endpoint_identity": endpoint_identity(description.endpoint),
                "all_bootstrap_origins": lineage.all_bootstrap_origins,
                "inventory_roots": lineage.inventory_roots,
                "listing_transports": lineage.listing_transports,
                "direct_probe_state": "DIRECT_TRANSPORT_VALID" if direct_valid else description.state,
                "endpoint_reachable": description.state is not f2.CapabilityState.QUALIFICATION_ERROR,
                "capability_offer_created": direct_valid,
                "qualification_state": "PENDING_STREAM" if direct_valid else description.state,
                "stream_capability": "NOT_EVALUATED",
                "event_time_semantics": "NOT_EVALUATED",
                "hardware_root": None,
                "reason": description.reason,
                "status_hash": description.status_hash,
                "expires_at": description.expires_at,
            },
            sink=sink,
        )
    description_hashes = tuple(item.status_hash for item in descriptions)
    direct_ready = [item for item in descriptions if item.state is f2.CapabilityState.CAPABILITY_QUALIFIED]
    if len(direct_ready) < 2:
        result = f2.no_experiment_result(
            f2.OutcomeKind.NO_CAPABILITY_QUALIFIED,
            "fewer than two candidates passed the direct status preconditions; stream/event-time qualification was not entered",
            progress=f2.GateProgress(f2.GatePhase.QUALIFICATION, successful_paths, len(candidates), 0, 0),
            discovery_receipts=discovery_receipts,
            candidate_hashes=candidate_hashes + description_hashes,
        )
        emit_jsonl("gate_f2_2_first_outcome", result, sink=sink)
        return result

    pairs = f2.enumerate_hardware_pairs(descriptions, mother)
    if not pairs:
        result = f2.no_experiment_result(
            f2.OutcomeKind.NO_CAPABILITY_QUALIFIED,
            "direct probes returned candidates, but no pair could enter independent dual-stream qualification",
            progress=f2.GateProgress(f2.GatePhase.QUALIFICATION, successful_paths, len(candidates), 0, 0),
            discovery_receipts=discovery_receipts,
            candidate_hashes=candidate_hashes + description_hashes,
        )
        emit_jsonl("gate_f2_2_first_outcome", result, sink=sink)
        return result

    retry_budget = f2._RetryBudget(mother.maximum_prefreeze_retries, set())
    qualification_hashes: list[str] = list(candidate_hashes + description_hashes)
    qualified_roots: set[str] = set()
    admitted_roots: set[str] = set()
    saw_admissible_pair_without_plan = False

    for pair_index, (left_description, right_description) in enumerate(pairs):
        if time.monotonic() >= overall_deadline:
            break
        endpoints_pair = (left_description.endpoint, right_description.endpoint)
        pair_key = f"pair:{pair_index}:{endpoint_identity(endpoints_pair[0])}:{endpoint_identity(endpoints_pair[1])}"
        waterfall = left_waterfall = right_waterfall = None
        try:
            def waterfall_operation():
                with ThreadPoolExecutor(max_workers=2) as pool:
                    artifacts = tuple(pool.map(lambda endpoint: f2._capture_waterfall(endpoint, mother.waterfall_frames), endpoints_pair))
                return artifacts

            waterfall = f2._prefreeze_call(f"{pair_key}:waterfall", waterfall_operation, retry_budget, sink)
            left_waterfall, right_waterfall = waterfall
            qualification_hashes.extend((left_waterfall.artifact_hash, right_waterfall.artifact_hash))
            centers = f2.waterfall_center_candidates(left_waterfall, right_waterfall, mother)
            emit_jsonl(
                "gate_f2_2_pair_waterfall",
                {
                    "pair": [endpoint_identity(endpoint) for endpoint in endpoints_pair],
                    "artifact_hashes": [left_waterfall.artifact_hash, right_waterfall.artifact_hash],
                    "candidate_center_count": len(centers),
                    "event_time_semantics": "arrival-time only; not a measurement root",
                },
                sink=sink,
            )
            del waterfall, left_waterfall, right_waterfall
        except Exception as error:
            waterfall = left_waterfall = right_waterfall = None
            emit_jsonl("gate_f2_2_qualification_error", {"candidate_key": pair_key, "stage": "waterfall", "reason": str(error)}, sink=sink)
            continue
        if not centers:
            emit_jsonl("gate_f2_2_capability_rejected", {"candidate_key": pair_key, "reason": "no simultaneously salient coarse RF region"}, sink=sink)
            continue

        for center_index, center_hz in enumerate(centers):
            if time.monotonic() >= overall_deadline:
                break
            center_key = f"{pair_key}:center:{center_index}:{center_hz:.3f}"
            baseline_hashes: tuple[str, str] = ()
            captures = left_capture = right_capture = None
            try:
                captures = f2._prefreeze_call(
                    center_key,
                    lambda: kiwi.capture_dual_kiwi(
                        endpoints_pair,
                        center_frequency_hz=center_hz,
                        duration_s=mother.qualification_duration_s,
                        max_gps_solution_age_s=mother.maximum_gps_solution_age_s,
                    ),
                    retry_budget,
                    sink,
                )
                left_capture, right_capture = captures
                baseline_hashes = (kiwi._capture_hash(left_capture), kiwi._capture_hash(right_capture))
                qualification_hashes.extend(baseline_hashes)
                audit_plan = _qualification_scout_plan(mother, center_hz)
                audits = (kiwi.audit_capture(left_capture, audit_plan), kiwi.audit_capture(right_capture, audit_plan))
                emit_jsonl(
                    "gate_f2_2_stream_audit",
                    {
                        "candidate_key": center_key,
                        "roots": (
                            _audit_summary(left_capture, audits[0], baseline_hashes[0]),
                            _audit_summary(right_capture, audits[1], baseline_hashes[1]),
                        ),
                    },
                    sink=sink,
                )
                if not all(audit.usable for audit in audits):
                    emit_jsonl(
                        "gate_f2_2_capability_rejected",
                        {"candidate_key": center_key, "reason": "dual IQ stream failed event-time, continuity or sample-integrity admission"},
                        sink=sink,
                    )
                    del captures, left_capture, right_capture
                    continue
                geometry = f2.find_target_and_witness(left_capture, right_capture, mother)
                del captures, left_capture, right_capture
            except ValueError as error:
                captures = left_capture = right_capture = None
                emit_jsonl("gate_f2_2_capability_rejected", {"candidate_key": center_key, "reason": str(error), "artifact_hashes": baseline_hashes}, sink=sink)
                continue
            except Exception as error:
                captures = left_capture = right_capture = None
                emit_jsonl("gate_f2_2_qualification_error", {"candidate_key": center_key, "stage": "dual_stream", "reason": str(error), "artifact_hashes": baseline_hashes}, sink=sink)
                continue

            try:
                qualification = f2._prefreeze_call(
                    f"{center_key}:retune-witness",
                    lambda: f2.qualify_geometry_orientation(endpoints_pair, geometry, mother),
                    retry_budget,
                    sink,
                )
                qualification_hashes.extend(qualification.qualification_hashes)
            except ValueError as error:
                emit_jsonl("gate_f2_2_capability_rejected", {"candidate_key": center_key, "reason": str(error), "stage": "retune_witness"}, sink=sink)
                continue
            except Exception as error:
                emit_jsonl("gate_f2_2_qualification_error", {"candidate_key": center_key, "reason": str(error), "stage": "retune_witness"}, sink=sink)
                continue

            roots = {
                f"kiwi:{qualification.reference.host}:{qualification.reference.port}",
                f"kiwi:{qualification.perturbed.host}:{qualification.perturbed.port}",
            }
            qualified_roots.update(roots)
            emit_jsonl(
                "gate_f2_2_capability_qualified",
                {
                    "candidate_key": center_key,
                    "hardware_roots": tuple(sorted(roots)),
                    "stream_real": True,
                    "event_time_valid": True,
                    "continuity": True,
                    "sample_integrity": True,
                    "retune_controllability": True,
                    "transform_witness": f"axis_orientation={qualification.axis_orientation}",
                    "overlapping_rf_coverage": True,
                    "artifact_hashes": qualification.qualification_hashes,
                    "expires_at": qualification.expires_at,
                },
                sink=sink,
            )
            frozen_at = datetime.now(timezone.utc)
            if frozen_at >= qualification.expires_at:
                emit_jsonl("gate_f2_2_capability_rejected", {"candidate_key": center_key, "reason": "qualified receipt expired before admission"}, sink=sink)
                continue
            admitted_roots.update(roots)
            try:
                plan = f2.freeze_plan(
                    mother,
                    qualification.reference,
                    qualification.perturbed,
                    qualification.geometry.center_a_hz,
                    qualification.geometry.delta_f_hz,
                    qualification.axis_orientation,
                    qualification.target,
                    qualification.witness,
                    frozen_at=frozen_at,
                    prediction_tolerance_hz=qualification.geometry.prediction_tolerance_hz,
                )
            except ValueError as error:
                saw_admissible_pair_without_plan = True
                emit_jsonl("gate_f2_2_admission_rejected", {"candidate_key": center_key, "reason": str(error)}, sink=sink)
                continue
            emit_jsonl(
                "gate_f2_2_plan_frozen",
                {
                    "plan": plan,
                    "plan_hash": plan.plan_hash,
                    "falsification_power_order": (
                        "complete_sequence_coverage",
                        "RF_baseband_distinction",
                        "same_path_retune_witness",
                        "causal_cut_closure",
                        "detectability_margin",
                        "prediction_separation",
                        "continuity_and_event_time",
                        "cost",
                    ),
                },
                sink=sink,
            )
            try:
                confirmation = f2.capture_dual_sequence(
                    (plan.reference_endpoint, plan.perturbed_endpoint),
                    plan.center_a_hz,
                    plan.delta_f_hz,
                    plan.segment_duration_s,
                    plan.settling_s,
                    mother,
                )
                result = f2.evaluate_sequence(plan, confirmation, mother)
                del confirmation
            except Exception as error:
                result = f2._post_freeze_not_detectable(
                    plan,
                    f"single confirmation failed with no retry: {type(error).__name__}: {error}",
                    evaluated_at=datetime.now(timezone.utc),
                )
            emit_jsonl("gate_f2_2_first_outcome", result, sink=sink)
            return result

    if not qualified_roots:
        outcome = f2.OutcomeKind.NO_CAPABILITY_QUALIFIED
        phase = f2.GatePhase.QUALIFICATION
        reason = "no candidate pair completed stream, event-time, integrity and retune-witness qualification"
    elif not admitted_roots:
        outcome = f2.OutcomeKind.NO_CAPABILITY_ADMITTED
        phase = f2.GatePhase.ADMISSION
        reason = "qualified hardware roots existed, but none remained fresh and admissible"
    else:
        outcome = f2.OutcomeKind.NO_FALSIFIABLE_EXPERIMENT_AVAILABLE
        phase = f2.GatePhase.ADMISSION
        reason = (
            "admitted roots produced no frozen intervention with non-overlapping predictions"
            if saw_admissible_pair_without_plan
            else "admitted roots did not yield a complete falsifiable intervention before the frozen deadline"
        )
    result = f2.no_experiment_result(
        outcome,
        reason,
        progress=f2.GateProgress(
            phase,
            successful_paths,
            len(candidates),
            len(qualified_roots),
            len(admitted_roots),
        ),
        discovery_receipts=discovery_receipts,
        candidate_hashes=tuple(dict.fromkeys(qualification_hashes)),
    )
    emit_jsonl("gate_f2_2_first_outcome", result, sink=sink)
    return result


def run_once(
    *,
    mother: f2.MotherPlan | None = None,
    gate_f2_runtime_commit: str | None = None,
    sink: Callable[[str], None] = print,
) -> f2.GateF2Result:
    """Execute exactly one frozen Gate F2.2 session and return its first outcome."""

    mother = mother or f2.MotherPlan()
    started_at = datetime.now(timezone.utc)
    commit = gate_f2_runtime_commit or runtime_commit()
    bootstrap = build_bootstrap_plan(mother, started_at=started_at, gate_f2_runtime_commit=commit)
    # This strict plan receipt and its hash are emitted before any network call.
    strict_json_value(bootstrap)
    emit_jsonl(
        "gate_f2_2_bootstrap_plan_frozen",
        {
            "receipt": bootstrap,
            "bootstrap_plan_hash": bootstrap.plan_hash,
            "bootstrap_mode": "MULTIPATH_WITH_SESSION_AFFORDANCE",
            "session_candidate_count": len(SESSION_AFFORDANCES),
            "candidate_set_hash": bootstrap.session_affordance_hash,
            "provenance": "frozen prior receipts",
        },
        sink=sink,
    )
    emit_jsonl("gate_f2_2_mother_plan_frozen", mother, sink=sink)
    overall_deadline = time.monotonic() + mother.prefreeze_budget_s
    discovery_receipts, candidate_receipts, candidates = execute_bootstrap(bootstrap, mother, sink=sink)
    discovery_terminal = f2.discovery_outcome(discovery_receipts, unique_candidate_count=len(candidates))
    emit_jsonl(
        "gate_f2_2_discovery_outcome",
        {
            "outcome": discovery_terminal,
            "unique_candidate_count": len(candidates),
            "candidate_set_hash": f2._hash(tuple(item.endpoint_identity for item in candidates)),
        },
        sink=sink,
    )
    successful_paths = _successful_path_count(discovery_receipts)
    if discovery_terminal is f2.DiscoveryOutcomeKind.DISCOVERY_PATH_FAILED:
        result = f2.no_experiment_result(
            f2.OutcomeKind.DISCOVERY_PATH_FAILED,
            "no frozen bootstrap path produced a valid result",
            progress=f2.GateProgress(f2.GatePhase.DISCOVERY, 0, 0, 0, 0),
            discovery_receipts=discovery_receipts,
        )
        emit_jsonl("gate_f2_2_first_outcome", result, sink=sink)
        return result
    if discovery_terminal is f2.DiscoveryOutcomeKind.NO_CAPABILITY_DISCOVERED:
        result = f2.no_experiment_result(
            f2.OutcomeKind.NO_CAPABILITY_DISCOVERED,
            "at least one bootstrap path returned a valid empty result",
            progress=f2.GateProgress(f2.GatePhase.DISCOVERY, successful_paths, 0, 0, 0),
            discovery_receipts=discovery_receipts,
        )
        emit_jsonl("gate_f2_2_first_outcome", result, sink=sink)
        return result
    return _run_qualification_and_experiment(
        mother,
        discovery_receipts,
        candidate_receipts,
        candidates,
        overall_deadline=overall_deadline,
        sink=sink,
    )


def main() -> None:
    run_once()


if __name__ == "__main__":
    main()
