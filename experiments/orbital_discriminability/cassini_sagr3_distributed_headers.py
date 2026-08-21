"""Header-only qualification for the three frozen Cassini SAGR3 products.

The module requests and parses only the 260-byte SFDU control header from each
4,260-byte record.  Data CHDO bytes are outside the request ranges and no raw
header is retained.  This is a product-specific spike, not an RSR adapter.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
from typing import Final, Literal, Mapping, Sequence
import urllib.request

from experiments.orbital_discriminability.cassini_dss14_header_evaluation import (
    _read_exact_range_response,
)
from experiments.orbital_discriminability.cassini_dss26_rsr_header import (
    FilterDecimationState,
    NumericState,
    PolynomialState,
    RSR_HEADER_BYTES,
    RSR_RECORD_BYTES,
    _allowed_bytes_hash,
    _filter_decimation,
    _number,
    _required_number,
    _u16,
    _utc_tag,
    _validate_sfdu_structure,
)


PARSER_VERSION: Final = "cassini-sagr3-three-product-header-whitelist-v1"
QUALIFICATION_VERSION: Final = "cassini-sagr3-distributed-header-qualification-v1"
FROZEN_SCREEN_COMMIT: Final = "66aca45"
FROZEN_SCREEN_MANIFEST_SHA256: Final = (
    "f63812b2366d5952d3590eef0e43148aa6b92ec6159a9504f5f57b01bd375aa7"
)
HEADER_RANGES_PER_REQUEST: Final = 100
USER_AGENT: Final = "Satellite-RF-Observatory-SAGR3-header-only/1"

ProductRole = Literal[
    "MEASUREMENT_X_DSS25",
    "WITNESS_KA_DSS25",
    "MEASUREMENT_X_DSS65",
]


class CassiniDistributedHeaderError(ValueError):
    """A frozen product header or topology is malformed or out of scope."""


@dataclass(frozen=True, slots=True)
class DistributedProductSpec:
    role: ProductRole
    lidvid: str
    source_product_id: str
    label_sha256: str
    data_url: str
    published_md5: str
    file_bytes: int
    records: int
    first_sample_utc: str
    last_first_sample_utc: str
    downlink_band: Literal["X", "KA"]
    expected_station_id: int
    expected_rsr_id: int
    declared_channel_id: Literal["A", "B"]
    expected_subchannel_id: int
    causal_role: str


PRODUCTS: Final[Mapping[ProductRole, DistributedProductSpec]] = {
    "MEASUREMENT_X_DSS25": DistributedProductSpec(
        role="MEASUREMENT_X_DSS25",
        lidvid=(
            "urn:nasa:pds:cassini.rss.raw.sagr:data.rsr01:"
            "s23sags2006_251_1200x14x25rd::1.0"
        ),
        source_product_id=(
            "CO-S-RSS-1-SAGR3-V1.0:S23SAGS2006251_1200X14X25RD.2A1"
        ),
        label_sha256=(
            "f83b5c6bb499b99ae0139ccc6c3d45b61b112a8d865490b09a193c20ebae51bc"
        ),
        data_url=(
            "https://atmos.nmsu.edu/PDS/data/PDS4/cassini-rss-raw-sagr/"
            "data-rsr01/2006/s23sags2006_251_1200x14x25rd.dat"
        ),
        published_md5="2f62c3b792fd643124f1a7a7968eb549",
        file_bytes=37_800 * RSR_RECORD_BYTES,
        records=37_800,
        first_sample_utc="2006-09-08T12:00:01.000000Z",
        last_first_sample_utc="2006-09-08T22:30:00.000000Z",
        downlink_band="X",
        expected_station_id=25,
        expected_rsr_id=2,
        declared_channel_id="A",
        expected_subchannel_id=1,
        causal_role="DISTRIBUTED_X_MEASUREMENT_LEFT",
    ),
    "WITNESS_KA_DSS25": DistributedProductSpec(
        role="WITNESS_KA_DSS25",
        lidvid=(
            "urn:nasa:pds:cassini.rss.raw.sagr:data.rsr01:"
            "s23sags2006_251_1200x14k25rd::1.0"
        ),
        source_product_id=(
            "CO-S-RSS-1-SAGR3-V1.0:S23SAGS2006251_1200X14K25RD.2B1"
        ),
        label_sha256=(
            "f8c0712750421d54bbb9d996bcb91e5bb0f844f928d94ba779366b21ba33fef0"
        ),
        data_url=(
            "https://atmos.nmsu.edu/PDS/data/PDS4/cassini-rss-raw-sagr/"
            "data-rsr01/2006/s23sags2006_251_1200x14k25rd.dat"
        ),
        published_md5="e6bc1d5485d97c0069e7bd40d036b843",
        file_bytes=37_800 * RSR_RECORD_BYTES,
        records=37_800,
        first_sample_utc="2006-09-08T12:00:01.000000Z",
        last_first_sample_utc="2006-09-08T22:30:00.000000Z",
        downlink_band="KA",
        expected_station_id=25,
        expected_rsr_id=2,
        declared_channel_id="B",
        expected_subchannel_id=1,
        causal_role="SAME_PATH_DISPERSIVE_WITNESS",
    ),
    "MEASUREMENT_X_DSS65": DistributedProductSpec(
        role="MEASUREMENT_X_DSS65",
        lidvid=(
            "urn:nasa:pds:cassini.rss.raw.sagr:data.rsr01:"
            "s23sags2006_251_1200x14x65rd::1.0"
        ),
        source_product_id=(
            "CO-S-RSS-1-SAGR3-V1.0:S23SAGS2006251_1200X14X65RD.2A1"
        ),
        label_sha256=(
            "5e6e7861dcc71552d4b7bebb07c63f03e2cc8968b7b3c0028ef0b3715f7a4419"
        ),
        data_url=(
            "https://atmos.nmsu.edu/PDS/data/PDS4/cassini-rss-raw-sagr/"
            "data-rsr01/2006/s23sags2006_251_1200x14x65rd.dat"
        ),
        published_md5="34e11aaab5265be5a5ae33a99b7e5e67",
        file_bytes=16_800 * RSR_RECORD_BYTES,
        records=16_800,
        first_sample_utc="2006-09-08T12:00:01.000000Z",
        last_first_sample_utc="2006-09-08T16:40:00.000000Z",
        downlink_band="X",
        expected_station_id=65,
        expected_rsr_id=2,
        declared_channel_id="A",
        expected_subchannel_id=1,
        causal_role="DISTRIBUTED_X_MEASUREMENT_RIGHT",
    ),
}


@dataclass(frozen=True, slots=True)
class DistributedHeaderReceipt:
    parser_version: str
    product_role: ProductRole
    lidvid: str
    source_product_id: str
    downlink_band: str
    record_sequence_number: int
    first_sample_utc: str
    signal_processing_center_id: int
    deep_space_station_id: int
    station_id: str
    rsr_id: int
    channel_id: str
    subchannel_id: int
    sample_rate_hz: int
    sample_resolution_bits: int
    rf_to_if_lo_hz: int
    ddc_lo_hz: int
    frequency_override_active: bool
    predicts_time_shift_s: NumericState
    predicts_frequency_override_hz: NumericState
    predicts_frequency_rate_hz_s: NumericState
    predicts_frequency_offset_hz: NumericState
    subchannel_frequency_offset_hz: NumericState
    frequency_polynomial: PolynomialState
    accumulated_phase_cycles: NumericState
    phase_polynomial: PolynomialState
    filter_decimation: FilterDecimationState
    allowed_bytes_sha256: str

    def as_json_object(self) -> dict[str, object]:
        return asdict(self)


def parse_distributed_header(
    header: bytes | bytearray | memoryview,
    role: ProductRole,
) -> DistributedHeaderReceipt:
    """Parse exactly one whitelisted header for one frozen PDS product."""

    try:
        spec = PRODUCTS[role]
    except KeyError as error:
        raise CassiniDistributedHeaderError(
            "header role is outside the frozen three-product set"
        ) from error
    view = memoryview(header)
    if view.nbytes != RSR_HEADER_BYTES:
        raise CassiniDistributedHeaderError(
            f"expected exactly {RSR_HEADER_BYTES} SFDU header bytes"
        )
    try:
        _validate_sfdu_structure(view)
        year = _u16(view, 76)
        day_of_year = _u16(view, 78)
        second_of_day = _required_number(_number(view, 80), "first-sample second")
        sample_rate_hz = _u16(view, 70) * 1_000
        sample_resolution_bits = view[68]
        if sample_resolution_bits not in {1, 2, 4, 8, 16}:
            raise CassiniDistributedHeaderError("unsupported RSR sample resolution")
        receipt = DistributedHeaderReceipt(
            parser_version=PARSER_VERSION,
            product_role=role,
            lidvid=spec.lidvid,
            source_product_id=spec.source_product_id,
            downlink_band=spec.downlink_band,
            record_sequence_number=_u16(view, 40),
            first_sample_utc=_utc_tag(year, day_of_year, second_of_day),
            signal_processing_center_id=view[42],
            deep_space_station_id=view[43],
            station_id=f"DSS-{view[43]}",
            rsr_id=view[44],
            channel_id=spec.declared_channel_id,
            subchannel_id=view[45],
            sample_rate_hz=sample_rate_hz,
            sample_resolution_bits=sample_resolution_bits,
            rf_to_if_lo_hz=_u16(view, 74) * 1_000_000,
            ddc_lo_hz=_u16(view, 72) * 1_000_000,
            frequency_override_active=view[56] != 0,
            predicts_time_shift_s=_number(view, 88),
            predicts_frequency_override_hz=_number(view, 96),
            predicts_frequency_rate_hz_s=_number(view, 104),
            predicts_frequency_offset_hz=_number(view, 112),
            subchannel_frequency_offset_hz=_number(view, 120),
            frequency_polynomial=PolynomialState(
                tuple(_number(view, offset) for offset in (176, 184, 192)),
                "hertz",
                "F1 + F2*u + F3*u^2; u=(millisecond+0.5)/1000",
            ),
            accumulated_phase_cycles=_number(view, 200),
            phase_polynomial=PolynomialState(
                tuple(_number(view, offset) for offset in (208, 216, 224, 232)),
                "cycle",
                "P1 + P2*u + P3*u^2 + P4*u^3; u=(millisecond+0.5)/1000",
            ),
            filter_decimation=_filter_decimation(sample_rate_hz),
            allowed_bytes_sha256=_allowed_bytes_hash(view),
        )
    except ValueError as error:
        if isinstance(error, CassiniDistributedHeaderError):
            raise
        raise CassiniDistributedHeaderError(str(error)) from error
    expected_identity = (
        spec.expected_station_id,
        spec.expected_rsr_id,
        spec.expected_subchannel_id,
    )
    if (
        receipt.deep_space_station_id,
        receipt.rsr_id,
        receipt.subchannel_id,
    ) != expected_identity:
        raise CassiniDistributedHeaderError(
            "SFDU station/RSR/subchannel differs from the frozen PDS product identity"
        )
    if receipt.frequency_override_active:
        _required_number(
            receipt.predicts_frequency_override_hz,
            "active predicts-frequency override",
        )
    strict_json(receipt.as_json_object())
    return receipt


class _HeaderAccumulator:
    """Incrementally commit every allowed field without retaining headers."""

    def __init__(self, spec: DistributedProductSpec) -> None:
        self.spec = spec
        self.count = 0
        self.digest = sha256()
        self.first: DistributedHeaderReceipt | None = None
        self.previous: DistributedHeaderReceipt | None = None
        self.non_unit_rsn_steps = 0
        self.non_one_second_steps = 0
        self.max_nco_boundary_hz = 0.0
        self.unique: dict[str, set[object]] = {
            name: set()
            for name in (
                "signal_processing_center_id", "deep_space_station_id", "rsr_id",
                "channel_id", "subchannel_id", "sample_rate_hz",
                "sample_resolution_bits", "rf_to_if_lo_hz", "ddc_lo_hz",
                "frequency_override_active",
            )
        }
        self.numeric: dict[str, list[NumericState]] = {
            name: []
            for name in (
                "predicts_time_shift_s", "predicts_frequency_override_hz",
                "predicts_frequency_rate_hz_s", "predicts_frequency_offset_hz",
                "subchannel_frequency_offset_hz", "accumulated_phase_cycles",
            )
        }
        self.frequency_ranges = [[float("inf"), float("-inf")] for _ in range(3)]
        self.phase_ranges = [[float("inf"), float("-inf")] for _ in range(4)]

    def add(self, receipt: DistributedHeaderReceipt) -> None:
        if receipt.product_role != self.spec.role:
            raise CassiniDistributedHeaderError("receipt role changed within stream")
        encoded = strict_json(receipt.as_json_object()).encode("ascii")
        self.digest.update(encoded)
        self.digest.update(b"\n")
        instant = _parse_utc(receipt.first_sample_utc)
        if self.previous is not None:
            previous_instant = _parse_utc(self.previous.first_sample_utc)
            if (
                receipt.record_sequence_number - self.previous.record_sequence_number
            ) % 65_536 != 1:
                self.non_unit_rsn_steps += 1
            if (instant - previous_instant).total_seconds() != 1.0:
                self.non_one_second_steps += 1
            left = _finite_polynomial(self.previous.frequency_polynomial)
            right = _finite_polynomial(receipt.frequency_polynomial)
            boundary = _polynomial(right, 0.0005) - _polynomial(left, 1.0005)
            self.max_nco_boundary_hz = max(self.max_nco_boundary_hz, abs(boundary))
        if self.first is None:
            self.first = receipt
        self.previous = receipt
        self.count += 1
        for name, values in self.unique.items():
            values.add(getattr(receipt, name))
        for name, values in self.numeric.items():
            values.append(getattr(receipt, name))
        for target, polynomial in (
            (self.frequency_ranges, receipt.frequency_polynomial),
            (self.phase_ranges, receipt.phase_polynomial),
        ):
            for index, value in enumerate(_finite_polynomial(polynomial)):
                target[index][0] = min(target[index][0], value)
                target[index][1] = max(target[index][1], value)

    def finish(self) -> dict[str, object]:
        if self.first is None or self.previous is None:
            raise CassiniDistributedHeaderError("product returned no SFDU headers")
        if self.count != self.spec.records:
            raise CassiniDistributedHeaderError(
                "header count differs from the frozen PDS label"
            )
        if self.non_unit_rsn_steps or self.non_one_second_steps:
            raise CassiniDistributedHeaderError(
                "complete product header grid is discontinuous"
            )
        if (
            self.first.first_sample_utc != self.spec.first_sample_utc
            or self.previous.first_sample_utc != self.spec.last_first_sample_utc
        ):
            raise CassiniDistributedHeaderError(
                "header time endpoints differ from the frozen PDS label"
            )
        return {
            "role": self.spec.role,
            "lidvid": self.spec.lidvid,
            "source_product_id": self.spec.source_product_id,
            "record_count": self.count,
            "ordered_whitelist_receipts_sha256": self.digest.hexdigest(),
            "event_time": {
                "first_sample_utc": self.first.first_sample_utc,
                "last_first_sample_utc": self.previous.first_sample_utc,
                "non_one_second_steps": self.non_one_second_steps,
            },
            "record_sequence": {
                "first": self.first.record_sequence_number,
                "last": self.previous.record_sequence_number,
                "non_unit_steps_modulo_65536": self.non_unit_rsn_steps,
            },
            "identity_and_sample_mode": {
                name: sorted(values) for name, values in self.unique.items()
            },
            "filter_decimation": asdict(self.first.filter_decimation),
            "predicts_fields": {
                name: _numeric_summary(values) for name, values in self.numeric.items()
            },
            "frequency_polynomial_coefficient_ranges_hz": [
                {"minimum": row[0], "maximum": row[1]}
                for row in self.frequency_ranges
            ],
            "frequency_polynomial_maximum_absolute_boundary_residual_hz": (
                self.max_nco_boundary_hz
            ),
            "phase_polynomial_coefficient_ranges_cycles": [
                {"minimum": row[0], "maximum": row[1]} for row in self.phase_ranges
            ],
            "raw_header_retained": False,
            "data_chdo_bytes_requested": 0,
            "data_chdo_bytes_read": 0,
        }


def fetch_and_summarize_product(role: ProductRole) -> dict[str, object]:
    """Fetch every exact header range, parse in RAM, then destroy raw bytes."""

    spec = PRODUCTS[role]
    accumulator = _HeaderAccumulator(spec)
    for first_index in range(0, spec.records, HEADER_RANGES_PER_REQUEST):
        indices = tuple(
            range(first_index, min(first_index + HEADER_RANGES_PER_REQUEST, spec.records))
        )
        ranges = tuple(
            (index * RSR_RECORD_BYTES, index * RSR_RECORD_BYTES + RSR_HEADER_BYTES - 1)
            for index in indices
        )
        request = urllib.request.Request(
            spec.data_url,
            headers={
                "Range": "bytes=" + ",".join(
                    f"{start}-{end}" for start, end in ranges
                ),
                "User-Agent": USER_AGENT,
            },
        )
        response = urllib.request.urlopen(request, timeout=60)
        try:
            parts = _read_exact_range_response(response, ranges, spec.file_bytes)
        finally:
            response.close()
        for index in indices:
            key = (
                index * RSR_RECORD_BYTES,
                index * RSR_RECORD_BYTES + RSR_HEADER_BYTES - 1,
            )
            raw = bytearray(parts.pop(key))
            try:
                accumulator.add(parse_distributed_header(raw, role))
            finally:
                raw[:] = bytes(len(raw))
        if parts:
            raise CassiniDistributedHeaderError(
                "server returned an unauthorized extra byte range"
            )
    return accumulator.finish()


def qualify_topology(
    summaries: Mapping[ProductRole, Mapping[str, object]],
) -> dict[str, object]:
    """Evaluate only the predeclared causal topology after stream admission."""

    if set(summaries) != set(PRODUCTS):
        raise CassiniDistributedHeaderError("all three frozen streams are required")
    left = summaries["MEASUREMENT_X_DSS25"]
    witness = summaries["WITNESS_KA_DSS25"]
    right = summaries["MEASUREMENT_X_DSS65"]
    left_identity = _single_identity(left)
    witness_identity = _single_identity(witness)
    right_identity = _single_identity(right)
    dss25_simultaneous = left["event_time"] == witness["event_time"]
    x_common_start = (
        left["event_time"]["first_sample_utc"]
        == right["event_time"]["first_sample_utc"]
    )
    dss25_distinct_channels = (
        left_identity[0:3] == witness_identity[0:3]
        and left_identity[3] != witness_identity[3]
        and left_identity[4] == witness_identity[4]
    )
    independent_x_roots = left_identity[1] != right_identity[1]
    clauses = {
        "all_streams_complete_and_continuous": all(
            summary["event_time"]["non_one_second_steps"] == 0
            and summary["record_sequence"]["non_unit_steps_modulo_65536"] == 0
            for summary in summaries.values()
        ),
        "dss25_x_ka_simultaneous": dss25_simultaneous,
        "dss25_x_ka_distinct_receiver_channels": dss25_distinct_channels,
        "dss25_dss65_x_independent_receive_roots": independent_x_roots,
        "distributed_x_common_start_and_overlap": x_common_start,
    }
    admitted = all(clauses.values())
    return {
        "clauses": clauses,
        "topology": {
            "shared_upstream": [
                "DSS-14 X-band uplink",
                "Cassini coherent transponder",
                "interplanetary path before Earth-near divergence",
            ],
            "independent_x_receive_roots": ["DSS-25", "DSS-65"],
            "dss25_same_path_witness": {
                "shared_station_and_rsr": True,
                "independent_channels": ["2A1", "2B1"],
                "counts_as_third_measurement_root": False,
            },
        },
        "outcome": (
            "CASSINI_SAGR3_HEADER_TOPOLOGY_QUALIFIED"
            if admitted
            else "NO_ADMISSIBLE_DISTRIBUTED_HEADER_TOPOLOGY"
        ),
        "physical_margin_admitted": False,
        "iq_access_authorized": False,
        "detector_authorized": False,
    }


def run_header_qualification(source_commit: str) -> dict[str, object]:
    if not source_commit:
        raise CassiniDistributedHeaderError("pre-access source commit is required")
    summaries = {
        role: fetch_and_summarize_product(role) for role in PRODUCTS
    }
    topology = qualify_topology(summaries)
    result = {
        "qualification_version": QUALIFICATION_VERSION,
        "authority": {
            "source_commit": source_commit,
            "frozen_screen_commit": FROZEN_SCREEN_COMMIT,
            "frozen_screen_manifest_sha256": FROZEN_SCREEN_MANIFEST_SHA256,
            "parser_manifest_sha256": parser_manifest_sha256(),
            "parser_source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        },
        "products": [summaries[role] for role in PRODUCTS],
        "topology_qualification": topology,
        "access_boundary": {
            "sfdu_header_bytes_requested_and_read": sum(
                spec.records * RSR_HEADER_BYTES for spec in PRODUCTS.values()
            ),
            "data_chdo_bytes_requested": 0,
            "data_chdo_bytes_read": 0,
            "raw_headers_persisted": False,
            "iq_or_amplitude_fields_represented": False,
        },
        "outcome": topology["outcome"],
        "next_physical_step": (
            "BOUND_DISTRIBUTED_PHYSICAL_ENVELOPE_ON_THE_EXACT_REAL_NCO_GRIDS"
            if topology["outcome"] == "CASSINI_SAGR3_HEADER_TOPOLOGY_QUALIFIED"
            else "ABANDON_THIS_THREE_PRODUCT_MEASUREMENT_PATH"
        ),
    }
    strict_json(result)
    return result


def parser_manifest() -> dict[str, object]:
    return {
        "parser_version": PARSER_VERSION,
        "scope": "EXACTLY_THREE_FROZEN_CASSINI_SAGR3_PRODUCTS",
        "frozen_screen_commit": FROZEN_SCREEN_COMMIT,
        "frozen_screen_manifest_sha256": FROZEN_SCREEN_MANIFEST_SHA256,
        "products": [asdict(PRODUCTS[role]) for role in PRODUCTS],
        "header_bytes": RSR_HEADER_BYTES,
        "record_bytes": RSR_RECORD_BYTES,
        "ranges_per_request": HEADER_RANGES_PER_REQUEST,
        "channel_lineage": "PDS_EXTERNAL_SOURCE_PRODUCT_IDENTIFIER_SUFFIX",
        "station_rsr_subchannel_lineage": "WHITELISTED_SFDU_BYTES_43_45",
        "sample_mode": {
            "layout": "PDS_LABEL_DECLARED_COMPLEX_Q_THEN_I_WORD",
            "resolution": "SFDU_BYTE_68",
            "sample_rate": "SFDU_BYTES_70_71_KSPS",
        },
        "raw_header_retention": "PROHIBITED",
        "data_chdo_access": "PROHIBITED",
        "signal_or_sample_diagnostics": "NOT_REPRESENTABLE",
        "utc_policy": (
            "ordinary UTC only; encoded leap-second boundary is rejected, never normalized"
        ),
        "qualification_claim": (
            "CONTROL_PATH_CONTINUITY_AND_CAUSAL_TOPOLOGY_ONLY_NO_RF_CLAIM"
        ),
    }


def parser_manifest_sha256() -> str:
    return sha256(strict_json(parser_manifest()).encode("ascii")).hexdigest()


def strict_json(value: object) -> str:
    return json.dumps(
        value, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    )


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _finite_polynomial(polynomial: PolynomialState) -> tuple[float, ...]:
    values = tuple(value.value for value in polynomial.coefficients)
    if any(value is None or not isfinite(value) for value in values):
        raise CassiniDistributedHeaderError(
            "required receiver polynomial contains a non-calculable coefficient"
        )
    return tuple(float(value) for value in values)


def _polynomial(coefficients: Sequence[float], u: float) -> float:
    return sum(value * u**power for power, value in enumerate(coefficients))


def _numeric_summary(values: Sequence[NumericState]) -> dict[str, object]:
    states = sorted({value.state for value in values})
    finite = [float(value.value) for value in values if value.value is not None]
    return {
        "states": states,
        "finite_minimum": min(finite) if finite else None,
        "finite_maximum": max(finite) if finite else None,
    }


def _single_identity(summary: Mapping[str, object]) -> tuple[object, ...]:
    fields = summary["identity_and_sample_mode"]
    names = (
        "signal_processing_center_id", "deep_space_station_id", "rsr_id",
        "channel_id", "subchannel_id",
    )
    result = []
    for name in names:
        values = fields[name]
        if len(values) != 1:
            raise CassiniDistributedHeaderError(
                f"identity field changed within stream: {name}"
            )
        result.append(values[0])
    return tuple(result)
