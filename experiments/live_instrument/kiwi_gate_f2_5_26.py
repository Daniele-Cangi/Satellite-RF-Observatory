"""Gate F2.5.26: offline temporal failure attribution.

This module audits only the frozen Gate F2.5.25 JSONL artifact and the pinned
KiwiSDR server source already retained in the repository.  It has no connector,
capture surface, threshold override, or authority to reinterpret the live
outcome.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any
from zipfile import ZipFile


TRANSFORM_VERSION = "gate-f2.5.26-offline-temporal-failure-attribution-v1"
FROZEN_OUTCOME = "QUALIFICATION_INCOMPLETE"
FROZEN_MAXIMUM_GPS_SOLUTION_AGE_S = 30
RAW_RF_PERSISTENCE = "ZERO"

FROZEN_RECEIPT_NAME = "gate-f2-5-25-20260818T194244.943090Z.jsonl"
FROZEN_RECEIPT_SHA256 = (
    "921deca68780b6546d19d4f8be2cb3cbb0ed5c9710d333f5dd24bf5d799b7380"
)
FROZEN_RECEIPT_PREFIX_SHA256 = (
    "22dede9a078858af115eb2ba042d4bfd0e2893f931c061e51428fae7790c5890"
)

PINNED_SERVER_COMMIT = "c40ecb471dced33689e335689f8ffd35a54f47fa"
PINNED_SERVER_ARCHIVE_NAME = f"kiwisdr-{PINNED_SERVER_COMMIT}.zip"
PINNED_SERVER_ARCHIVE_SHA256 = (
    "d6a50adfce7f75133020de85635711dc6c2218e6f134d901ac13a450b57de7ea"
)
PINNED_SERVER_MEMBER = "rx/rx_sound.cpp"
PINNED_SERVER_MEMBER_SHA256 = (
    "b749c91446a5c28e63b37997fa5d0912cf0bdb1a665a053810bf2cfc13547128"
)
LOCAL_DECODER_SHA256 = (
    "85e861a112be31330827c17d902e377c12f9e19bda4e69d2ca1f0c01b93b752a"
)
LOCAL_SEMANTIC_RECEIPT_SHA256 = (
    "11aabcb0bd05ea2353cfbc184bb8e9a889fd72757625aa33861a66e38aec1323"
)

_HERE = Path(__file__).resolve().parent
FROZEN_RECEIPT_PATH = _HERE / "session_receipts" / FROZEN_RECEIPT_NAME
PINNED_SERVER_ARCHIVE_PATH = (
    _HERE / "protocol_sources" / "gate_f2_5_6" / PINNED_SERVER_ARCHIVE_NAME
)
LOCAL_DECODER_PATH = _HERE / "kiwi_probe.py"
LOCAL_SEMANTIC_RECEIPT_PATH = _HERE / "kiwi_gate_f2_5_12.py"

_SOURCE_ANCHORS = (
    "const double dt_to_pos_sol = s->last_gpssec - clk.gps_secs;",
    "std::min(252.0, dt_to_pos_sol)",
    "s->out_pkt_iq.h.last_gps_solution =",
    "s->gpssec = fmod(gps_week_sec + clk.gps_secs + "
    "(dticks/clk.adc_clock_base)",
)

_MISSING_RELATIVE_TIME_STATISTICS = (
    "per_frame_monotonic_arrival_time",
    "gps_seconds_value",
    "gps_nanoseconds_value",
    "server_sample_tick_or_equivalent",
    "decoded_sample_count_per_frame",
    "retune_command_issue_time",
)

_FORBIDDEN_RF_KEYS = {
    "blocks",
    "frames",
    "iq",
    "iq_array",
    "iq_samples",
    "raw_body",
    "raw_frame",
    "raw_frames",
    "samples",
    "stft",
    "waterfall",
}


class F2526Exit(str, Enum):
    TEMPORAL_FAILURE_ATTRIBUTED_OFFLINE = "TEMPORAL_FAILURE_ATTRIBUTED_OFFLINE"


class EvidenceStatus(str, Enum):
    SATISFIED = "SATISFIED"
    UNSATISFIED = "UNSATISFIED"
    NOT_EVALUATED = "NOT_EVALUATED"
    NOT_DERIVED = "NOT_DERIVED"
    NOT_FALSIFIABLE_WITH_THIS_RECEIPT = "NOT_FALSIFIABLE_WITH_THIS_RECEIPT"


@dataclass(frozen=True, slots=True)
class PinnedSourceAttribution:
    archive_sha256: str
    member_sha256: str
    server_commit: str
    field_semantics: str
    saturation_value_s: int
    source_anchors_satisfied: bool
    local_decoder_sha256: str
    local_semantic_receipt_sha256: str
    local_decoder_anchors_satisfied: bool


@dataclass(frozen=True, slots=True)
class BranchTemporalAttribution:
    role: str
    channel_id: int
    incoming_frame_count: int
    snd_frame_count: int
    first_sequence: int
    last_sequence: int
    unique_sequence_count: int
    sequence_gap_count: int
    missing_gps_seconds_count: int
    stale_gps_solution_count: int
    minimum_stale_gps_solution_age_s: int
    maximum_stale_gps_solution_age_s: int
    readiness_admitted_count: int
    snd_header_state: str
    sample_decode_state: str
    iq_mode_state: str
    transport_state: str
    terminal_error_type: str
    terminal_error_relation: str
    raw_rf_persistence: str

    def __post_init__(self) -> None:
        if self.role not in {"reference", "perturbed"}:
            raise ValueError("unknown branch role")
        if self.sequence_gap_count != 0:
            raise ValueError("the frozen receipt recorded a sequence gap")
        if self.readiness_admitted_count != 0:
            raise ValueError("the frozen outcome cannot admit a readiness frame")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")


@dataclass(frozen=True, slots=True)
class TemporalRequirementAttribution:
    frozen_clause: str
    frozen_limit_s: int
    frozen_clause_result: str
    frozen_outcome_preserved: bool
    proximal_observed_failure: str
    remote_staleness_cause: str
    shared_causal_location: str
    ddc_hypothesis_temporal_need: str
    absolute_gnss_freshness_necessity: str
    relative_time_alternative: str
    alternative_receipt_status: str
    missing_relative_time_statistics: tuple[str, ...]
    future_change_scope: str

    def __post_init__(self) -> None:
        if self.frozen_limit_s != FROZEN_MAXIMUM_GPS_SOLUTION_AGE_S:
            raise ValueError("the frozen temporal threshold changed")
        if not self.frozen_outcome_preserved:
            raise ValueError("an offline attribution cannot reclassify Gate F2.5.25")
        if self.missing_relative_time_statistics != _MISSING_RELATIVE_TIME_STATISTICS:
            raise ValueError("relative-time receipt gap changed")


@dataclass(frozen=True, slots=True)
class F2526Assessment:
    exit: F2526Exit
    transform_version: str
    receipt_sha256: str
    receipt_prefix_sha256: str
    frozen_outcome: str
    source: PinnedSourceAttribution
    branches: tuple[BranchTemporalAttribution, ...]
    requirement: TemporalRequirementAttribution
    data_available: bool
    measurement_admissible: bool
    physical_hypothesis_state: str
    decoder_semantics_match_server: bool
    physical_decision_affected: bool
    authorised_claims: tuple[str, ...]
    unauthorised_claims: tuple[str, ...]
    raw_rf_persistence: str

    def __post_init__(self) -> None:
        if self.transform_version != TRANSFORM_VERSION:
            raise ValueError("attribution transform changed")
        if self.frozen_outcome != FROZEN_OUTCOME:
            raise ValueError("frozen outcome changed")
        if len(self.branches) != 2 or {item.role for item in self.branches} != {
            "reference",
            "perturbed",
        }:
            raise ValueError("exactly two branch attributions are required")
        if self.physical_decision_affected:
            raise ValueError("description cannot modify a physical decision")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")


def _reject_nonfinite(token: str) -> Any:
    raise ValueError(f"non-finite JSON token: {token}")


def _strict_documents(path: Path) -> tuple[dict[str, Any], ...]:
    documents = tuple(
        json.loads(line, parse_constant=_reject_nonfinite)
        for line in path.read_text(encoding="utf-8").splitlines()
    )
    if not documents:
        raise ValueError("frozen receipt is empty")
    _assert_finite(documents)
    return documents


def _assert_finite(value: Any) -> None:
    if isinstance(value, dict):
        for item in value.values():
            _assert_finite(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _assert_finite(item)
    elif isinstance(value, float) and not math.isfinite(value):
        raise ValueError("frozen receipt contains a non-finite number")


def _event(documents: tuple[dict[str, Any], ...], name: str) -> dict[str, Any]:
    matches = tuple(item for item in documents if item.get("event") == name)
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {name!r} event")
    return matches[0]


def _walk_keys(value: Any) -> tuple[str, ...]:
    if isinstance(value, dict):
        return tuple(str(key) for key in value) + tuple(
            key for item in value.values() for key in _walk_keys(item)
        )
    if isinstance(value, list):
        return tuple(key for item in value for key in _walk_keys(item))
    return ()


def _verify_source(path: Path) -> PinnedSourceAttribution:
    archive = path.read_bytes()
    if sha256(archive).hexdigest() != PINNED_SERVER_ARCHIVE_SHA256:
        raise ValueError("pinned KiwiSDR server archive hash changed")
    with ZipFile(path) as source_zip:
        member = source_zip.read(PINNED_SERVER_MEMBER)
    if sha256(member).hexdigest() != PINNED_SERVER_MEMBER_SHA256:
        raise ValueError("pinned rx_sound.cpp hash changed")
    source = member.decode("utf-8")
    anchors_satisfied = all(anchor in source for anchor in _SOURCE_ANCHORS)
    if not anchors_satisfied:
        raise ValueError("pinned source no longer supports the temporal attribution")
    decoder_source = LOCAL_DECODER_PATH.read_text(encoding="utf-8").replace(
        "\r\n", "\n"
    )
    semantic_source = LOCAL_SEMANTIC_RECEIPT_PATH.read_text(
        encoding="utf-8"
    ).replace("\r\n", "\n")
    if sha256(decoder_source.encode()).hexdigest() != LOCAL_DECODER_SHA256:
        raise ValueError("local IQ decoder changed after the frozen outcome")
    if (
        sha256(semantic_source.encode()).hexdigest()
        != LOCAL_SEMANTIC_RECEIPT_SHA256
    ):
        raise ValueError("local semantic receipt decoder changed after the outcome")
    local_anchors_satisfied = all(
        anchor in decoder_source
        for anchor in (
            'struct.unpack("<BBII", body[7:17])',
            "gps_timestamp_available=gps_seconds > 0 and gps_solution_age_s <= 252",
        )
    ) and all(
        anchor in semantic_source
        for anchor in (
            "FROZEN_MAX_GPS_SOLUTION_AGE_S = 30",
            'struct.unpack(\n        "<BBII", body[7:17]\n    )',
            "if gps_solution_age_s <= FROZEN_MAX_GPS_SOLUTION_AGE_S",
        )
    )
    if not local_anchors_satisfied:
        raise ValueError("local decoder no longer matches the attributed field semantics")
    return PinnedSourceAttribution(
        PINNED_SERVER_ARCHIVE_SHA256,
        PINNED_SERVER_MEMBER_SHA256,
        PINNED_SERVER_COMMIT,
        "seconds since the server's latest GPS position solution",
        252,
        True,
        LOCAL_DECODER_SHA256,
        LOCAL_SEMANTIC_RECEIPT_SHA256,
        True,
    )


def _sequence_gaps(sequences: tuple[int, ...]) -> int:
    return sum(current != previous + 1 for previous, current in zip(sequences, sequences[1:]))


def _branch_attribution(branch: dict[str, Any]) -> BranchTemporalAttribution:
    snd = tuple(
        item
        for item in branch["semantic_frame_receipts"]
        if item["frame_class"] == "SND"
    )
    if not snd:
        raise ValueError("branch contains no semantic SND receipt")
    sequences = tuple(int(item["sequence"]) for item in snd)
    missing_seconds = tuple(
        item for item in snd if item["gps_seconds_present_clause"] == "UNSATISFIED"
    )
    stale = tuple(
        item for item in snd if item["gps_age_within_limit_clause"] == "UNSATISFIED"
    )
    if len(missing_seconds) != 1 or missing_seconds[0]["gps_solution_age_s"] != 0:
        raise ValueError("unexpected initial GPS metadata state")
    if len(stale) != len(snd) - 1:
        raise ValueError("unexpected temporal-clause distribution")
    ages = tuple(int(item["gps_solution_age_s"]) for item in stale)
    if not all(item["snd_header_clause"] == "SATISFIED" for item in snd):
        raise ValueError("SND header decode was not uniformly satisfied")
    if not all(item["sample_decode_clause"] == "SATISFIED" for item in snd):
        raise ValueError("sample decode was not uniformly satisfied")
    if not all(item["iq_mode_clause"] == "SATISFIED" for item in snd):
        raise ValueError("IQ mode was not uniformly satisfied")
    return BranchTemporalAttribution(
        role=str(branch["role"]),
        channel_id=int(branch["observed_channel_id"]),
        incoming_frame_count=int(branch["incoming_frame_count"]),
        snd_frame_count=len(snd),
        first_sequence=sequences[0],
        last_sequence=sequences[-1],
        unique_sequence_count=len(set(sequences)),
        sequence_gap_count=_sequence_gaps(sequences),
        missing_gps_seconds_count=len(missing_seconds),
        stale_gps_solution_count=len(stale),
        minimum_stale_gps_solution_age_s=min(ages),
        maximum_stale_gps_solution_age_s=max(ages),
        readiness_admitted_count=sum(
            item["readiness_clause"] == "SATISFIED" for item in snd
        ),
        snd_header_state=EvidenceStatus.SATISFIED.value,
        sample_decode_state=EvidenceStatus.SATISFIED.value,
        iq_mode_state=EvidenceStatus.SATISFIED.value,
        transport_state="ACTIVE_CONTIGUOUS_SND_DELIVERY",
        terminal_error_type=str(branch["error_type"]),
        terminal_error_relation="DOWNSTREAM_DEADLINE_CONSEQUENCE",
        raw_rf_persistence=str(branch["raw_rf_persistence"]),
    )


def _requirement_attribution() -> TemporalRequirementAttribution:
    return TemporalRequirementAttribution(
        frozen_clause="gps_solution_age_s <= 30 and gps_seconds present",
        frozen_limit_s=FROZEN_MAXIMUM_GPS_SOLUTION_AGE_S,
        frozen_clause_result=EvidenceStatus.UNSATISFIED.value,
        frozen_outcome_preserved=True,
        proximal_observed_failure="REMOTE_GPS_SOLUTION_FRESHNESS_CLAUSE_UNSATISFIED",
        remote_staleness_cause="UNKNOWN_NOT_RECORDED",
        shared_causal_location="SHARED_UPSTREAM_SERVER_GPS_CLOCK_STATE",
        ddc_hypothesis_temporal_need=(
            "relative simultaneity, continuity, command-boundary ordering, and "
            "drift on the shared ADC clock"
        ),
        absolute_gnss_freshness_necessity=EvidenceStatus.NOT_DERIVED.value,
        relative_time_alternative="CONCEPTUALLY_PLAUSIBLE_NEW_TRIAL_ONLY",
        alternative_receipt_status=(
            EvidenceStatus.NOT_FALSIFIABLE_WITH_THIS_RECEIPT.value
        ),
        missing_relative_time_statistics=_MISSING_RELATIVE_TIME_STATISTICS,
        future_change_scope=(
            "derive a new temporal clause from the intervention topology; do not "
            "raise or remove the frozen threshold"
        ),
    )


def audit_frozen_outcome(
    receipt_path: Path = FROZEN_RECEIPT_PATH,
    source_archive_path: Path = PINNED_SERVER_ARCHIVE_PATH,
) -> F2526Assessment:
    """Attribute Gate F2.5.25 without network access or outcome mutation."""

    receipt = receipt_path.read_bytes()
    if sha256(receipt).hexdigest() != FROZEN_RECEIPT_SHA256:
        raise ValueError("frozen Gate F2.5.25 receipt hash changed")
    lines = receipt.splitlines(keepends=True)
    if sha256(b"".join(lines[:-1])).hexdigest() != FROZEN_RECEIPT_PREFIX_SHA256:
        raise ValueError("frozen Gate F2.5.25 prefix hash changed")

    documents = _strict_documents(receipt_path)
    if set(_walk_keys(list(documents))) & _FORBIDDEN_RF_KEYS:
        raise ValueError("frozen receipt unexpectedly contains RF payload data")

    control = _event(
        documents, "gate_f2_5_25_phase_aware_control_receipt"
    )["payload"]
    branches = tuple(
        _branch_attribution(item["integrated_receipt"])
        for item in control["branch_controls"]
    )
    outcome = _event(documents, "gate_f2_5_25_prefreeze_outcome")["payload"]
    if outcome["outcome"] != FROZEN_OUTCOME or outcome["plan"] is not None:
        raise ValueError("frozen Gate F2.5.25 outcome changed")
    if any(
        item["state"] != "NOT_EVALUATED"
        for item in outcome["phase_receipts"]
        if item["phase"] != "DIRECT_DUAL_SND_QUALIFICATION"
    ):
        raise ValueError("a downstream physical phase was unexpectedly evaluated")

    source = _verify_source(source_archive_path)
    return F2526Assessment(
        exit=F2526Exit.TEMPORAL_FAILURE_ATTRIBUTED_OFFLINE,
        transform_version=TRANSFORM_VERSION,
        receipt_sha256=FROZEN_RECEIPT_SHA256,
        receipt_prefix_sha256=FROZEN_RECEIPT_PREFIX_SHA256,
        frozen_outcome=FROZEN_OUTCOME,
        source=source,
        branches=branches,
        requirement=_requirement_attribution(),
        data_available=True,
        measurement_admissible=False,
        physical_hypothesis_state=EvidenceStatus.NOT_EVALUATED.value,
        decoder_semantics_match_server=True,
        physical_decision_affected=False,
        authorised_claims=(
            "two distinct server channels delivered contiguous decodable SND/IQ frames",
            "no frame satisfied the frozen event-time admission clause",
            "the terminal timeout followed repeated temporal-clause failures",
            "the DDC physical hypothesis was not evaluated",
        ),
        unauthorised_claims=(
            "the receiver GPS subsystem failed for a known cause",
            "the samples lacked physical information",
            "the 30-second limit may be changed retroactively",
            "relative timing would have admitted the frozen session",
            "the feature was upstream or downstream of the channel DDC",
        ),
        raw_rf_persistence=RAW_RF_PERSISTENCE,
    )


def assess() -> F2526Assessment:
    """Return the deterministic, repository-bound offline attribution."""

    return audit_frozen_outcome()
