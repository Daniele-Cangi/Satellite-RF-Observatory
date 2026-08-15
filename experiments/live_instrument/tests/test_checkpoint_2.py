"""Offline tests for the minimal Checkpoint 2 model and both probe kernels."""

from datetime import datetime, timedelta, timezone
from io import BytesIO

import numpy as np
from PIL import Image, ImageDraw

from experiments.live_instrument.kiwi_probe import (
    IQBlock,
    IQBlockRing,
    KiwiCapture,
    KiwiEndpoint,
    compare_rf_structure,
)
from experiments.live_instrument.models import (
    CausalGraph,
    ClauseAssessment,
    ClauseStatus,
    ConstraintReceipt,
    DecisionClause,
    DecisionContract,
    Intent,
    emit_jsonl,
)
from experiments.live_instrument.satnogs_probe import (
    SatnogsObservation,
    WaterfallArtifact,
    _waterfall_constraints,
    assimilate_satnogs_pair,
    select_fresh_pair,
)


NOW = datetime(2026, 8, 15, 22, 10, tzinfo=timezone.utc)


def test_intent_target_is_optional_and_ttl_uses_event_end() -> None:
    contract = _availability_contract("Did a physical RF change occur?", 600.0)

    assert contract.intent.target is None
    assert contract.accepts_age(NOW - timedelta(seconds=600), NOW)
    assert not contract.accepts_age(NOW - timedelta(seconds=601), NOW)


def test_causal_graph_rejects_silent_root_redefinition() -> None:
    graph = CausalGraph()
    graph.add_node("station:a", "measurement_root", "first")

    try:
        graph.add_node("station:a", "measurement_root", "different")
    except ValueError as error:
        assert "redefined" in str(error)
    else:
        raise AssertionError("causal node redefinition must fail")


def test_satnogs_selection_is_local_fresh_and_two_station() -> None:
    contract = _availability_contract(
        "two-station evidence", 600.0, roots=2, target="control-only"
    )
    payload = [
        _satnogs_payload(1, 10, 50.0, 8.0, 300),
        _satnogs_payload(2, 11, 52.0, 12.0, 250),
        _satnogs_payload(3, 12, 54.0, 13.0, 601),
    ]

    left, right = select_fresh_pair(payload, contract, NOW)

    assert {left.observation_id, right.observation_id} == {1, 2}
    assert left.station_id != right.station_id


def test_waterfall_receipt_keeps_image_domain_constraints() -> None:
    image = Image.new("RGB", (400, 300), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((40, 20, 359, 279), fill=(20, 30, 60))
    for y in (80, 160, 220):
        draw.line((90, y, 250, y), fill=(240, 230, 40), width=2)
    output = BytesIO()
    image.save(output, format="PNG")

    constraints = _waterfall_constraints(output.getvalue())

    assert constraints["structured_time_fraction"] > 0.0
    assert constraints["plot_pixels"][0] > 250
    assert len(constraints["bright_energy_band_normalized_from_center"]) == 2


def test_satnogs_assimilation_does_not_claim_identity() -> None:
    contract = _satnogs_contract()
    first = SatnogsObservation.from_api(_satnogs_payload(1, 10, 50.0, 8.0, 300))
    second = SatnogsObservation.from_api(_satnogs_payload(2, 11, 52.0, 12.0, 250))
    artifacts = [
        WaterfallArtifact(
            observation=item,
            arrived_at=NOW,
            published_at=NOW - timedelta(seconds=200),
            content_length=10,
            sha256_hex=str(index) * 64,
            constraints={
                "structured_time_fraction": 0.01,
                "structured_time_segments_image_fraction": [[0.1, 0.2]],
                "bright_energy_band_normalized_from_center": [-0.2, 0.1],
                "plot_pixels": [100, 200],
            },
        )
        for index, item in enumerate((first, second), start=1)
    ]

    evidence, belief, graph = assimilate_satnogs_pair(
        contract, artifacts[0], artifacts[1], NOW
    )

    assert belief.assessment("measurement_availability").status is ClauseStatus.SATISFIED
    assert belief.assessment("emitter_identity").status is ClauseStatus.UNRESOLVED
    assert len(graph.root_ids("measurement_root")) == 2
    assert evidence.receipt.branch == "satnogs"


def test_iq_ring_evicts_by_event_time() -> None:
    ring = IQBlockRing(1.0)
    for index in range(4):
        start = NOW + timedelta(seconds=index * 0.5)
        ring.append(_iq_block(start, np.ones(100, dtype=np.complex64)))

    blocks = ring.snapshot()
    assert blocks[0].event_start >= NOW + timedelta(seconds=0.5)
    assert blocks[-1].event_start == NOW + timedelta(seconds=1.5)


def test_dual_kiwi_requires_structure_not_equal_frequency_alone() -> None:
    sample_rate = 12_000.0
    count = int(sample_rate * 3.0)
    rng = np.random.default_rng(7)
    left_noise = (
        rng.normal(size=count) + 1j * rng.normal(size=count)
    ).astype(np.complex64)
    right_noise = (
        rng.normal(size=count) + 1j * rng.normal(size=count)
    ).astype(np.complex64)
    left = _capture("left", left_noise, sample_rate)
    right = _capture("right", right_noise, sample_rate)
    contract = _kiwi_contract()

    _event, belief, _graph = compare_rf_structure(
        contract, left, right, NOW + timedelta(seconds=3.1)
    )

    assert belief.assessment("measurement_availability").status is ClauseStatus.SATISFIED
    assert belief.assessment("common_physical_cause").status is ClauseStatus.UNRESOLVED


def test_dual_kiwi_accepts_multiple_aligned_structural_properties() -> None:
    sample_rate = 12_000.0
    count = int(sample_rate * 3.0)
    t = np.arange(count) / sample_rate
    amplitude = 0.15 + 0.85 * (np.sin(2 * np.pi * 1.7 * t) > 0)
    frequency = 700.0 + 130.0 * np.sin(2 * np.pi * 0.8 * t)
    phase = 2 * np.pi * np.cumsum(frequency) / sample_rate
    rng = np.random.default_rng(11)
    shared = amplitude * np.exp(1j * phase)
    left_samples = (shared + 0.04 * (rng.normal(size=count) + 1j * rng.normal(size=count))).astype(np.complex64)
    right_samples = (shared * np.exp(1j * 0.7) + 0.05 * (rng.normal(size=count) + 1j * rng.normal(size=count))).astype(np.complex64)
    contract = _kiwi_contract()

    _event, belief, graph = compare_rf_structure(
        contract,
        _capture("left", left_samples, sample_rate),
        _capture("right", right_samples, sample_rate),
        NOW + timedelta(seconds=3.1),
    )

    assert belief.assessment("measurement_availability").status is ClauseStatus.SATISFIED
    assert belief.assessment("common_physical_cause").status is ClauseStatus.SATISFIED
    assert belief.target is None
    assert len(graph.root_ids("measurement_root")) == 2


def test_expired_evidence_cannot_satisfy_a_contract_clause() -> None:
    contract = _availability_contract("fresh?", 10.0)
    receipt = ConstraintReceipt(
        branch="test",
        event_start=NOW - timedelta(seconds=20),
        event_end=NOW - timedelta(seconds=11),
        constraints=(),
        transforms=(),
        measurement_roots=("station:a",),
        model_roots=(),
        artifact_hashes=(),
        caveats=(),
    )

    try:
        contract.snapshot_from_evidence(
            receipt,
            valid_at=NOW,
            clause_assessments=(
                ClauseAssessment(
                    "measurement_availability",
                    ClauseStatus.SATISFIED,
                    "stale measurement",
                    ("station:a",),
                ),
            ),
            uncertainty=(),
            active_model_roots=(),
        )
    except ValueError as error:
        assert "expired evidence cannot satisfy" in str(error)
    else:
        raise AssertionError("a stale receipt must never satisfy a clause")


def test_jsonl_uses_a_decimal_point_for_measurement_age_seconds() -> None:
    lines: list[str] = []

    emit_jsonl("age", {"measurement_age_s": 77.638}, sink=lines.append)

    assert '"measurement_age_s": 77.638' in lines[0]
    assert "77,638" not in lines[0]


def _satnogs_payload(
    observation_id: int,
    station_id: int,
    latitude: float,
    longitude: float,
    age_s: float,
) -> dict[str, object]:
    end = NOW - timedelta(seconds=age_s)
    start = end - timedelta(minutes=7)
    return {
        "id": observation_id,
        "start": start.isoformat().replace("+00:00", "Z"),
        "end": end.isoformat().replace("+00:00", "Z"),
        "ground_station": station_id,
        "station_name": f"station-{station_id}",
        "station_lat": latitude,
        "station_lng": longitude,
        "station_alt": 100,
        "norad_cat_id": 40014,
        "transmitter_uuid": "same-transmitter",
        "transmitter_downlink_low": 437_445_000,
        "waterfall": f"https://example.invalid/{observation_id}.png",
        "status": "good",
        "tle1": "tle-line-1",
        "tle2": "tle-line-2",
    }


def _availability_contract(
    question: str,
    ttl_s: float,
    *,
    roots: int = 1,
    target: str | None = None,
) -> DecisionContract:
    return DecisionContract(
        Intent(question, target),
        (
            DecisionClause(
                "measurement_availability",
                "fresh measurement roots are available",
                ("rf_structure",),
                roots,
            ),
        ),
        ttl_s,
    )


def _satnogs_contract() -> DecisionContract:
    return DecisionContract(
        Intent("two station", "control target"),
        (
            DecisionClause("measurement_availability", "two roots", ("rf",), 2),
            DecisionClause("emitter_identity", "identity evidence", ("identity",), 2),
        ),
        600.0,
    )


def _kiwi_contract() -> DecisionContract:
    return DecisionContract(
        Intent("same phenomenon?"),
        (
            DecisionClause("measurement_availability", "two IQ streams", ("iq",), 2),
            DecisionClause("common_physical_cause", "same cause", ("rf_structure",), 2),
        ),
        30.0,
    )


def _iq_block(start: datetime, samples: np.ndarray, sample_rate: float = 100.0) -> IQBlock:
    return IQBlock(
        event_start=start,
        event_end=start + timedelta(seconds=len(samples) / sample_rate),
        samples=samples,
        rssi_db=-80.0,
        gps_solution_age_s=2,
        gps_timestamp_available=True,
        adc_overflow=False,
        sequence=1,
    )


def _capture(name: str, samples: np.ndarray, sample_rate: float) -> KiwiCapture:
    block = _iq_block(NOW, samples, sample_rate)
    return KiwiCapture(
        endpoint=KiwiEndpoint(name, "127.0.0.1"),
        center_frequency_hz=9_996_000.0,
        sample_rate_hz=sample_rate,
        status={"ext_api": "4"},
        blocks=(block,),
        arrived_start=NOW,
        arrived_end=block.event_end,
    )
