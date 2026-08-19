"""Gate G1.3: pure receipt logic for one bounded inventory search.

Search and document retrieval are performed outside this module.  The module
only closes a frozen set of search receipts and delegates mechanism clauses to
Gate G1.2.  It cannot contact a receiver or acquire RF.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
from typing import Sequence

from experiments.live_instrument.models import strict_json_value

from .g1_2_inventory import (
    EvidenceBasis,
    G12InventoryPlan,
    InventoryMechanismAssessment,
    InventoryMechanismReceipt,
    evaluate_inventory_mechanism,
)


FROZEN_QUERIES = (
    "public SDR receiver directory API machine readable",
    "KiwiSDR public receiver directory API official",
    "OpenWebRX receiver directory API official",
    "WebSDR server list machine readable API official",
)


class SearchState(str, Enum):
    SUCCESS = "SUCCESS"
    SEARCH_ERROR = "SEARCH_ERROR"


class CandidateAuditState(str, Enum):
    EVALUATED = "EVALUATED"
    QUALIFICATION_ERROR = "QUALIFICATION_ERROR"


class G13Outcome(str, Enum):
    NO_LEGITIMATE_INVENTORY_FOUND = "NO_LEGITIMATE_INVENTORY_FOUND"
    LEGITIMATE_INVENTORY_FOUND = "LEGITIMATE_INVENTORY_FOUND"
    INVENTORY_SEARCH_INCOMPLETE = "INVENTORY_SEARCH_INCOMPLETE"


@dataclass(frozen=True, slots=True)
class G13SearchPlan:
    queries: tuple[str, ...] = FROZEN_QUERIES
    maximum_results_per_query: int = 5
    maximum_candidate_mechanisms: int = 6
    maximum_documents_per_candidate: int = 2
    maximum_document_bytes: int = 1_048_576
    request_timeout_s: float = 15.0
    retry_count: int = 0
    status_requests_allowed: bool = False
    rf_requests_allowed: bool = False

    def validate(self) -> None:
        if self.queries != FROZEN_QUERIES:
            raise ValueError("Gate G1.3 query set and order are frozen")
        if self.maximum_results_per_query != 5:
            raise ValueError("Gate G1.3 freezes five results per query")
        if self.maximum_candidate_mechanisms != 6:
            raise ValueError("Gate G1.3 freezes six candidate mechanisms")
        if self.maximum_documents_per_candidate != 2:
            raise ValueError("Gate G1.3 freezes two documents per candidate")
        if self.maximum_document_bytes != 1_048_576:
            raise ValueError("Gate G1.3 freezes a 1 MiB document limit")
        if self.request_timeout_s != 15.0:
            raise ValueError("Gate G1.3 freezes a 15 s document timeout")
        if self.retry_count != 0:
            raise ValueError("Gate G1.3 freezes zero retry")
        if self.status_requests_allowed or self.rf_requests_allowed:
            raise ValueError("Gate G1.3 cannot request receiver status or RF")

    @property
    def plan_hash(self) -> str:
        self.validate()
        return _hash_json(asdict(self))


@dataclass(frozen=True, slots=True)
class SearchQueryReceipt:
    query: str
    state: str
    result_count: int
    ordered_result_set_sha256: str | None
    candidate_document_urls: tuple[str, ...]
    detail: str
    raw_search_artifact_persisted: bool = False


@dataclass(frozen=True, slots=True)
class CandidateMechanismAudit:
    mechanism_id: str
    search_query: str
    discovery_rank: int
    operator_document_url: str
    operator_document_sha256: str | None
    inventory_url: str | None
    state: str
    inventory_receipt: InventoryMechanismReceipt | None
    detail: str
    raw_documents_persisted: bool = False


@dataclass(frozen=True, slots=True)
class CandidateSearchAssessment:
    mechanism_id: str
    state: str
    mechanism_assessment: InventoryMechanismAssessment | None
    detail: str


@dataclass(frozen=True, slots=True)
class G13SearchResult:
    outcome: str
    plan_hash: str
    evaluated_at: str
    search_receipts: tuple[SearchQueryReceipt, ...]
    candidate_assessments: tuple[CandidateSearchAssessment, ...]
    admitted_mechanisms: tuple[str, ...]
    capability_admission_state: str
    status_request_count: int
    raw_rf_activity: str
    persistent_catalog_created: bool
    authorized_claims: tuple[str, ...]
    unauthorized_claims: tuple[str, ...]

    def strict_json(self) -> str:
        return json.dumps(
            strict_json_value(asdict(self)),
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )


def finalize_inventory_search(
    plan: G13SearchPlan,
    search_receipts: Sequence[SearchQueryReceipt],
    candidate_audits: Sequence[CandidateMechanismAudit],
    *,
    evaluated_at: datetime,
) -> G13SearchResult:
    """Close the frozen search without converting errors into absence."""

    plan.validate()
    now = _aware_utc(evaluated_at)
    searches = _validate_search_receipts(plan, search_receipts)
    audits = _validate_candidate_audits(plan, candidate_audits)
    expected_urls = select_candidate_document_urls(plan, searches)
    if tuple(item.operator_document_url for item in audits) != expected_urls:
        raise ValueError(
            "candidate audits must match the frozen round-robin URL selection exactly"
        )
    search_incomplete = any(
        item.state != SearchState.SUCCESS.value for item in searches
    )

    assessments: list[CandidateSearchAssessment] = []
    qualification_error = False
    for audit in audits:
        if audit.state == CandidateAuditState.QUALIFICATION_ERROR.value:
            qualification_error = True
            assessments.append(
                CandidateSearchAssessment(
                    audit.mechanism_id,
                    CandidateAuditState.QUALIFICATION_ERROR.value,
                    None,
                    audit.detail,
                )
            )
            continue
        if audit.inventory_receipt is None:
            raise ValueError("an evaluated candidate needs an inventory receipt")
        mechanism = evaluate_inventory_mechanism(
            G12InventoryPlan(),
            audit.inventory_receipt,
            evaluated_at=now,
        )
        assessments.append(
            CandidateSearchAssessment(
                audit.mechanism_id,
                CandidateAuditState.EVALUATED.value,
                mechanism,
                audit.detail,
            )
        )

    admitted = tuple(
        item.mechanism_id
        for item in assessments
        if item.mechanism_assessment is not None
        and item.mechanism_assessment.mechanism_admissible
    )
    if admitted:
        outcome = G13Outcome.LEGITIMATE_INVENTORY_FOUND
    elif search_incomplete or qualification_error:
        outcome = G13Outcome.INVENTORY_SEARCH_INCOMPLETE
    else:
        outcome = G13Outcome.NO_LEGITIMATE_INVENTORY_FOUND

    result = G13SearchResult(
        outcome=outcome.value,
        plan_hash=plan.plan_hash,
        evaluated_at=now.isoformat(),
        search_receipts=searches,
        candidate_assessments=tuple(assessments),
        admitted_mechanisms=admitted,
        capability_admission_state="NOT_EVALUATED",
        status_request_count=0,
        raw_rf_activity="ZERO",
        persistent_catalog_created=False,
        authorized_claims=(
            "only the four frozen query families and bounded candidate documents were evaluated",
            "a no-result claim is limited to this frozen search surface",
            "no receiver status or RF request was performed",
        ),
        unauthorized_claims=(
            "no legitimate inventory exists anywhere on the Internet",
            "a discovered directory endpoint is a qualified receiver",
            "a receiver or pair satisfies Gate G1",
            "any candidate satellite is emitting or observable",
        ),
    )
    result.strict_json()
    return result


def ordered_result_hash(urls: Sequence[str]) -> str:
    """Bind search ordering without retaining a search-engine response body."""

    return _hash_json(tuple(urls))


def select_candidate_document_urls(
    plan: G13SearchPlan,
    receipts: Sequence[SearchQueryReceipt],
) -> tuple[str, ...]:
    """Select candidates round-robin across query families before inspection."""

    plan.validate()
    searches = _validate_search_receipts(plan, receipts)
    selected: list[str] = []
    seen: set[str] = set()
    for result_index in range(plan.maximum_results_per_query):
        for receipt in searches:
            if receipt.state != SearchState.SUCCESS.value:
                continue
            if result_index >= len(receipt.candidate_document_urls):
                continue
            url = receipt.candidate_document_urls[result_index]
            if url in seen:
                continue
            seen.add(url)
            selected.append(url)
            if len(selected) == plan.maximum_candidate_mechanisms:
                return tuple(selected)
    return tuple(selected)


def mechanism_id_for_url(url: str) -> str:
    if not url.strip():
        raise ValueError("candidate URL must be non-empty")
    return f"candidate:{sha256(url.encode('utf-8')).hexdigest()[:16]}"


def _validate_search_receipts(
    plan: G13SearchPlan,
    receipts: Sequence[SearchQueryReceipt],
) -> tuple[SearchQueryReceipt, ...]:
    by_query = {item.query: item for item in receipts}
    if len(by_query) != len(receipts) or set(by_query) != set(plan.queries):
        raise ValueError("search receipts must match every frozen query exactly once")
    ordered = tuple(by_query[query] for query in plan.queries)
    for receipt in ordered:
        try:
            SearchState(receipt.state)
        except ValueError as error:
            raise ValueError(f"invalid search state: {receipt.state!r}") from error
        if not 0 <= receipt.result_count <= plan.maximum_results_per_query:
            raise ValueError("search result count exceeds the frozen bound")
        if receipt.result_count != len(receipt.candidate_document_urls):
            raise ValueError("search result count and retained URL count differ")
        if len(set(receipt.candidate_document_urls)) != receipt.result_count:
            raise ValueError("one search receipt contains duplicate URLs")
        if receipt.state == SearchState.SUCCESS.value:
            if not _is_sha256(receipt.ordered_result_set_sha256):
                raise ValueError("successful search lacks its ordered result-set hash")
            if receipt.ordered_result_set_sha256 != ordered_result_hash(
                receipt.candidate_document_urls
            ):
                raise ValueError("search result-set hash does not match its URLs")
        if receipt.raw_search_artifact_persisted:
            raise ValueError("raw search artifacts may not persist")
    return ordered


def _validate_candidate_audits(
    plan: G13SearchPlan,
    audits: Sequence[CandidateMechanismAudit],
) -> tuple[CandidateMechanismAudit, ...]:
    if len(audits) > plan.maximum_candidate_mechanisms:
        raise ValueError("candidate mechanism count exceeds the frozen bound")
    identifiers = tuple(item.mechanism_id for item in audits)
    if any(not item.strip() for item in identifiers) or len(set(identifiers)) != len(
        identifiers
    ):
        raise ValueError("candidate mechanism identifiers must be non-empty and unique")
    ordered = tuple(sorted(audits, key=lambda item: (item.discovery_rank, item.mechanism_id)))
    for expected_rank, audit in enumerate(ordered, start=1):
        if audit.discovery_rank != expected_rank:
            raise ValueError("candidate discovery ranks must be contiguous from one")
        if audit.search_query not in plan.queries:
            raise ValueError("candidate is not bound to a frozen query")
        if not audit.operator_document_url.strip():
            raise ValueError("candidate lacks an operator document URL")
        if audit.mechanism_id != mechanism_id_for_url(audit.operator_document_url):
            raise ValueError("candidate identifier is not derived from its document URL")
        if audit.operator_document_sha256 is not None and not _is_sha256(
            audit.operator_document_sha256
        ):
            raise ValueError("candidate operator document hash is invalid")
        try:
            state = CandidateAuditState(audit.state)
        except ValueError as error:
            raise ValueError(f"invalid candidate audit state: {audit.state!r}") from error
        if state is CandidateAuditState.EVALUATED:
            if audit.inventory_receipt is None:
                raise ValueError("evaluated candidate lacks an inventory receipt")
            if audit.inventory_url is None or not audit.inventory_url.strip():
                raise ValueError("evaluated candidate lacks its linked inventory URL")
            if audit.inventory_receipt.mechanism_id != audit.mechanism_id:
                raise ValueError("candidate and inventory receipt identifiers differ")
            if (
                audit.inventory_receipt.evidence_basis
                != EvidenceBasis.OBSERVED_ARTIFACT.value
            ):
                raise ValueError("Gate G1.3 accepts only observed current-session artifacts")
        elif audit.inventory_receipt is not None:
            raise ValueError("qualification errors cannot carry a physical rejection receipt")
        if audit.raw_documents_persisted:
            raise ValueError("raw candidate documents may not persist")
    return ordered


def _hash_json(value: object) -> str:
    encoded = json.dumps(
        strict_json_value(value),
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _is_sha256(value: str | None) -> bool:
    if value is None or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc)
