"""Gate G1.3.1: offline one-query-per-call search transport contract."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Sequence
from urllib.parse import urlsplit

from experiments.live_instrument.models import strict_json_value

from .g1_3_search import (
    FROZEN_QUERIES,
    G13SearchPlan,
    SearchQueryReceipt,
    SearchState,
    ordered_result_hash,
)


PARENT_PLAN_HASH = G13SearchPlan().plan_hash


class TransportOutcome(str, Enum):
    SEARCH_TRANSPORT_FROZEN = "SEARCH_TRANSPORT_FROZEN"


@dataclass(frozen=True, slots=True)
class G131TransportPlan:
    parent_plan_hash: str = PARENT_PLAN_HASH
    queries: tuple[str, ...] = FROZEN_QUERIES
    invocation_mode: str = "ONE_QUERY_PER_CALL"
    invocation_count: int = 4
    maximum_results_per_invocation: int = 5
    retain_provider_order: bool = True
    require_distinct_invocation_ids: bool = True
    retry_count: int = 0
    result_page_requests_allowed: bool = False
    status_requests_allowed: bool = False
    rf_requests_allowed: bool = False

    def validate(self) -> None:
        if self.parent_plan_hash != PARENT_PLAN_HASH:
            raise ValueError("Gate G1.3.1 must bind the frozen G1.3 plan")
        if self.queries != FROZEN_QUERIES:
            raise ValueError("Gate G1.3.1 query set and order are frozen")
        if self.invocation_mode != "ONE_QUERY_PER_CALL":
            raise ValueError("Gate G1.3.1 forbids bundled search calls")
        if self.invocation_count != len(FROZEN_QUERIES):
            raise ValueError("Gate G1.3.1 requires exactly four invocations")
        if self.maximum_results_per_invocation != 5:
            raise ValueError("Gate G1.3.1 freezes five ordered URLs per invocation")
        if not self.retain_provider_order or not self.require_distinct_invocation_ids:
            raise ValueError("provider order and invocation identity must be preserved")
        if self.retry_count != 0:
            raise ValueError("Gate G1.3.1 freezes zero retry")
        if (
            self.result_page_requests_allowed
            or self.status_requests_allowed
            or self.rf_requests_allowed
        ):
            raise ValueError("transport qualification cannot open pages, status or RF")

    @property
    def plan_hash(self) -> str:
        self.validate()
        return _hash_json(asdict(self))


@dataclass(frozen=True, slots=True)
class IndependentQueryResponse:
    call_index: int
    invocation_id: str
    queries_in_call: tuple[str, ...]
    state: str
    ordered_result_urls: tuple[str, ...]
    detail: str
    raw_response_persisted: bool = False


@dataclass(frozen=True, slots=True)
class TransportPlanReceipt:
    outcome: str
    plan_hash: str
    parent_plan_hash: str
    invocation_mode: str
    invocation_count: int
    retry_count: int
    result_page_requests: int
    status_requests: int
    raw_rf_activity: str
    persistent_catalog_created: bool
    statement: str
    authorized_claims: tuple[str, ...]
    unauthorized_claims: tuple[str, ...]

    def strict_json(self) -> str:
        return json.dumps(
            strict_json_value(asdict(self)),
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )


def freeze_transport(plan: G131TransportPlan) -> TransportPlanReceipt:
    """Describe the offline transport contract without executing it."""

    plan.validate()
    receipt = TransportPlanReceipt(
        outcome=TransportOutcome.SEARCH_TRANSPORT_FROZEN.value,
        plan_hash=plan.plan_hash,
        parent_plan_hash=plan.parent_plan_hash,
        invocation_mode=plan.invocation_mode,
        invocation_count=plan.invocation_count,
        retry_count=plan.retry_count,
        result_page_requests=0,
        status_requests=0,
        raw_rf_activity="ZERO",
        persistent_catalog_created=False,
        statement=(
            "each frozen query must execute in its own invocation and materialize "
            "one independently hashable ordered URL list"
        ),
        authorized_claims=(
            "the transport shape needed by the consumed G1.3 selector is frozen",
            "synthetic responses can materialize independent per-query receipts",
            "no search or result-page request was executed by Gate G1.3.1",
        ),
        unauthorized_claims=(
            "the transport has succeeded against a live search provider",
            "an inventory mechanism or receiver has been discovered",
            "Gate G1 capability admission has been entered",
        ),
    )
    receipt.strict_json()
    return receipt


def materialize_query_receipts(
    plan: G131TransportPlan,
    responses: Sequence[IndependentQueryResponse],
) -> tuple[SearchQueryReceipt, ...]:
    """Convert four independent responses into the frozen G1.3 receipt shape."""

    plan.validate()
    if len(responses) != plan.invocation_count:
        raise ValueError("exactly four independent query responses are required")
    ordered = tuple(sorted(responses, key=lambda item: item.call_index))
    if tuple(item.call_index for item in ordered) != tuple(
        range(1, plan.invocation_count + 1)
    ):
        raise ValueError("query call indexes must be contiguous from one")
    invocation_ids = tuple(item.invocation_id for item in ordered)
    if any(not item.strip() for item in invocation_ids):
        raise ValueError("every query call needs a non-empty invocation identity")
    if len(set(invocation_ids)) != len(invocation_ids):
        raise ValueError("query calls must have distinct invocation identities")

    receipts: list[SearchQueryReceipt] = []
    for response, expected_query in zip(ordered, plan.queries, strict=True):
        if response.queries_in_call != (expected_query,):
            raise ValueError("each invocation must contain exactly its one frozen query")
        try:
            state = SearchState(response.state)
        except ValueError as error:
            raise ValueError(f"invalid search response state: {response.state!r}") from error
        if response.raw_response_persisted:
            raise ValueError("raw search responses may not persist")
        urls = response.ordered_result_urls
        if len(urls) > plan.maximum_results_per_invocation:
            raise ValueError("ordered URL count exceeds the frozen per-call bound")
        if len(set(urls)) != len(urls):
            raise ValueError("one query response contains duplicate URLs")
        if state is SearchState.SEARCH_ERROR and urls:
            raise ValueError("a failed query call cannot expose a stable ordered URL set")
        if state is SearchState.SUCCESS:
            for url in urls:
                _validate_result_url(url)
        receipts.append(
            SearchQueryReceipt(
                query=expected_query,
                state=state.value,
                result_count=len(urls),
                ordered_result_set_sha256=(
                    ordered_result_hash(urls)
                    if state is SearchState.SUCCESS
                    else None
                ),
                candidate_document_urls=urls,
                detail=response.detail,
                raw_search_artifact_persisted=False,
            )
        )
    return tuple(receipts)


def _validate_result_url(url: str) -> None:
    parsed = urlsplit(url)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise ValueError("search result URL must be a public HTTP(S) document URL")


def _hash_json(value: object) -> str:
    encoded = json.dumps(
        strict_json_value(value),
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()
