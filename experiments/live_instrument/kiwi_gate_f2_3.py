"""Gate F2.3 causal-topology audit and prospective probe semantics.

This module is deliberately offline and Gate-F2-specific.  It describes the
experiment that a later, separately authorised runner could materialise; it
does not discover endpoints, open sockets, acquire RF, or persist samples.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


KIWI_SERVER_COMMIT = "c40ecb471dced33689e335689f8ffd35a54f47fa"
KIWI_CLIENT_COMMIT = "4eb733e6b6147f7fbeb97ced64cdac029b202d18"


class TopologyKind(str, Enum):
    TWO_INDEPENDENT_KIWIS = "A_TWO_INDEPENDENT_KIWIS"
    ONE_KIWI_TWO_SIMULTANEOUS_CHANNELS = "B_ONE_KIWI_TWO_SIMULTANEOUS_CHANNELS"
    ONE_KIWI_TIME_MULTIPLEXED = "C_ONE_KIWI_TIME_MULTIPLEXED"


class F23Hypothesis(str, Enum):
    H_UPSTREAM_OF_CHANNEL_DDC = "H_UPSTREAM_OF_CHANNEL_DDC"
    H_DOWNSTREAM_CHANNEL_FIXED = "H_DOWNSTREAM_CHANNEL_FIXED"
    H_UNRESOLVED = "H_UNRESOLVED"


class F23Outcome(str, Enum):
    NO_MULTI_CHANNEL_CAPABILITY = "NO_MULTI_CHANNEL_CAPABILITY"
    NO_ADMISSIBLE_CAUSAL_TOPOLOGY = "NO_ADMISSIBLE_CAUSAL_TOPOLOGY"
    NO_FALSIFIABLE_INTERVENTION = "NO_FALSIFIABLE_INTERVENTION"
    UPSTREAM_OF_CHANNEL_DDC_SUPPORTED = "UPSTREAM_OF_CHANNEL_DDC_SUPPORTED"
    DOWNSTREAM_CHANNEL_FIXED_SUPPORTED = "DOWNSTREAM_CHANNEL_FIXED_SUPPORTED"
    AMBIGUOUS = "AMBIGUOUS"
    INTERVENTION_INVALID = "INTERVENTION_INVALID"
    NOT_DETECTABLE = "NOT_DETECTABLE"


@dataclass(frozen=True, slots=True)
class TopologyAudit:
    topology: TopologyKind
    causal_cut: str
    ambiguities_eliminated: tuple[str, ...]
    ambiguities_left_open: tuple[str, ...]
    maximum_authorised_claim: str
    required_witnesses: tuple[str, ...]
    necessary_metadata: tuple[str, ...]
    geographic_location_required: bool
    geographic_location_caveat: str
    required_independence: str


def topology_audits() -> tuple[TopologyAudit, ...]:
    """Return the three competing causal topologies, without ranking by convenience."""

    return (
        TopologyAudit(
            TopologyKind.TWO_INDEPENDENT_KIWIS,
            "retune the selected RX DDC on one hardware path while another hardware, ADC, clock and propagation path remains fixed",
            (
                "a feature reported by both devices is not rooted in one receiver's downstream channel alone",
                "a stable remote branch can expose gross temporal change during the intervention",
            ),
            (
                "different HF propagation, antennas, analogue responses and site interference",
                "clock and frequency-reference offsets between receivers",
                "source identity and the distinction between external RF and two similar local artifacts",
            ),
            "the feature is consistent with being upstream of the perturbed receiver's channel DDC and was also observed on an independent apparatus; no emitter identity or location follows",
            (
                "GNSS event-time continuity on both streams",
                "command ledger and retune-effect witness on the perturbed stream",
                "stable feature or orthogonal witness on the remote reference stream",
                "independent hardware/antenna/ADC lineage",
            ),
            (
                "hardware-root identities",
                "per-stream sequence ranges and event times",
                "requested centers, sample rates, overflow and transform ledgers",
                "antenna/configuration lineage; location only when site/path separation is claimed",
            ),
            False,
            "coordinates are not needed for the DDC cut itself, but some independent evidence of distinct apparatus is; coordinates become necessary only for a geographic/path claim",
            "hardware independence plus temporal alignment",
        ),
        TopologyAudit(
            TopologyKind.ONE_KIWI_TWO_SIMULTANEOUS_CHANNELS,
            "hold one RX DDC branch fixed while retuning a simultaneous sibling RX DDC after the shared antenna, front-end, ADC and clock",
            (
                "different propagation paths and analogue front ends",
                "inter-receiver clock drift and client-arrival alignment",
                "ordinary temporal fading as the sole explanation for A/B differences",
            ),
            (
                "antenna/front-end/ADC/clock artifacts upstream of the channel split",
                "ADC overload, analogue intermodulation and common-mode gain change",
                "FPGA channel coupling, command misrouting and shared server/software defects",
                "source identity and whether an upstream feature is external RF",
            ),
            "the feature is supported as upstream of the per-channel DDC, or fixed downstream in the perturbed channel, within this receiver; 'external RF' is not authorised",
            (
                "reference command ledger contains no retune",
                "independent sequence and artifact receipts for both SND streams",
                "continuous GNSS event time on both streams",
                "retune-effect witness in the perturbed branch",
                "target or same-path witness remains stable in the fixed branch across A1/B/A2",
            ),
            (
                "one receiver identity and two connection/channel roles",
                "per-stream sequence ranges, GNSS event times and sample rates",
                "per-connection command ledger and requested centers",
                "overflow flags, passbands, transform version and ephemeral artifact hashes",
            ),
            False,
            "geography is outside this within-receiver intervention",
            "simultaneous downstream channel-branch independence; hardware and timebase are intentionally shared",
        ),
        TopologyAudit(
            TopologyKind.ONE_KIWI_TIME_MULTIPLEXED,
            "retune and restore one DDC branch over time (A1 -> B -> A2), so intervention and time are not separated",
            (
                "A2 recovery can reject an irreversible failure or permanent untuning",
                "one hardware path avoids inter-receiver calibration differences",
            ),
            (
                "HF fading, transient interference, AGC state and receiver drift during B",
                "settling/hysteresis and packet loss at either boundary",
                "loss of the feature during B cannot be compared with a simultaneous fixed branch",
            ),
            "a reversible response is consistent with retuning; the receipt alone cannot localise the feature across the DDC boundary",
            (
                "same-path positive witness in A1, B and A2",
                "command-boundary receipts and post-command sample evidence",
                "sequence/event-time continuity and A2 return",
            ),
            (
                "single stream identity and sequence range",
                "GNSS event times, command times and settling exclusions",
                "requested centers, sample rate, overflow and transform ledger",
            ),
            False,
            "geography cannot repair the missing simultaneous control",
            "temporal reversibility only; neither hardware nor simultaneous channel independence",
        ),
    )


@dataclass(frozen=True, slots=True)
class RootTopologyRequirement:
    """The Gate F2.3 requirement, not a project-wide root abstraction."""

    intervention_boundary: str
    shared_upstream_components: tuple[str, ...]
    independent_downstream_branches: tuple[str, str]
    fixed_reference_branch: str
    perturbed_branch: str
    claim_scope: str
    simultaneous_required: bool
    independent_stream_receipts_required: bool
    geographic_location_required: bool
    hardware_independence_required: bool
    channel_independence_required: bool

    def __post_init__(self) -> None:
        branches = self.independent_downstream_branches
        if len(set(branches)) != 2:
            raise ValueError("Gate F2.3 requires two distinct downstream branches")
        if self.fixed_reference_branch not in branches or self.perturbed_branch not in branches:
            raise ValueError("fixed and perturbed roles must name the downstream branches")
        if self.fixed_reference_branch == self.perturbed_branch:
            raise ValueError("one branch cannot be both fixed and perturbed")
        if not self.intervention_boundary or not self.shared_upstream_components or not self.claim_scope:
            raise ValueError("the causal boundary, shared roots and claim scope must be explicit")
        if not self.simultaneous_required or not self.independent_stream_receipts_required:
            raise ValueError("Gate F2.3 cannot weaken simultaneity or atomic stream receipts")
        if self.geographic_location_required or self.hardware_independence_required:
            raise ValueError("geography and a second hardware root are outside the Gate F2.3 cut")
        if not self.channel_independence_required:
            raise ValueError("Gate F2.3 requires two independently controlled channel branches")


def gate_f2_root_topology_requirement() -> RootTopologyRequirement:
    return RootTopologyRequirement(
        intervention_boundary="FPGA per-channel RX NCO/DDC",
        shared_upstream_components=(
            "antenna",
            "analogue front-end",
            "ADC",
            "ADC sample clock",
            "receiver GNSS timebase",
        ),
        independent_downstream_branches=("reference_rx_channel", "perturbed_rx_channel"),
        fixed_reference_branch="reference_rx_channel",
        perturbed_branch="perturbed_rx_channel",
        claim_scope="relative localisation upstream versus channel-fixed downstream of the per-channel DDC; never source identity or external-RF origin",
        simultaneous_required=True,
        independent_stream_receipts_required=True,
        geographic_location_required=False,
        hardware_independence_required=False,
        channel_independence_required=True,
    )


@dataclass(frozen=True, slots=True)
class SourceEvidence:
    proposition: str
    status: str
    basis: tuple[str, ...]
    limit: str


@dataclass(frozen=True, slots=True)
class MultiChannelCodeAudit:
    server_commit: str
    client_commit: str
    evidence: tuple[SourceEvidence, ...]
    shared_components: tuple[str, ...]
    distinct_stream_metadata: tuple[str, ...]
    operator_limits: tuple[str, ...]
    fixed_branch_proof: tuple[str, ...]


def multi_channel_code_audit() -> MultiChannelCodeAudit:
    """Evidence already frozen before F2.3; this function performs no I/O."""

    official = (
        "rx/rx_sound_cmd.cpp:67-79",
        "rx/rx_sound_cmd.cpp:151-175",
        "rx/rx_sound.cpp:568-596",
        "rx/rx_sound.cpp:1082-1136",
    )
    return MultiChannelCodeAudit(
        KIWI_SERVER_COMMIT,
        KIWI_CLIENT_COMMIT,
        (
            SourceEvidence(
                "a SND connection is allocated a selected FPGA RX channel",
                "VERIFIED_FROM_FROZEN_OFFICIAL_SOURCE_AUDIT",
                official,
                "the channel allocation itself does not prove that two public slots are available now",
            ),
            SourceEvidence(
                "SET mod=iq ... freq=<kHz> changes the 48-bit phase word of the selected RX channel",
                "VERIFIED_FROM_FROZEN_OFFICIAL_SOURCE_AUDIT",
                official,
                "there is no protocol tune acknowledgement; post-command samples and a witness must demonstrate effect",
            ),
            SourceEvidence(
                "one process can maintain two SND WebSocket connections concurrently",
                "VERIFIED_IN_FROZEN_CLIENT_IMPLEMENTATION",
                (
                    "experiments/live_instrument/kiwi_gate_f2.py:_capture_sequence_root",
                    "experiments/live_instrument/kiwi_gate_f2.py:capture_dual_sequence",
                ),
                "the existing implementation used two endpoints; same-endpoint availability remains a qualification fact, not an offline fact",
            ),
            SourceEvidence(
                "each SND stream carries its own observable sequence field and GNSS sample timestamp headers",
                "VERIFIED_FROM_WIRE_DECODER_AND_FROZEN_SOURCE_AUDIT",
                ("experiments/live_instrument/kiwi_probe.py:_decode_iq_block",) + official,
                "sequence ranges are stream-addressed receipts, not evidence of independent clocks; GNSS/ADC timing is shared",
            ),
        ),
        (
            "antenna",
            "analogue front-end",
            "ADC",
            "ADC sample clock and GNSS timing",
            "server process and FPGA fabric before RX-channel fan-out",
        ),
        (
            "connection/channel role",
            "sequence range",
            "GNSS event-time range",
            "sample rate and IQ flags",
            "requested center and per-connection command ledger",
            "artifact hash and receipt hash",
        ),
        (
            "ext_api can expose fewer than two free public slots",
            "password policy, user limits, preemption and time limits can reject a second connection",
            "server channel configuration can disable IQ or invert the spectrum",
            "busy state can change between status description and stream admission",
        ),
        (
            "freeze a distinct reference connection/channel role",
            "send no frequency command to that connection after initial tuning",
            "retain separate command ledgers and sequence/event-time receipts",
            "require reference continuity and stable target/witness coordinates through A1/B/A2",
            "require a retune-effect witness only on the perturbed branch",
        ),
    )


@dataclass(frozen=True, slots=True)
class CapabilityQualification:
    endpoint_status_available: bool
    external_api_slots: int
    simultaneous_iq_supported: bool
    reference_stream_valid: bool
    perturbed_stream_valid: bool
    distinct_stream_sequences_and_receipts: bool
    per_channel_retune_witnessable: bool
    fixed_reference_branch_witnessable: bool
    target_and_witness_fit_passband: bool


def qualification_blocker(qualification: CapabilityQualification) -> F23Outcome | None:
    """Return the first pre-freeze terminal outcome, or None when admission may proceed."""

    if (
        not qualification.endpoint_status_available
        or qualification.external_api_slots < 2
        or not qualification.simultaneous_iq_supported
        or not qualification.reference_stream_valid
        or not qualification.perturbed_stream_valid
    ):
        return F23Outcome.NO_MULTI_CHANNEL_CAPABILITY
    if (
        not qualification.distinct_stream_sequences_and_receipts
        or not qualification.per_channel_retune_witnessable
        or not qualification.fixed_reference_branch_witnessable
    ):
        return F23Outcome.NO_ADMISSIBLE_CAUSAL_TOPOLOGY
    if not qualification.target_and_witness_fit_passband:
        return F23Outcome.NO_FALSIFIABLE_INTERVENTION
    return None


@dataclass(frozen=True, slots=True)
class HypothesisConsequences:
    hypothesis: F23Hypothesis
    perturbed_baseband_prediction: str
    reconstructed_rf_prediction: str
    fixed_reference_prediction: str


def frozen_hypothesis_consequences() -> tuple[HypothesisConsequences, ...]:
    return (
        HypothesisConsequences(
            F23Hypothesis.H_UPSTREAM_OF_CHANNEL_DDC,
            "feature moves by the frozen signed inverse of the perturbed-channel tuning delta",
            "feature absolute-RF coordinate remains invariant within the frozen tolerance",
            "feature remains stable in the simultaneous fixed channel",
        ),
        HypothesisConsequences(
            F23Hypothesis.H_DOWNSTREAM_CHANNEL_FIXED,
            "feature remains at the same perturbed-channel baseband position",
            "reconstructed RF coordinate changes by the frozen signed tuning delta",
            "feature remains stable in the simultaneous fixed channel if it is visible there; otherwise the orthogonal same-path witness remains stable",
        ),
        HypothesisConsequences(
            F23Hypothesis.H_UNRESOLVED,
            "neither frozen coordinate prediction is uniquely supported",
            "no unique causal side of the DDC is assigned",
            "the reference can validate the intervention without resolving the target",
        ),
    )


@dataclass(frozen=True, slots=True)
class VerticalProbeBlueprint:
    receiver_count: int
    simultaneous_snd_slots: int
    connection_roles: tuple[str, str]
    phases: tuple[str, str, str]
    intervention: str
    qualification_clauses: tuple[str, ...]
    confirmation_witnesses: tuple[str, ...]
    artifact_policy: str
    persistence_policy: str
    post_freeze_retry_budget: int
    stop_condition: str


def minimal_vertical_probe() -> VerticalProbeBlueprint:
    return VerticalProbeBlueprint(
        receiver_count=1,
        simultaneous_snd_slots=2,
        connection_roles=("fixed_reference", "controllably_retuned"),
        phases=("A1", "B", "A2"),
        intervention="only the perturbed connection receives A->B->A frequency commands; reference remains fixed",
        qualification_clauses=(
            "endpoint_status_available",
            "multi_channel_slots_available",
            "reference_stream_valid",
            "perturbed_stream_valid",
            "per_channel_retune_testimoniable",
            "admissible_causal_topology",
            "target_and_witness_inside_both_required_passbands",
        ),
        confirmation_witnesses=(
            "reference stream sequence/event-time continuity",
            "perturbed stream sequence/event-time continuity",
            "reference target or orthogonal feature stable across A1/B/A2",
            "perturbed retune witness follows the frozen signed prediction and returns in A2",
        ),
        artifact_policy="hash every ephemeral per-stream/per-phase artifact before analysis and destruction",
        persistence_policy="zero RF, waterfall or sample persistence; receipts and hashes only",
        post_freeze_retry_budget=0,
        stop_condition="one independent confirmation outcome or the first terminal qualification/intervention outcome",
    )


@dataclass(frozen=True, slots=True)
class ConfirmationEvidence:
    both_streams_continuous: bool
    gnss_event_time_aligned: bool
    adc_clean_and_transform_complete: bool
    reference_command_ledger_clean: bool
    reference_branch_stable: bool
    retune_command_routed_to_perturbed_only: bool
    retune_effect_witnessed: bool
    target_detectable_in_a1_b_a2: bool
    a2_return_matches: bool
    upstream_prediction_matches: bool
    downstream_prediction_matches: bool


def classify_confirmation(evidence: ConfirmationEvidence) -> F23Outcome:
    """Classify one frozen confirmation without adapting predictions or thresholds."""

    if (
        not evidence.reference_command_ledger_clean
        or not evidence.reference_branch_stable
        or not evidence.retune_command_routed_to_perturbed_only
        or not evidence.retune_effect_witnessed
    ):
        return F23Outcome.INTERVENTION_INVALID
    if (
        not evidence.both_streams_continuous
        or not evidence.gnss_event_time_aligned
        or not evidence.adc_clean_and_transform_complete
        or not evidence.target_detectable_in_a1_b_a2
        or not evidence.a2_return_matches
    ):
        return F23Outcome.NOT_DETECTABLE
    if evidence.upstream_prediction_matches and not evidence.downstream_prediction_matches:
        return F23Outcome.UPSTREAM_OF_CHANNEL_DDC_SUPPORTED
    if evidence.downstream_prediction_matches and not evidence.upstream_prediction_matches:
        return F23Outcome.DOWNSTREAM_CHANNEL_FIXED_SUPPORTED
    return F23Outcome.AMBIGUOUS


def shock_answer() -> tuple[str, str]:
    return (
        "The second hardware root was not required for the F2 DDC-invariance hypothesis; requiring it blocked the cleaner same-ADC simultaneous intervention that the hypothesis actually needs.",
        "Shared ADC, clock and front-end improve relative alignment and remove propagation differences, but a coherent clock spur, ADC artifact, overload product or analogue intermodulation is also shared and can satisfy the upstream-of-channel-DDC prediction. The result therefore localises a boundary without proving external RF.",
    )
