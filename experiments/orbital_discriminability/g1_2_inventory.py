"""Gate G1.2: offline qualification of an inventory *mechanism*.

The unit assessed here is deliberately not a receiver and not a persistent
catalog.  It is the bounded route by which a current-session endpoint set
could be materialized before status-only qualification.  This module performs
no I/O and cannot authorize receiver or RF requests.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from hashlib import sha256
import json
from math import isfinite
from numbers import Integral
from typing import Mapping, Sequence

from experiments.live_instrument.models import strict_json_value


class InventoryMechanismKind(str, Enum):
    INTERACTIVE_DIRECTORY = "INTERACTIVE_DIRECTORY"
    REMEMBERED_ENDPOINT_SET = "REMEMBERED_ENDPOINT_SET"
    OPERATOR_MANIFEST = "OPERATOR_MANIFEST"
    DNS_SERVICE_DISCOVERY = "DNS_SERVICE_DISCOVERY"


class EvidenceBasis(str, Enum):
    OBSERVED_ARTIFACT = "OBSERVED_ARTIFACT"
    REMEMBERED_STATE = "REMEMBERED_STATE"
    CONTRACT_FIXTURE = "CONTRACT_FIXTURE"


class AuthorityBinding(str, Enum):
    NONE = "NONE"
    HTTPS_OPERATOR_ORIGIN = "HTTPS_OPERATOR_ORIGIN"
    VERIFIED_SIGNED_MANIFEST = "VERIFIED_SIGNED_MANIFEST"
    DNSSEC_OPERATOR_DOMAIN = "DNSSEC_OPERATOR_DOMAIN"


class ClauseState(str, Enum):
    SATISFIED = "SATISFIED"
    UNSATISFIED = "UNSATISFIED"


class G12Outcome(str, Enum):
    NO_LEGITIMATE_INVENTORY_MECHANISM = "NO_LEGITIMATE_INVENTORY_MECHANISM"
    INVENTORY_MECHANISM_ADMISSIBLE = "INVENTORY_MECHANISM_ADMISSIBLE"


REQUIRED_ENDPOINT_FIELDS = ("endpoint_id", "status_route")


@dataclass(frozen=True, slots=True)
class G12InventoryPlan:
    """Frozen limits for comparing inventory receipt forms offline."""

    qualification_budget_s: float = 120.0
    maximum_snapshot_ttl_s: float = 600.0
    maximum_endpoints: int = 20
    required_endpoint_fields: tuple[str, ...] = REQUIRED_ENDPOINT_FIELDS
    retry_count: int = 0

    def validate(self) -> None:
        if not (
            isfinite(self.qualification_budget_s)
            and 0.0 < self.qualification_budget_s <= 120.0
        ):
            raise ValueError("Gate G1.2 qualification budget must be in (0, 120] s")
        if not (
            isfinite(self.maximum_snapshot_ttl_s)
            and self.qualification_budget_s <= self.maximum_snapshot_ttl_s <= 600.0
        ):
            raise ValueError("Gate G1.2 inventory TTL must be in [budget, 600] s")
        if not 1 <= self.maximum_endpoints <= 20:
            raise ValueError("Gate G1.2 allows at most twenty endpoint descriptions")
        if self.required_endpoint_fields != REQUIRED_ENDPOINT_FIELDS:
            raise ValueError("Gate G1.2 endpoint binding fields are frozen")
        if self.retry_count != 0:
            raise ValueError("Gate G1.2 is offline and freezes zero retry")

    @property
    def plan_hash(self) -> str:
        self.validate()
        return _hash_json(asdict(self))


@dataclass(frozen=True, slots=True)
class InventoryMechanismReceipt:
    mechanism_id: str
    mechanism_kind: str
    evidence_basis: str
    authority_binding: str
    authority_identity: str | None
    automation_permission_reference: str | None
    interaction_required: bool
    browser_state_or_custom_auth_required: bool
    schema_name: str | None
    schema_version: str | None
    artifact_sha256: str | None
    artifact_byte_count: int
    hashed_before_parsing: bool
    observed_at: datetime | None
    ttl_s: float | None
    declared_coverage_scope: str | None
    complete_for_declared_scope: bool
    endpoint_count: int
    endpoint_fields: tuple[str, ...]
    endpoint_set_sha256: str | None
    deterministic_extraction: bool
    raw_artifact_persisted: bool
    rf_activity: str = "ZERO"


@dataclass(frozen=True, slots=True)
class InventoryClause:
    clause_id: str
    state: str
    observed: str
    required: str


@dataclass(frozen=True, slots=True)
class InventoryMechanismAssessment:
    mechanism_id: str
    mechanism_kind: str
    evidence_basis: str
    receipt_hash: str
    mechanism_admissible: bool
    clauses: tuple[InventoryClause, ...]
    claim_scope: str


@dataclass(frozen=True, slots=True)
class G12InventoryResult:
    outcome: str
    plan_hash: str
    evaluated_at: str
    assessments: tuple[InventoryMechanismAssessment, ...]
    observed_admissible_mechanisms: tuple[str, ...]
    admissible_contract_fixtures: tuple[str, ...]
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


def evaluate_inventory_mechanism(
    plan: G12InventoryPlan,
    receipt: InventoryMechanismReceipt,
    *,
    evaluated_at: datetime,
) -> InventoryMechanismAssessment:
    """Assess one already-described route without contacting it."""

    plan.validate()
    now = _aware_utc(evaluated_at)
    if not receipt.mechanism_id.strip():
        raise ValueError("mechanism_id must be non-empty")
    kind = _enum_value(InventoryMechanismKind, receipt.mechanism_kind)
    basis = _enum_value(EvidenceBasis, receipt.evidence_basis)
    authority = _enum_value(AuthorityBinding, receipt.authority_binding)

    receipt_basis = basis is not EvidenceBasis.REMEMBERED_STATE
    authority_bound = (
        authority is not AuthorityBinding.NONE
        and _nonempty(receipt.authority_identity)
    )
    automation_intent = _nonempty(receipt.automation_permission_reference)
    noninteractive = not receipt.interaction_required and not (
        receipt.browser_state_or_custom_auth_required
    )
    artifact_integrity = (
        _is_sha256(receipt.artifact_sha256)
        and _nonnegative_int(receipt.artifact_byte_count)
        and receipt.artifact_byte_count > 0
        and receipt.hashed_before_parsing
    )
    temporal_validity = _temporally_valid(plan, receipt, now)
    schema = _nonempty(receipt.schema_name) and _nonempty(receipt.schema_version)
    coverage = (
        _nonempty(receipt.declared_coverage_scope)
        and receipt.complete_for_declared_scope
    )
    endpoint_set = (
        _nonnegative_int(receipt.endpoint_count)
        and receipt.endpoint_count <= plan.maximum_endpoints
        and set(plan.required_endpoint_fields).issubset(receipt.endpoint_fields)
        and _is_sha256(receipt.endpoint_set_sha256)
        and receipt.deterministic_extraction
    )
    ephemeral = not receipt.raw_artifact_persisted
    no_rf = receipt.rf_activity == "ZERO"

    clauses = (
        _clause(
            "current_artifact_basis",
            receipt_basis,
            basis.value,
            "observed artifact or explicit contract fixture; remembered state is excluded",
        ),
        _clause(
            "authority_binding",
            authority_bound,
            f"binding={authority.value}; identity={receipt.authority_identity}",
            "operator-bound HTTPS/signature or DNSSEC authority",
        ),
        _clause(
            "automation_intent",
            automation_intent,
            str(receipt.automation_permission_reference),
            "documented public machine-readable automation permission",
        ),
        _clause(
            "noninteractive_route",
            noninteractive,
            (
                f"interaction={receipt.interaction_required}; "
                f"browser_or_custom_auth={receipt.browser_state_or_custom_auth_required}"
            ),
            "no user gesture, browser state, CAPTCHA or replayed custom authorization",
        ),
        _clause(
            "artifact_integrity",
            artifact_integrity,
            (
                f"sha256={receipt.artifact_sha256}; bytes={receipt.artifact_byte_count}; "
                f"hash_before_parse={receipt.hashed_before_parsing}"
            ),
            "bounded non-empty artifact hashed before parsing",
        ),
        _clause(
            "temporal_validity",
            temporal_validity,
            _temporal_text(receipt, now),
            (
                f"positive TTL <= {plan.maximum_snapshot_ttl_s:.3f} s and snapshot "
                f"valid through {plan.qualification_budget_s:.3f} s qualification budget"
            ),
        ),
        _clause(
            "machine_readable_schema",
            schema,
            f"name={receipt.schema_name}; version={receipt.schema_version}",
            "named and versioned bounded schema",
        ),
        _clause(
            "declared_coverage",
            coverage,
            (
                f"scope={receipt.declared_coverage_scope}; "
                f"complete={receipt.complete_for_declared_scope}"
            ),
            "selection scope declared and snapshot complete for that scope",
        ),
        _clause(
            "deterministic_endpoint_binding",
            endpoint_set,
            (
                f"count={receipt.endpoint_count}; fields={receipt.endpoint_fields}; "
                f"set_sha256={receipt.endpoint_set_sha256}; "
                f"deterministic={receipt.deterministic_extraction}"
            ),
            (
                f"0..{plan.maximum_endpoints} endpoints, required fields, canonical "
                "set hash and deterministic extraction"
            ),
        ),
        _clause(
            "ephemeral_artifact",
            ephemeral,
            f"raw_artifact_persisted={receipt.raw_artifact_persisted}",
            "hash/receipt may persist; raw inventory artifact may not",
        ),
        _clause(
            "descriptive_only",
            no_rf,
            f"rf_activity={receipt.rf_activity}",
            "zero RF, SND, IQ, waterfall, audio or spectrum activity",
        ),
    )
    admissible = all(item.state == ClauseState.SATISFIED.value for item in clauses)
    if admissible and basis is EvidenceBasis.OBSERVED_ARTIFACT:
        claim_scope = (
            "this observed inventory mechanism may materialize only its declared "
            "endpoint scope for later status-only qualification"
        )
    elif admissible:
        claim_scope = (
            "this fixture demonstrates an admissible receipt form only; it does not "
            "assert that the route or endpoints exist"
        )
    else:
        claim_scope = (
            "the mechanism cannot supply a selection-neutral current-session endpoint "
            "set; no receiver absence follows"
        )
    assessment = InventoryMechanismAssessment(
        mechanism_id=receipt.mechanism_id,
        mechanism_kind=kind.value,
        evidence_basis=basis.value,
        receipt_hash=_hash_json(asdict(receipt)),
        mechanism_admissible=admissible,
        clauses=clauses,
        claim_scope=claim_scope,
    )
    strict_json_value(asdict(assessment))
    return assessment


def compare_inventory_mechanisms(
    plan: G12InventoryPlan,
    receipts: Sequence[InventoryMechanismReceipt],
    *,
    evaluated_at: datetime,
) -> G12InventoryResult:
    """Compare concurrent receipt forms without selecting a receiver source."""

    plan.validate()
    now = _aware_utc(evaluated_at)
    ordered = tuple(sorted(receipts, key=lambda item: item.mechanism_id))
    if not ordered:
        raise ValueError("Gate G1.2 comparison requires at least one receipt form")
    identifiers = tuple(item.mechanism_id for item in ordered)
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("mechanism identifiers must be unique")
    assessments = tuple(
        evaluate_inventory_mechanism(plan, receipt, evaluated_at=now)
        for receipt in ordered
    )
    observed = tuple(
        item.mechanism_id
        for item in assessments
        if item.mechanism_admissible
        and item.evidence_basis == EvidenceBasis.OBSERVED_ARTIFACT.value
    )
    fixtures = tuple(
        item.mechanism_id
        for item in assessments
        if item.mechanism_admissible
        and item.evidence_basis == EvidenceBasis.CONTRACT_FIXTURE.value
    )
    outcome = (
        G12Outcome.INVENTORY_MECHANISM_ADMISSIBLE
        if observed
        else G12Outcome.NO_LEGITIMATE_INVENTORY_MECHANISM
    )
    result = G12InventoryResult(
        outcome=outcome.value,
        plan_hash=plan.plan_hash,
        evaluated_at=now.isoformat(),
        assessments=assessments,
        observed_admissible_mechanisms=observed,
        admissible_contract_fixtures=fixtures,
        capability_admission_state="NOT_EVALUATED",
        status_request_count=0,
        raw_rf_activity="ZERO",
        persistent_catalog_created=False,
        authorized_claims=(
            "only the supplied inventory receipt forms were evaluated under the frozen clauses",
            (
                "admissible contract fixtures demonstrate receipt shape only and do not "
                "materialize live sources"
            ),
            "no receiver status or RF activity was performed",
        ),
        unauthorized_claims=(
            "either contract-fixture route exists on the public Internet",
            "any remembered endpoint is currently available or selection-neutral",
            "a receiver or receiver pair satisfies Gate G1",
            "no suitable Internet RF capability exists",
        ),
    )
    result.strict_json()
    return result


def candidate_from_g11_receipt(payload: Mapping[str, object]) -> InventoryMechanismReceipt:
    """Describe the frozen G1.1 directory artifact without re-reading the network."""

    fetches = payload.get("fetch_receipts")
    if not isinstance(fetches, list) or not fetches:
        raise ValueError("G1.1 receipt has no fetch ledger")
    directory = fetches[-1]
    if not isinstance(directory, Mapping):
        raise ValueError("G1.1 directory fetch receipt is malformed")
    if directory.get("requested_url") != "http://rx.kiwisdr.com":
        raise ValueError("G1.1 fetch ledger does not end at the frozen directory route")
    observed_at = _parse_datetime(payload.get("evaluated_at"))
    interaction = directory.get("state") == "INTERACTION_REQUIRED"
    return InventoryMechanismReceipt(
        mechanism_id="g1.1:kiwi-public-directory",
        mechanism_kind=InventoryMechanismKind.INTERACTIVE_DIRECTORY.value,
        evidence_basis=EvidenceBasis.OBSERVED_ARTIFACT.value,
        authority_binding=AuthorityBinding.NONE.value,
        authority_identity=None,
        automation_permission_reference=None,
        interaction_required=interaction,
        browser_state_or_custom_auth_required=interaction,
        schema_name=None,
        schema_version=None,
        artifact_sha256=_optional_string(directory.get("body_sha256")),
        artifact_byte_count=_safe_int(directory.get("byte_count")),
        hashed_before_parsing=True,
        observed_at=observed_at,
        ttl_s=None,
        declared_coverage_scope=None,
        complete_for_declared_scope=False,
        endpoint_count=_safe_int(payload.get("endpoint_candidate_count")),
        endpoint_fields=(),
        endpoint_set_sha256=None,
        deterministic_extraction=False,
        raw_artifact_persisted=False,
        rf_activity=str(payload.get("raw_rf_activity") or "UNKNOWN"),
    )


def remembered_endpoint_fixture(*, endpoint_count: int = 3) -> InventoryMechanismReceipt:
    """Represent, but never legitimize, endpoint memory from earlier gates."""

    return InventoryMechanismReceipt(
        mechanism_id="remembered:f2-endpoints",
        mechanism_kind=InventoryMechanismKind.REMEMBERED_ENDPOINT_SET.value,
        evidence_basis=EvidenceBasis.REMEMBERED_STATE.value,
        authority_binding=AuthorityBinding.NONE.value,
        authority_identity=None,
        automation_permission_reference=None,
        interaction_required=False,
        browser_state_or_custom_auth_required=False,
        schema_name=None,
        schema_version=None,
        artifact_sha256=None,
        artifact_byte_count=0,
        hashed_before_parsing=False,
        observed_at=None,
        ttl_s=None,
        declared_coverage_scope=None,
        complete_for_declared_scope=False,
        endpoint_count=endpoint_count,
        endpoint_fields=REQUIRED_ENDPOINT_FIELDS,
        endpoint_set_sha256=None,
        deterministic_extraction=True,
        raw_artifact_persisted=False,
    )


def operator_manifest_contract_fixture(
    *,
    observed_at: datetime,
) -> InventoryMechanismReceipt:
    """A non-live fixture for an operator-published manifest receipt."""

    artifact = b'{"schema":"rf-capability-inventory/v1","receivers":["a","b"]}'
    return InventoryMechanismReceipt(
        mechanism_id="fixture:operator-manifest",
        mechanism_kind=InventoryMechanismKind.OPERATOR_MANIFEST.value,
        evidence_basis=EvidenceBasis.CONTRACT_FIXTURE.value,
        authority_binding=AuthorityBinding.HTTPS_OPERATOR_ORIGIN.value,
        authority_identity="https://operator.invalid/.well-known/rf-inventory.json",
        automation_permission_reference="https://operator.invalid/automation-policy",
        interaction_required=False,
        browser_state_or_custom_auth_required=False,
        schema_name="rf-capability-inventory",
        schema_version="1",
        artifact_sha256=sha256(artifact).hexdigest(),
        artifact_byte_count=len(artifact),
        hashed_before_parsing=True,
        observed_at=_aware_utc(observed_at),
        ttl_s=300.0,
        declared_coverage_scope="all public receivers operated by operator.invalid",
        complete_for_declared_scope=True,
        endpoint_count=2,
        endpoint_fields=REQUIRED_ENDPOINT_FIELDS,
        endpoint_set_sha256=_endpoint_set_hash(("a", "b")),
        deterministic_extraction=True,
        raw_artifact_persisted=False,
    )


def dns_service_contract_fixture(
    *,
    observed_at: datetime,
) -> InventoryMechanismReceipt:
    """A non-live fixture for an authoritative DNS service receipt."""

    answer = b"_rf._tcp.operator.invalid SRV 0 0 8073 a.operator.invalid"
    return InventoryMechanismReceipt(
        mechanism_id="fixture:dnssec-service-discovery",
        mechanism_kind=InventoryMechanismKind.DNS_SERVICE_DISCOVERY.value,
        evidence_basis=EvidenceBasis.CONTRACT_FIXTURE.value,
        authority_binding=AuthorityBinding.DNSSEC_OPERATOR_DOMAIN.value,
        authority_identity="operator.invalid DNSSEC chain",
        automation_permission_reference="_rf-inventory-policy.operator.invalid TXT api=v1",
        interaction_required=False,
        browser_state_or_custom_auth_required=False,
        schema_name="dns-sd-srv-txt",
        schema_version="1",
        artifact_sha256=sha256(answer).hexdigest(),
        artifact_byte_count=len(answer),
        hashed_before_parsing=True,
        observed_at=_aware_utc(observed_at),
        ttl_s=180.0,
        declared_coverage_scope="public RF services under operator.invalid",
        complete_for_declared_scope=True,
        endpoint_count=1,
        endpoint_fields=REQUIRED_ENDPOINT_FIELDS,
        endpoint_set_sha256=_endpoint_set_hash(("a.operator.invalid:8073",)),
        deterministic_extraction=True,
        raw_artifact_persisted=False,
    )


def _temporally_valid(
    plan: G12InventoryPlan,
    receipt: InventoryMechanismReceipt,
    now: datetime,
) -> bool:
    if receipt.observed_at is None or receipt.ttl_s is None:
        return False
    try:
        observed = _aware_utc(receipt.observed_at)
        ttl = float(receipt.ttl_s)
    except (TypeError, ValueError):
        return False
    if not isfinite(ttl) or not 0.0 < ttl <= plan.maximum_snapshot_ttl_s:
        return False
    if observed > now:
        return False
    return observed + timedelta(seconds=ttl) >= now + timedelta(
        seconds=plan.qualification_budget_s
    )


def _temporal_text(receipt: InventoryMechanismReceipt, now: datetime) -> str:
    return f"observed_at={receipt.observed_at}; ttl_s={receipt.ttl_s}; evaluated_at={now.isoformat()}"


def _clause(clause_id: str, satisfied: bool, observed: str, required: str) -> InventoryClause:
    return InventoryClause(
        clause_id=clause_id,
        state=(ClauseState.SATISFIED if satisfied else ClauseState.UNSATISFIED).value,
        observed=observed,
        required=required,
    )


def _endpoint_set_hash(endpoint_ids: Sequence[str]) -> str:
    return _hash_json(tuple(sorted(endpoint_ids)))


def _hash_json(value: object) -> str:
    encoded = json.dumps(
        strict_json_value(value),
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _enum_value(enum_type: type[Enum], value: str) -> Enum:
    try:
        return enum_type(value)
    except ValueError as error:
        raise ValueError(f"invalid {enum_type.__name__}: {value!r}") from error


def _is_sha256(value: str | None) -> bool:
    if value is None or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _nonempty(value: str | None) -> bool:
    return bool(value and value.strip())


def _nonnegative_int(value: object) -> bool:
    return isinstance(value, Integral) and not isinstance(value, bool) and value >= 0


def _parse_datetime(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return _aware_utc(parsed)


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _safe_int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc)
