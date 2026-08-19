"""Gate F2.5.16: offline attribution of the frozen control sequence.

This module reads only the committed F2.5.15 receipt and the already pinned
KiwiSDR server-source archive.  It does not expose a connector or an execution
entry point.  Its narrow purpose is to distinguish a locally demonstrated
control-plan defect from an unobserved remote close cause.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile


F2516_TRANSFORM_VERSION = "gate-f2.5.16-offline-control-attribution-v1"
FROZEN_RECEIPT_SHA256 = (
    "ba77314fa10ea5ebc6fa3c29f9b4a9ebfdcf0b815d94fe77182a939b63e77619"
)
FROZEN_PREFIX_SHA256 = (
    "9dd51ec1813427db243ee12bfba6a3790e90c0f61353fa0e9b643d4180d9d04a"
)
PINNED_SERVER_ARCHIVE_SHA256 = (
    "d6a50adfce7f75133020de85635711dc6c2218e6f134d901ac13a450b57de7ea"
)
PINNED_SERVER_COMMIT = "c40ecb471dced33689e335689f8ffd35a54f47fa"
PINNED_LOCAL_CONTROL_SHA256 = (
    "147b966aa792270093bbf468bc2b391f04885f5e104486b0d3e880a90dcfa433"
)
KEEPALIVE_COMMAND = "SET keepalive"
AR_OK_COMMAND = "SET AR OK in=12000 out=44100"
KEEPALIVE_SHA256 = sha256(KEEPALIVE_COMMAND.encode("utf-8")).hexdigest()
AR_OK_SHA256 = sha256(AR_OK_COMMAND.encode("utf-8")).hexdigest()
PINNED_KEEPALIVE_GUARD = 4


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


FROZEN_RECEIPT_PATH = (
    _repository_root()
    / "experiments"
    / "live_instrument"
    / "session_receipts"
    / "gate-f2-5-15-20260817T112702.764940Z.jsonl"
)
PINNED_MANIFEST_PATH = (
    _repository_root()
    / "experiments"
    / "live_instrument"
    / "protocol_sources"
    / "gate_f2_5_6"
    / "manifest.json"
)
PINNED_SERVER_ARCHIVE_PATH = PINNED_MANIFEST_PATH.with_name(
    "kiwisdr-c40ecb471dced33689e335689f8ffd35a54f47fa.zip"
)
PINNED_LOCAL_CONTROL_PATH = (
    _repository_root()
    / "experiments"
    / "live_instrument"
    / "kiwi_gate_f2_5_13.py"
)


class ClauseState(str, Enum):
    SATISFIED = "SATISFIED"
    NOT_SATISFIED = "NOT_SATISFIED"
    NOT_EVALUATED = "NOT_EVALUATED"


class LocalPlanAssessment(str, Enum):
    FALSIFIED_BY_PINNED_CONTROL_INVARIANT = (
        "FALSIFIED_BY_PINNED_CONTROL_INVARIANT"
    )


class RemoteCauseAssessment(str, Enum):
    INCONCLUSIVE = "INCONCLUSIVE"


class PhysicalCapabilityAssessment(str, Enum):
    NOT_EVALUATED = "NOT_EVALUATED"


@dataclass(frozen=True, slots=True)
class AttributionClause:
    clause_id: str
    state: ClauseState
    observation: str


@dataclass(frozen=True, slots=True)
class BranchControlAudit:
    endpoint_identity: str
    role: str
    branch_state: str
    channel_allocated: bool
    duration_s: float
    local_command_count: int
    keepalive_count: int
    ar_ok_seen: bool
    ar_ok_command_index: int | None
    keepalive_count_before_ar_ok: int | None
    snd_frame_count: int
    close_payload_state: str


@dataclass(frozen=True, slots=True)
class PinnedServerAudit:
    archive_sha256: str
    pinned_commit: str
    keepalive_counter_increment_present: bool
    incomplete_setup_guard_present: bool
    audio_gate_present: bool
    ar_ok_setup_bit_present: bool
    cmd_snd_all_definition_retained: bool
    remote_revision_bound_by_receipt: bool


@dataclass(frozen=True, slots=True)
class F2516Assessment:
    transform_version: str
    receipt_sha256: str
    receipt_prefix_sha256: str
    local_plan_assessment: LocalPlanAssessment
    remote_close_cause: RemoteCauseAssessment
    physical_dual_snd_capability: PhysicalCapabilityAssessment
    allocated_branch_count: int
    zero_snd_branch_count: int
    branches: tuple[BranchControlAudit, ...]
    pinned_server: PinnedServerAudit
    clauses: tuple[AttributionClause, ...]
    authorised_claims: tuple[str, ...]
    unauthorised_claims: tuple[str, ...]
    raw_rf_persistence: str


def _strict_documents(path: Path) -> tuple[dict[str, object], ...]:
    def reject_constant(value: str) -> object:
        raise ValueError(f"non-finite JSON constant: {value}")

    return tuple(
        json.loads(line, parse_constant=reject_constant)
        for line in path.read_text(encoding="utf-8").splitlines()
    )


def _canonical_source_sha256(path: Path) -> str:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    return sha256(text.encode("utf-8")).hexdigest()


def _duration_s(started_at: str, completed_at: str) -> float:
    started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    completed = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
    return (completed - started).total_seconds()


def _receipt_prefix_sha256(path: Path) -> str:
    lines = path.read_bytes().splitlines(keepends=True)
    if len(lines) < 2:
        raise ValueError("frozen receipt has no terminal line")
    return sha256(b"".join(lines[:-1])).hexdigest()


def _branch_audits(documents: tuple[dict[str, object], ...]) -> tuple[BranchControlAudit, ...]:
    pairs = tuple(
        document["payload"]
        for document in documents
        if document["event"] == "gate_f2_5_15_candidate_pair"
    )
    audits: list[BranchControlAudit] = []
    for pair in pairs:
        assert isinstance(pair, dict)
        for branch in pair["branch_receipts"]:
            command_hashes = tuple(branch["local_command_hashes"])
            ar_index = (
                command_hashes.index(AR_OK_SHA256)
                if AR_OK_SHA256 in command_hashes
                else None
            )
            semantic = tuple(branch["semantic_frame_receipts"])
            audits.append(
                BranchControlAudit(
                    str(branch["endpoint_identity"]),
                    str(branch["role"]),
                    str(branch["state"]),
                    branch["observed_channel_id"] is not None,
                    _duration_s(str(branch["started_at"]), str(branch["completed_at"])),
                    len(command_hashes),
                    command_hashes.count(KEEPALIVE_SHA256),
                    ar_index is not None,
                    ar_index,
                    (
                        command_hashes[:ar_index].count(KEEPALIVE_SHA256)
                        if ar_index is not None
                        else None
                    ),
                    sum(frame["frame_class"] == "SND" for frame in semantic),
                    str(branch["close_payload_state"]),
                )
            )
    return tuple(audits)


def _pinned_server_audit(receipt_documents: tuple[dict[str, object], ...]) -> PinnedServerAudit:
    archive_hash = sha256(PINNED_SERVER_ARCHIVE_PATH.read_bytes()).hexdigest()
    if archive_hash != PINNED_SERVER_ARCHIVE_SHA256:
        raise ValueError("pinned KiwiSDR source archive hash changed")

    manifest = json.loads(PINNED_MANIFEST_PATH.read_text(encoding="utf-8"))
    server = manifest["repositories"][0]
    if server["commit"] != PINNED_SERVER_COMMIT:
        raise ValueError("pinned KiwiSDR commit changed")

    with ZipFile(PINNED_SERVER_ARCHIVE_PATH) as archive:
        members = set(archive.namelist())
        rx_cmd = archive.read("rx/rx_cmd.cpp").decode("utf-8")
        rx_sound = archive.read("rx/rx_sound.cpp").decode("utf-8")
        rx_sound_cmd = archive.read("rx/rx_sound_cmd.cpp").decode("utf-8")

    receipt_text = json.dumps(receipt_documents, sort_keys=True)
    return PinnedServerAudit(
        archive_hash,
        PINNED_SERVER_COMMIT,
        "conn->keepalive_count++;" in rx_cmd,
        (
            "conn->keepalive_count > 4" in rx_sound
            and "s->cmd_recv != CMD_SND_ALL" in rx_sound
            and "connection_hang" in rx_sound
        ),
        "if (s->cmd_recv != CMD_SND_ALL)" in rx_sound,
        "s->cmd_recv |= CMD_AR_OK" in rx_sound_cmd,
        "rx/rx_sound_cmd.h" in members,
        PINNED_SERVER_COMMIT in receipt_text,
    )


def audit_frozen_outcome() -> F2516Assessment:
    """Return the bounded offline attribution for the single frozen outcome."""

    receipt_hash = sha256(FROZEN_RECEIPT_PATH.read_bytes()).hexdigest()
    prefix_hash = _receipt_prefix_sha256(FROZEN_RECEIPT_PATH)
    if receipt_hash != FROZEN_RECEIPT_SHA256:
        raise ValueError("frozen F2.5.15 receipt hash changed")
    if prefix_hash != FROZEN_PREFIX_SHA256:
        raise ValueError("frozen F2.5.15 prefix hash changed")
    if _canonical_source_sha256(PINNED_LOCAL_CONTROL_PATH) != PINNED_LOCAL_CONTROL_SHA256:
        raise ValueError("frozen local SND control source changed")

    documents = _strict_documents(FROZEN_RECEIPT_PATH)
    branches = _branch_audits(documents)
    allocated = tuple(branch for branch in branches if branch.channel_allocated)
    zero_snd = tuple(branch for branch in allocated if branch.snd_frame_count == 0)
    server = _pinned_server_audit(documents)

    if len(branches) != 12 or len(allocated) != 8 or len(zero_snd) != 8:
        raise ValueError("frozen branch population changed")
    if not all(
        branch.ar_ok_seen
        and branch.keepalive_count_before_ar_ok is not None
        and branch.keepalive_count_before_ar_ok > PINNED_KEEPALIVE_GUARD
        for branch in allocated
    ):
        raise ValueError("frozen pre-AR keepalive exposure changed")
    if not (
        server.keepalive_counter_increment_present
        and server.incomplete_setup_guard_present
        and server.audio_gate_present
        and server.ar_ok_setup_bit_present
    ):
        raise ValueError("required pinned server control evidence is absent")

    clauses = (
        AttributionClause(
            "FROZEN_RECEIPT_INTEGRITY",
            ClauseState.SATISFIED,
            "The committed JSONL and its terminal prefix match their frozen SHA-256 values.",
        ),
        AttributionClause(
            "DIRECT_SND_BRANCH_ATTEMPTS",
            ClauseState.SATISFIED,
            "Twelve branch attempts are present; eight reached channel allocation.",
        ),
        AttributionClause(
            "ZERO_SEMANTIC_SND_FRAMES_AFTER_ALLOCATION",
            ClauseState.SATISFIED,
            "All eight allocated branches record zero semantic SND frames.",
        ),
        AttributionClause(
            "LOCAL_COMMAND_ORDER_RECONSTRUCTABLE",
            ClauseState.SATISFIED,
            "Command hashes preserve local emission order without retaining credentials.",
        ),
        AttributionClause(
            "PRE_AR_KEEPALIVE_EXCEEDS_PINNED_GUARD",
            ClauseState.SATISFIED,
            "Every allocated branch emitted 15 or 16 keepalives before AR OK; the pinned guard is greater than four.",
        ),
        AttributionClause(
            "PINNED_SERVER_INCOMPLETE_SETUP_REMOVAL_PATH",
            ClauseState.SATISFIED,
            "The retained server source increments keepalive_count and contains the incomplete CMD_SND_ALL removal predicate.",
        ),
        AttributionClause(
            "CMD_SND_ALL_DEFINITION_RETAINED",
            ClauseState.NOT_SATISFIED,
            "rx/rx_sound_cmd.h is absent, so the exact required-bit definition is not retained.",
        ),
        AttributionClause(
            "REMOTE_SERVER_REVISION_BOUND",
            ClauseState.NOT_EVALUATED,
            "The receipt contains no remote build identity tied to the pinned source commit.",
        ),
        AttributionClause(
            "REMOTE_COMMAND_RECEIPT_ORDER_OBSERVED",
            ClauseState.NOT_EVALUATED,
            "Local send hashes do not prove which commands the remote server received or in what state.",
        ),
        AttributionClause(
            "REMOTE_CMD_RECV_AT_CLOSE_OBSERVED",
            ClauseState.NOT_EVALUATED,
            "The remote CMD_SND_ALL bitmask state is not exposed by the receipt.",
        ),
        AttributionClause(
            "PEER_CLOSE_REASON_OBSERVED",
            ClauseState.NOT_EVALUATED,
            "All allocated branches ended with an empty close and no peer status code.",
        ),
        AttributionClause(
            "PHYSICAL_DUAL_SND_CAPABILITY",
            ClauseState.NOT_EVALUATED,
            "No SND frame crossed the admission boundary, so physical multichannel capability was not tested.",
        ),
    )

    return F2516Assessment(
        F2516_TRANSFORM_VERSION,
        receipt_hash,
        prefix_hash,
        LocalPlanAssessment.FALSIFIED_BY_PINNED_CONTROL_INVARIANT,
        RemoteCauseAssessment.INCONCLUSIVE,
        PhysicalCapabilityAssessment.NOT_EVALUATED,
        len(allocated),
        len(zero_snd),
        branches,
        server,
        clauses,
        (
            "The frozen client emitted more than four keepalives before AR OK on every allocated branch.",
            "The pinned server model treats keepalive count as control state and exposes an incomplete-setup removal path.",
            "The F2.5.15 local control plan is unsafe under the pinned server semantics.",
            "The live receipt contains zero semantic SND frames and cannot evaluate dual-SND physical capability.",
        ),
        (
            "The pinned incomplete-setup guard caused the remote closes.",
            "The live endpoints ran the pinned server revision.",
            "AR OK was the only missing bit of CMD_SND_ALL at each close.",
            "The endpoints lack multichannel SND capability.",
            "Any physical or RF hypothesis was tested.",
        ),
        "ZERO",
    )
