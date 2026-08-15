"""Probe A: assimilate one fresh pair of SatNOGS waterfall artifacts.

All artifacts and causal state remain in memory. Satellite/job identity is used
to select and reconstruct the controlled observation, never as independent RF
evidence for that identity.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
from io import BytesIO
from math import asin, cos, radians, sin, sqrt
from typing import Any, Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np
from PIL import Image

from .models import (
    BeliefSnapshot,
    CausalGraph,
    ClauseAssessment,
    ClauseStatus,
    Constraint,
    ConstraintReceipt,
    DecisionClause,
    DecisionContract,
    EvidenceEvent,
    Intent,
    Transform,
    emit_jsonl,
)


SATNOGS_OBSERVATIONS = "https://network.satnogs.org/api/observations/"
USER_AGENT = "Satellite-RF-Observatory-Gate-B/0.1 (short read-only probe)"


@dataclass(frozen=True, slots=True)
class SatnogsObservation:
    observation_id: int
    start: datetime
    end: datetime
    station_id: int
    station_name: str
    station_lat: float
    station_lng: float
    station_alt_m: float
    norad_id: int
    transmitter_uuid: str
    carrier_hz: float | None
    waterfall_url: str
    status: str
    tle1: str
    tle2: str

    @classmethod
    def from_api(cls, item: dict[str, Any]) -> "SatnogsObservation":
        carrier = item.get("transmitter_downlink_low")
        return cls(
            observation_id=int(item["id"]),
            start=_parse_time(item["start"]),
            end=_parse_time(item["end"]),
            station_id=int(item["ground_station"]),
            station_name=str(item["station_name"]),
            station_lat=float(item["station_lat"]),
            station_lng=float(item["station_lng"]),
            station_alt_m=float(item["station_alt"]),
            norad_id=int(item["norad_cat_id"]),
            transmitter_uuid=str(item["transmitter_uuid"]),
            carrier_hz=None if carrier is None else float(carrier),
            waterfall_url=str(item["waterfall"]),
            status=str(item.get("status", item.get("vetted_status", "unknown"))),
            tle1=str(item.get("tle1", "")),
            tle2=str(item.get("tle2", "")),
        )


@dataclass(frozen=True, slots=True)
class WaterfallArtifact:
    observation: SatnogsObservation
    arrived_at: datetime
    published_at: datetime | None
    content_length: int
    sha256_hex: str
    constraints: dict[str, Any]


def fetch_recent_observations(
    end_before: datetime,
    timeout_s: float = 15.0,
) -> list[dict[str, Any]]:
    query = urlencode({"end": end_before.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")})
    request = Request(
        f"{SATNOGS_OBSERVATIONS}?{query}",
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )
    with urlopen(request, timeout=timeout_s) as response:
        import json

        payload = json.loads(response.read())
    if not isinstance(payload, list):
        raise RuntimeError("SatNOGS observations endpoint did not return a list")
    return payload


def select_fresh_pair(
    payload: Iterable[dict[str, Any]],
    contract: DecisionContract,
    now: datetime,
) -> tuple[SatnogsObservation, SatnogsObservation]:
    ranked = rank_fresh_pairs(payload, contract, now)
    if not ranked:
        raise RuntimeError("no fresh two-station SatNOGS waterfall pair satisfies the contract")
    return ranked[0]


def rank_fresh_pairs(
    payload: Iterable[dict[str, Any]],
    contract: DecisionContract,
    now: datetime,
) -> list[tuple[SatnogsObservation, SatnogsObservation]]:
    candidates: list[SatnogsObservation] = []
    for item in payload:
        if not item.get("waterfall"):
            continue
        status = str(item.get("status", item.get("vetted_status", "unknown")))
        # Human vetting is not a physical measurement. Completed "unknown"
        # artifacts remain candidates and must pass our own structure checks;
        # explicit bad/future observations do not.
        if status not in {"good", "unknown"}:
            continue
        try:
            candidate = SatnogsObservation.from_api(item)
        except (KeyError, TypeError, ValueError):
            continue
        if contract.accepts_age(candidate.end, now):
            candidates.append(candidate)

    groups: dict[tuple[int, str], list[SatnogsObservation]] = {}
    for candidate in candidates:
        groups.setdefault((candidate.norad_id, candidate.transmitter_uuid), []).append(candidate)

    ranked: list[tuple[tuple[float, float, float], SatnogsObservation, SatnogsObservation]] = []
    for observations in groups.values():
        for index, left in enumerate(observations):
            for right in observations[index + 1 :]:
                if left.station_id == right.station_id:
                    continue
                overlap_s = (
                    min(left.end, right.end) - max(left.start, right.start)
                ).total_seconds()
                if overlap_s <= 0.0:
                    continue
                separation_km = _haversine_km(
                    left.station_lat,
                    left.station_lng,
                    right.station_lat,
                    right.station_lng,
                )
                if separation_km < 20.0:
                    continue
                oldest_age = max(
                    contract.measurement_age_s(left.end, now),
                    contract.measurement_age_s(right.end, now),
                )
                ranked.append(
                    ((-oldest_age, overlap_s, separation_km), left, right)
                )
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [(item[1], item[2]) for item in ranked]


def fetch_waterfall(
    observation: SatnogsObservation,
    timeout_s: float = 20.0,
) -> WaterfallArtifact:
    request = Request(
        observation.waterfall_url,
        headers={"Accept": "image/png", "User-Agent": USER_AGENT},
    )
    with urlopen(request, timeout=timeout_s) as response:
        body = response.read()
        last_modified = response.headers.get("Last-Modified")
    arrived_at = datetime.now(timezone.utc)
    published_at = None if last_modified is None else parsedate_to_datetime(last_modified).astimezone(timezone.utc)
    return WaterfallArtifact(
        observation=observation,
        arrived_at=arrived_at,
        published_at=published_at,
        content_length=len(body),
        sha256_hex=sha256(body).hexdigest(),
        constraints=_waterfall_constraints(body),
    )


def assimilate_satnogs_pair(
    contract: DecisionContract,
    left: WaterfallArtifact,
    right: WaterfallArtifact,
    now: datetime,
) -> tuple[EvidenceEvent, BeliefSnapshot, CausalGraph]:
    observations = (left.observation, right.observation)
    if len({item.station_id for item in observations}) != 2:
        raise ValueError("SatNOGS assimilation requires two station hardware roots")
    if not all(contract.accepts_age(item.end, now) for item in observations):
        raise ValueError("SatNOGS evidence expired before assimilation")

    event_start = max(item.start for item in observations)
    event_end = min(item.end for item in observations)
    overlap_s = (event_end - event_start).total_seconds()
    separation_km = _haversine_km(
        observations[0].station_lat,
        observations[0].station_lng,
        observations[1].station_lat,
        observations[1].station_lng,
    )
    structured = sum(
        artifact.constraints["structured_time_fraction"] > 0.0
        for artifact in (left, right)
    )
    if overlap_s <= 0.0 or structured < 2:
        raise ValueError("the pair does not contain two overlapping structured artifacts")

    gp_fingerprint = sha256(
        "|".join(sorted(f"{item.tle1}|{item.tle2}" for item in observations)).encode()
    ).hexdigest()[:16]
    station_roots = tuple(f"station:{item.station_id}" for item in observations)
    model_roots = (
        "satnogs:network-flowgraph-storage",
        f"satnogs-db:transmitter:{observations[0].transmitter_uuid}",
        f"gp-control-family:{gp_fingerprint}",
    )
    constraints = (
        Constraint("artifact_count", "==", 2, "artifact", "exact", "two HTTP payloads"),
        Constraint("overlap", ">", overlap_s, "s", "API event-window metadata", "intersection of event windows"),
        Constraint("station_separation", ">=", separation_km, "km", "station coordinates are self-reported", "great-circle distance"),
        Constraint(
            "structured_rf_energy",
            "present_in",
            [
                {
                    "observation_id": artifact.observation.observation_id,
                    **artifact.constraints,
                }
                for artifact in (left, right)
            ],
            None,
            "PNG raster/colormap and axes are lossy",
            "robust image-domain structure only; not an absolute spectrum",
        ),
        Constraint(
            "target_identity",
            "not_inferred",
            observations[0].norad_id,
            None,
            "job identity is circular control metadata",
            "selection label retained only for reconstruction",
        ),
    )
    transforms = (
        Transform("station_rf_chain", "partial", "antenna/front-end/clock calibration is not fully published"),
        Transform("tuning", "partial", "job/client tuning is known; oscillator truth is not"),
        Transform("doppler_compensation", "model_conditioned", "flowgraph conditions the observable on GP control", model_roots[-1:]),
        Transform("fft_waterfall_png", "known_lossy", "FFT output was color-mapped and rasterized"),
        Transform("upload", "known", "publication lag is measured from event end to HTTP Last-Modified"),
    )
    receipt = ConstraintReceipt(
        branch="satnogs",
        event_start=event_start,
        event_end=event_end,
        constraints=constraints,
        transforms=transforms,
        measurement_roots=station_roots,
        model_roots=model_roots,
        artifact_hashes=(left.sha256_hex, right.sha256_hex),
        caveats=(
            "same pass and carrier are control context, not independent identity evidence",
            "two hardware roots share SatNOGS software, storage, catalog, and Doppler method",
            "PNG supports residual constraints but not phase or calibrated IQ",
        ),
    )
    evidence = EvidenceEvent(
        source="satnogs-network",
        arrived_at=max(left.arrived_at, right.arrived_at),
        receipt=receipt,
    )
    belief = contract.snapshot_from_evidence(
        receipt,
        valid_at=now,
        clause_assessments=(
            ClauseAssessment(
                clause="measurement_availability",
                status=ClauseStatus.SATISFIED,
                statement="Two distinct station artifacts contain structured RF energy during one overlapping, model-conditioned observation window.",
                measurement_roots=station_roots,
            ),
            ClauseAssessment(
                clause="emitter_identity",
                status=ClauseStatus.UNRESOLVED,
                statement="The controlled job selects the case but does not prove emitter identity.",
                measurement_roots=station_roots,
            ),
        ),
        uncertainty=(
            "absolute frequency and power are not reconstructed from the PNG",
            "shared SatNOGS/model roots limit causal independence",
            "human good status is not additional physical evidence",
        ),
        active_model_roots=model_roots,
    )
    graph = _build_graph(observations, model_roots)
    return evidence, belief, graph


def run_probe_a(
    contract: DecisionContract,
    *,
    now: datetime | None = None,
) -> tuple[EvidenceEvent, BeliefSnapshot, CausalGraph]:
    now = datetime.now(timezone.utc) if now is None else now.astimezone(timezone.utc)
    emit_jsonl("intent_received", contract.intent)
    emit_jsonl("capability_probe", {"source": "satnogs", "ttl_s": contract.max_measurement_age_s})
    pairs = rank_fresh_pairs(fetch_recent_observations(now), contract, now)
    if not pairs:
        raise RuntimeError("no fresh two-station SatNOGS waterfall pair satisfies the contract")
    cache: dict[int, WaterfallArtifact] = {}
    for pair in pairs[:6]:
        for observation in pair:
            emit_jsonl(
                "capability_offer",
                {
                    "source": "satnogs",
                    "observation_id": observation.observation_id,
                    "station_id": observation.station_id,
                    "event_end": observation.end,
                    "expires_at": observation.end + timedelta(seconds=contract.max_measurement_age_s or 0),
                },
            )
        for observation in pair:
            if observation.observation_id not in cache:
                cache[observation.observation_id] = fetch_waterfall(observation)
        artifacts = tuple(cache[observation.observation_id] for observation in pair)
        for artifact in artifacts:
            emit_jsonl(
                "evidence_received",
                {
                    "observation_id": artifact.observation.observation_id,
                    "station_id": artifact.observation.station_id,
                    "event_start": artifact.observation.start,
                    "event_end": artifact.observation.end,
                    "arrived_at": artifact.arrived_at,
                    "published_at": artifact.published_at,
                    "bytes": artifact.content_length,
                    "sha256": artifact.sha256_hex,
                    "constraints": artifact.constraints,
                },
            )
        assimilation_now = datetime.now(timezone.utc)
        try:
            evidence, belief, graph = assimilate_satnogs_pair(
                contract,
                artifacts[0],
                artifacts[1],
                assimilation_now,
            )
        except ValueError as error:
            emit_jsonl(
                "evidence_rejected",
                {
                    "observation_ids": [item.observation.observation_id for item in artifacts],
                    "reason": str(error),
                },
            )
            continue
        emit_jsonl("evidence_assimilated", evidence.receipt)
        emit_jsonl("belief_updated", belief)
        emit_jsonl("causal_graph_snapshot", graph.snapshot())
        return evidence, belief, graph
    raise RuntimeError("fresh SatNOGS pairs were accessible but none contained two internally structured waterfalls")


def _waterfall_constraints(png: bytes) -> dict[str, Any]:
    with Image.open(BytesIO(png)) as image:
        rgb = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    nonwhite = np.any(rgb < 0.96, axis=2)
    column_ranges = _true_ranges(nonwhite.mean(axis=0) > 0.55)
    if not column_ranges:
        raise ValueError("could not locate waterfall plot in PNG")
    x0, x1 = max(column_ranges, key=lambda bounds: bounds[1] - bounds[0])
    row_ranges = _true_ranges(nonwhite[:, x0:x1].mean(axis=1) > 0.80)
    if not row_ranges:
        raise ValueError("could not locate waterfall time axis in PNG")
    y0, y1 = max(row_ranges, key=lambda bounds: bounds[1] - bounds[0])
    crop = rgb[y0:y1, x0:x1]
    luminance = 0.2126 * crop[:, :, 0] + 0.7152 * crop[:, :, 1] + 0.0722 * crop[:, :, 2]
    margin_y = max(2, int(0.02 * luminance.shape[0]))
    margin_x = max(2, int(0.02 * luminance.shape[1]))
    interior = luminance[margin_y:-margin_y, margin_x:-margin_x]
    # A single hot pixel is not RF structure. Requiring the 98th percentile to
    # rise above the row floor means at least a small spectral width supports
    # each detected time segment.
    row_contrast = np.quantile(interior, 0.98, axis=1) - np.quantile(interior, 0.25, axis=1)
    median = float(np.median(row_contrast))
    mad = float(np.median(np.abs(row_contrast - median))) + 1e-9
    structured_rows = row_contrast > median + 4.0 * mad
    segments = [
        [
            round((start + margin_y) / luminance.shape[0], 4),
            round((end + margin_y) / luminance.shape[0], 4),
        ]
        for start, end in _true_ranges(structured_rows)
        if end - start >= 1
    ]
    bright = interior >= np.quantile(interior, 0.995)
    column_weight = bright.sum(axis=0).astype(float)
    if column_weight.sum() == 0:
        residual_band = [-0.5, 0.5]
    else:
        cdf = np.cumsum(column_weight) / column_weight.sum()
        lo = int(np.searchsorted(cdf, 0.05))
        hi = int(np.searchsorted(cdf, 0.95))
        residual_band = [round(lo / len(column_weight) - 0.5, 4), round(hi / len(column_weight) - 0.5, 4)]
    return {
        "structured_time_fraction": round(float(structured_rows.mean()), 6),
        "structured_time_segments_image_fraction": segments,
        "bright_energy_band_normalized_from_center": residual_band,
        "plot_pixels": [int(crop.shape[1]), int(crop.shape[0])],
    }


def _true_ranges(mask: np.ndarray) -> list[tuple[int, int]]:
    padded = np.pad(mask.astype(np.int8), (1, 1))
    transitions = np.diff(padded)
    starts = np.flatnonzero(transitions == 1)
    ends = np.flatnonzero(transitions == -1)
    return [(int(start), int(end)) for start, end in zip(starts, ends)]


def _build_graph(
    observations: tuple[SatnogsObservation, SatnogsObservation],
    model_roots: tuple[str, ...],
) -> CausalGraph:
    graph = CausalGraph()
    for root in model_roots:
        graph.add_node(root, "model_root", root)
    for observation in observations:
        station = f"station:{observation.station_id}"
        evidence = f"evidence:satnogs:{observation.observation_id}"
        graph.add_node(station, "measurement_root", observation.station_name)
        graph.add_node(evidence, "evidence", observation.waterfall_url)
        graph.add_dependency(evidence, station, "received_by")
        for model_root in model_roots:
            graph.add_dependency(evidence, model_root, "conditioned_or_published_by")
    return graph


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 6371.0 * 2.0 * asin(sqrt(a))


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def main() -> None:
    contract = DecisionContract(
        intent=Intent(
            question="Is there fresh two-station RF evidence compatible with one controlled SatNOGS observation?",
            target="satellite selected only as SatNOGS control context",
        ),
        clauses=(
            DecisionClause(
                "measurement_availability",
                "fresh structured RF from two independent station roots",
                ("two_station_structured_rf", "event_time"),
                2,
            ),
            DecisionClause(
                "emitter_identity",
                "physical evidence independently supports emitter identity",
                ("identity_evidence",),
                2,
            ),
        ),
        max_measurement_age_s=600.0,
    )
    run_probe_a(contract)


if __name__ == "__main__":
    main()
