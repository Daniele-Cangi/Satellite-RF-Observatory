"""Amplitude-blind SFDU qualification for the frozen 2005 Cassini pair.

Only the 260-byte control header of each record intersecting the frozen
post-media window may be requested. A server response that does not prove the
exact HTTP byte ranges is rejected before its body is read. Data CHDO, samples,
amplitude, signal strength, and signal-derived diagnostics are structurally
outside this module.
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


PARSER_VERSION: Final = "cassini-sroc-2005-dual-root-four-stream-header-v1"
QUALIFICATION_VERSION: Final = "cassini-sroc-2005-header-qualification-v1"
FROZEN_SELECTION_COMMIT: Final = (
    "8c18f82f8c26d09f1545eb98838617aa55b1e6e2"
)
FROZEN_SELECTION_MANIFEST_SHA256: Final = (
    "9f0f409e2067820578ad8c586213ee8fee1288465c99065f2453c1742053ce69"
)
FROZEN_WINDOW_START_UTC: Final = "2005-06-08T19:17:00.000000Z"
FROZEN_WINDOW_STOP_UTC: Final = "2005-06-08T20:44:59.000000Z"
FROZEN_WINDOW_RECORDS: Final = 5_280
HEADER_RANGES_PER_REQUEST: Final = 100
USER_AGENT: Final = "Satellite-RF-Observatory-SROC2005-header-only/1"

ProductRole = Literal["DSS25_X", "DSS25_KA", "DSS55_X", "DSS55_KA"]


class CassiniDualRootHeaderError(ValueError):
    """A frozen product header or its causal topology is out of scope."""


@dataclass(frozen=True, slots=True)
class ProductSpec:
    role: ProductRole
    lidvid: str
    source_product_id: str
    label_sha256: str
    label_bytes: int
    data_url: str
    published_md5: str
    file_bytes: int
    full_product_records: int
    window_first_record_index: int
    window_records: int
    window_first_sample_utc: str
    window_last_first_sample_utc: str
    downlink_band: Literal["X", "KA"]
    expected_station_id: int
    declared_channel_id: Literal["A", "B"]
    expected_subchannel_id: int
    causal_role: str


_BASE_URL: Final = (
    "https://atmos.nmsu.edu/PDS/data/PDS4/"
    "cassini-rss-raw-sroc/data-rsr01/2005/"
)

PRODUCTS: Final[Mapping[ProductRole, ProductSpec]] = {
    "DSS25_X": ProductSpec(
        role="DSS25_X",
        lidvid=(
            "urn:nasa:pds:cassini.rss.raw.sroc:data.rsr01:"
            "s11sroe2005_159_1715nnnx25rd::1.0"
        ),
        source_product_id=(
            "CO-S-RSS-1-SROC1-V1.0:S11SROE2005159_1715NNNX25RD.1A1"
        ),
        label_sha256=(
            "74ad0b7c1911ac7567843dd576263fc3e7aa19cda2b484cb78610fc7a4d76d5e"
        ),
        label_bytes=73_345,
        data_url=_BASE_URL + "s11sroe2005_159_1715nnnx25rd.dat",
        published_md5="74e093f68b55aa95481793840fc497ac",
        file_bytes=53_680_260,
        full_product_records=12_601,
        window_first_record_index=7_320,
        window_records=FROZEN_WINDOW_RECORDS,
        window_first_sample_utc=FROZEN_WINDOW_START_UTC,
        window_last_first_sample_utc=FROZEN_WINDOW_STOP_UTC,
        downlink_band="X",
        expected_station_id=25,
        declared_channel_id="A",
        expected_subchannel_id=1,
        causal_role="DISTRIBUTED_X_MEASUREMENT_LEFT",
    ),
    "DSS25_KA": ProductSpec(
        role="DSS25_KA",
        lidvid=(
            "urn:nasa:pds:cassini.rss.raw.sroc:data.rsr01:"
            "s11sroe2005_159_1715nnnk25rd::1.0"
        ),
        source_product_id=(
            "CO-S-RSS-1-SROC1-V1.0:S11SROE2005159_1715NNNK25RD.1B1"
        ),
        label_sha256=(
            "a785a4c803b4b66aaa5b585e98834e7141fdb9405c10eef8acab0165ecd371c4"
        ),
        label_bytes=73_345,
        data_url=_BASE_URL + "s11sroe2005_159_1715nnnk25rd.dat",
        published_md5="ba42b0cb354a93b8c7b6b805bb34aa0c",
        file_bytes=53_676_000,
        full_product_records=12_600,
        window_first_record_index=7_319,
        window_records=FROZEN_WINDOW_RECORDS,
        window_first_sample_utc=FROZEN_WINDOW_START_UTC,
        window_last_first_sample_utc=FROZEN_WINDOW_STOP_UTC,
        downlink_band="KA",
        expected_station_id=25,
        declared_channel_id="B",
        expected_subchannel_id=1,
        causal_role="DSS25_SAME_PATH_DISPERSIVE_WITNESS",
    ),
    "DSS55_X": ProductSpec(
        role="DSS55_X",
        lidvid=(
            "urn:nasa:pds:cassini.rss.raw.sroc:data.rsr01:"
            "s11sroe2005_159_1715nnnx55rd::1.0"
        ),
        source_product_id=(
            "CO-S-RSS-1-SROC1-V1.0:S11SROE2005159_1715NNNX55RD.1A1"
        ),
        label_sha256=(
            "fd135f96ca3f3d1e0d21aef09c3e50f13a624b42291977cfffa5abce0cd09cfe"
        ),
        label_bytes=73_342,
        data_url=_BASE_URL + "s11sroe2005_159_1715nnnx55rd.dat",
        published_md5="8904afec54ba0cbe63f0471fc33f07dc",
        file_bytes=53_676_000,
        full_product_records=12_600,
        window_first_record_index=7_320,
        window_records=FROZEN_WINDOW_RECORDS,
        window_first_sample_utc=FROZEN_WINDOW_START_UTC,
        window_last_first_sample_utc=FROZEN_WINDOW_STOP_UTC,
        downlink_band="X",
        expected_station_id=55,
        declared_channel_id="A",
        expected_subchannel_id=1,
        causal_role="DISTRIBUTED_X_MEASUREMENT_RIGHT",
    ),
    "DSS55_KA": ProductSpec(
        role="DSS55_KA",
        lidvid=(
            "urn:nasa:pds:cassini.rss.raw.sroc:data.rsr01:"
            "s11sroe2005_159_1715nnnk55rd::1.0"
        ),
        source_product_id=(
            "CO-S-RSS-1-SROC1-V1.0:S11SROE2005159_1715NNNK55RD.1B1"
        ),
        label_sha256=(
            "8cbcea9512d103d2992738e98b5b5c72ce44f1888415436c0d5f39e555ec61c2"
        ),
        label_bytes=73_342,
        data_url=_BASE_URL + "s11sroe2005_159_1715nnnk55rd.dat",
        published_md5="44831c3d9d149ee56fbda762fe0ff1d9",
        file_bytes=53_680_260,
        full_product_records=12_601,
        window_first_record_index=7_320,
        window_records=FROZEN_WINDOW_RECORDS,
        window_first_sample_utc=FROZEN_WINDOW_START_UTC,
        window_last_first_sample_utc=FROZEN_WINDOW_STOP_UTC,
        downlink_band="KA",
        expected_station_id=55,
        declared_channel_id="B",
        expected_subchannel_id=1,
        causal_role="DSS55_SAME_PATH_DISPERSIVE_WITNESS",
    ),
}


@dataclass(frozen=True, slots=True)
class HeaderReceipt:
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


def parse_header(
    header: bytes | bytearray | memoryview,
    role: ProductRole,
) -> HeaderReceipt:
    """Parse exactly one whitelisted SFDU header for one frozen product."""

    try:
        spec = PRODUCTS[role]
    except KeyError as error:
        raise CassiniDualRootHeaderError(
            "header role is outside the frozen four-product set"
        ) from error
    view = memoryview(header)
    if view.nbytes != RSR_HEADER_BYTES:
        raise CassiniDualRootHeaderError(
            f"expected exactly {RSR_HEADER_BYTES} SFDU header bytes"
        )
    try:
        _validate_sfdu_structure(view)
        year = _u16(view, 76)
        day_of_year = _u16(view, 78)
        second_of_day = _required_number(
            _number(view, 80), "first-sample second"
        )
        sample_rate_hz = _u16(view, 70) * 1_000
        sample_resolution_bits = view[68]
        if sample_resolution_bits not in {1, 2, 4, 8, 16}:
            raise CassiniDualRootHeaderError(
                "unsupported RSR sample resolution"
            )
        receipt = HeaderReceipt(
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
                tuple(
                    _number(view, offset)
                    for offset in (208, 216, 224, 232)
                ),
                "cycle",
                "P1 + P2*u + P3*u^2 + P4*u^3; "
                "u=(millisecond+0.5)/1000",
            ),
            filter_decimation=_filter_decimation(sample_rate_hz),
            allowed_bytes_sha256=_allowed_bytes_hash(view),
        )
    except ValueError as error:
        if isinstance(error, CassiniDualRootHeaderError):
            raise
        raise CassiniDualRootHeaderError(str(error)) from error
    if (
        receipt.deep_space_station_id != spec.expected_station_id
        or receipt.subchannel_id != spec.expected_subchannel_id
        or receipt.rsr_id == 0
    ):
        raise CassiniDualRootHeaderError(
            "SFDU station/subchannel is out of scope or RSR identity is zero"
        )
    if receipt.frequency_override_active:
        _required_number(
            receipt.predicts_frequency_override_hz,
            "active predicts-frequency override",
        )
    strict_json(receipt.as_json_object())
    return receipt


class _Accumulator:
    """Commit allowed control fields incrementally without retaining headers."""

    def __init__(self, spec: ProductSpec) -> None:
        self.spec = spec
        self.count = 0
        self.digest = sha256()
        self.first: HeaderReceipt | None = None
        self.previous: HeaderReceipt | None = None
        self.non_unit_rsn_steps = 0
        self.non_one_second_steps = 0
        self.ddc_lo_change_count = 0
        self.rf_to_if_lo_change_count = 0
        self.override_state_change_count = 0
        self.max_nco_boundary_hz = 0.0
        self.max_transform_boundary_hz = 0.0
        self.unique: dict[str, set[object]] = {
            name: set()
            for name in (
                "signal_processing_center_id",
                "deep_space_station_id",
                "rsr_id",
                "channel_id",
                "subchannel_id",
                "sample_rate_hz",
                "sample_resolution_bits",
                "rf_to_if_lo_hz",
                "ddc_lo_hz",
                "frequency_override_active",
            )
        }
        self.numeric: dict[str, list[NumericState]] = {
            name: []
            for name in (
                "predicts_time_shift_s",
                "predicts_frequency_override_hz",
                "predicts_frequency_rate_hz_s",
                "predicts_frequency_offset_hz",
                "subchannel_frequency_offset_hz",
                "accumulated_phase_cycles",
            )
        }
        self.frequency_ranges = [
            [float("inf"), float("-inf")] for _ in range(3)
        ]
        self.phase_ranges = [
            [float("inf"), float("-inf")] for _ in range(4)
        ]

    def add(self, receipt: HeaderReceipt) -> None:
        if receipt.product_role != self.spec.role:
            raise CassiniDualRootHeaderError(
                "receipt role changed within stream"
            )
        self.digest.update(
            strict_json(receipt.as_json_object()).encode("ascii")
        )
        self.digest.update(b"\n")
        instant = _parse_utc(receipt.first_sample_utc)
        if self.previous is not None:
            previous_instant = _parse_utc(self.previous.first_sample_utc)
            rsn_step = (
                receipt.record_sequence_number
                - self.previous.record_sequence_number
            ) % 65_536
            self.non_unit_rsn_steps += rsn_step != 1
            self.non_one_second_steps += (
                instant - previous_instant
            ).total_seconds() != 1.0
            previous_frequency = _finite_polynomial(
                self.previous.frequency_polynomial
            )
            frequency = _finite_polynomial(
                receipt.frequency_polynomial
            )
            previous_nco = _polynomial(previous_frequency, 1.0005)
            nco = _polynomial(frequency, 0.0005)
            self.max_nco_boundary_hz = max(
                self.max_nco_boundary_hz, abs(nco - previous_nco)
            )
            previous_transform = (
                -self.previous.rf_to_if_lo_hz
                - self.previous.ddc_lo_hz
                + previous_nco
            )
            transform = (
                -receipt.rf_to_if_lo_hz - receipt.ddc_lo_hz + nco
            )
            self.max_transform_boundary_hz = max(
                self.max_transform_boundary_hz,
                abs(transform - previous_transform),
            )
            self.ddc_lo_change_count += (
                receipt.ddc_lo_hz != self.previous.ddc_lo_hz
            )
            self.rf_to_if_lo_change_count += (
                receipt.rf_to_if_lo_hz
                != self.previous.rf_to_if_lo_hz
            )
            self.override_state_change_count += (
                receipt.frequency_override_active
                != self.previous.frequency_override_active
            )
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
            raise CassiniDualRootHeaderError(
                "product returned no SFDU headers"
            )
        if self.count != self.spec.window_records:
            raise CassiniDualRootHeaderError(
                "header count differs from the frozen window"
            )
        if self.non_unit_rsn_steps or self.non_one_second_steps:
            raise CassiniDualRootHeaderError(
                "frozen product window is discontinuous"
            )
        if (
            self.first.first_sample_utc
            != self.spec.window_first_sample_utc
            or self.previous.first_sample_utc
            != self.spec.window_last_first_sample_utc
        ):
            raise CassiniDualRootHeaderError(
                "header time endpoints differ from the frozen window"
            )
        return {
            "role": self.spec.role,
            "lidvid": self.spec.lidvid,
            "source_product_id": self.spec.source_product_id,
            "downlink_band": self.spec.downlink_band,
            "causal_role": self.spec.causal_role,
            "window_record_count": self.count,
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
                name: sorted(values)
                for name, values in self.unique.items()
            },
            "filter_decimation": asdict(self.first.filter_decimation),
            "predicts_fields": {
                name: _numeric_summary(values)
                for name, values in self.numeric.items()
            },
            "frequency_polynomial_coefficient_ranges_hz": [
                {"minimum": row[0], "maximum": row[1]}
                for row in self.frequency_ranges
            ],
            "phase_polynomial_coefficient_ranges_cycles": [
                {"minimum": row[0], "maximum": row[1]}
                for row in self.phase_ranges
            ],
            "receiver_frequency_transform": {
                "equation": (
                    "recorded_baseband = sky - RF_TO_IF_LO - DDC_LO + NCO"
                ),
                "ddc_lo_change_count": self.ddc_lo_change_count,
                "rf_to_if_lo_change_count": (
                    self.rf_to_if_lo_change_count
                ),
                "frequency_override_state_change_count": (
                    self.override_state_change_count
                ),
                "maximum_absolute_nco_boundary_residual_hz": (
                    self.max_nco_boundary_hz
                ),
                "maximum_absolute_transform_boundary_residual_hz": (
                    self.max_transform_boundary_hz
                ),
                "finite_and_explicit_on_every_record": True,
            },
            "raw_header_retained": False,
            "data_chdo_bytes_requested": 0,
            "data_chdo_bytes_read": 0,
        }


def fetch_and_summarize_product(role: ProductRole) -> dict[str, object]:
    """Fetch only exact 260-byte ranges, parse in RAM, then zero buffers."""

    spec = PRODUCTS[role]
    accumulator = _Accumulator(spec)
    first = spec.window_first_record_index
    stop = first + spec.window_records
    for batch_start in range(first, stop, HEADER_RANGES_PER_REQUEST):
        indices = tuple(
            range(
                batch_start,
                min(batch_start + HEADER_RANGES_PER_REQUEST, stop),
            )
        )
        ranges = tuple(
            (
                index * RSR_RECORD_BYTES,
                index * RSR_RECORD_BYTES + RSR_HEADER_BYTES - 1,
            )
            for index in indices
        )
        request = urllib.request.Request(
            spec.data_url,
            headers={
                "Range": "bytes="
                + ",".join(f"{start}-{end}" for start, end in ranges),
                "User-Agent": USER_AGENT,
            },
        )
        response = urllib.request.urlopen(request, timeout=60)
        try:
            parts = _read_exact_range_response(
                response, ranges, spec.file_bytes
            )
        finally:
            response.close()
        for index in indices:
            key = (
                index * RSR_RECORD_BYTES,
                index * RSR_RECORD_BYTES + RSR_HEADER_BYTES - 1,
            )
            raw = bytearray(parts.pop(key))
            try:
                accumulator.add(parse_header(raw, role))
            finally:
                raw[:] = bytes(len(raw))
        if parts:
            raise CassiniDualRootHeaderError(
                "server returned an unauthorized extra byte range"
            )
    return accumulator.finish()


def qualify_header_path(
    summaries: Mapping[ProductRole, Mapping[str, object]],
) -> dict[str, object]:
    """Evaluate only the frozen four-stream causal and control topology."""

    if set(summaries) != set(PRODUCTS):
        raise CassiniDualRootHeaderError(
            "all four frozen streams are required"
        )
    identities = {
        role: _single_identity(summary)
        for role, summary in summaries.items()
    }
    event_times = [
        summary["event_time"] for summary in summaries.values()
    ]
    clauses = {
        "all_streams_complete_and_continuous": all(
            summary["event_time"]["non_one_second_steps"] == 0
            and summary["record_sequence"][
                "non_unit_steps_modulo_65536"
            ]
            == 0
            for summary in summaries.values()
        ),
        "four_stream_common_header_grid": all(
            event_time == event_times[0] for event_time in event_times
        ),
        "independent_receive_roots": (
            identities["DSS25_X"][1] != identities["DSS55_X"][1]
        ),
        "dss25_x_ka_distinct_channels": _distinct_x_ka(
            identities["DSS25_X"], identities["DSS25_KA"]
        ),
        "dss55_x_ka_distinct_channels": _distinct_x_ka(
            identities["DSS55_X"], identities["DSS55_KA"]
        ),
        "all_receiver_transforms_finite": all(
            summary["receiver_frequency_transform"][
                "finite_and_explicit_on_every_record"
            ]
            for summary in summaries.values()
        ),
        "no_discrete_lo_ddc_or_override_transition": all(
            summary["receiver_frequency_transform"][
                "ddc_lo_change_count"
            ]
            == 0
            and summary["receiver_frequency_transform"][
                "rf_to_if_lo_change_count"
            ]
            == 0
            and summary["receiver_frequency_transform"][
                "frequency_override_state_change_count"
            ]
            == 0
            for summary in summaries.values()
        ),
    }
    admitted = all(clauses.values())
    return {
        "clauses": clauses,
        "topology": {
            "shared_upstream": [
                "Cassini USO and one-way downlink generation",
                "interplanetary path before Earth-near divergence",
            ],
            "independent_receive_roots": ["DSS-25", "DSS-55"],
            "same_path_dispersive_witnesses": {
                "DSS-25": ["X channel A", "Ka channel B"],
                "DSS-55": ["X channel A", "Ka channel B"],
            },
            "witnesses_count_as_additional_receive_roots": False,
        },
        "outcome": (
            "CASSINI_DUAL_ROOT_HEADER_PATH_QUALIFIED"
            if admitted
            else "NO_ADMISSIBLE_DUAL_ROOT_HEADER_PATH"
        ),
        "physical_margin_admitted": False,
        "forward_experiment_frozen": False,
        "iq_access_authorized": False,
    }


def build_qualification(
    summaries: Mapping[ProductRole, Mapping[str, object]],
    *,
    source_commit: str,
) -> dict[str, object]:
    if len(source_commit) != 40:
        raise CassiniDualRootHeaderError(
            "full pre-access source commit is required"
        )
    topology = qualify_header_path(summaries)
    result = {
        "qualification_version": QUALIFICATION_VERSION,
        "authority": {
            "source_commit": source_commit,
            "frozen_selection_commit": FROZEN_SELECTION_COMMIT,
            "frozen_selection_manifest_sha256": (
                FROZEN_SELECTION_MANIFEST_SHA256
            ),
            "parser_manifest_sha256": parser_manifest_sha256(),
            "canonical_parser_source_sha256": (
                canonical_parser_source_sha256()
            ),
        },
        "frozen_window": {
            "first_sample_utc": FROZEN_WINDOW_START_UTC,
            "last_first_sample_utc": FROZEN_WINDOW_STOP_UTC,
            "records_per_stream": FROZEN_WINDOW_RECORDS,
        },
        "products": [summaries[role] for role in PRODUCTS],
        "topology_qualification": topology,
        "access_boundary": {
            "sfdu_header_bytes_requested_and_read": (
                len(PRODUCTS)
                * FROZEN_WINDOW_RECORDS
                * RSR_HEADER_BYTES
            ),
            "data_chdo_bytes_requested": 0,
            "data_chdo_bytes_read": 0,
            "raw_headers_persisted": False,
            "iq_or_amplitude_fields_represented": False,
        },
        "outcome": topology["outcome"],
        "next_physical_step": (
            "COMPILE_EXACT_X_KA_COMPOSITE_AND_BOUND_PHYSICAL_ENVELOPE"
            if topology["outcome"]
            == "CASSINI_DUAL_ROOT_HEADER_PATH_QUALIFIED"
            else "ABANDON_2005_DUAL_ROOT_MEASUREMENT_PATH"
        ),
    }
    strict_json(result)
    return result


def run_header_qualification(source_commit: str) -> dict[str, object]:
    summaries = {
        role: fetch_and_summarize_product(role) for role in PRODUCTS
    }
    return build_qualification(summaries, source_commit=source_commit)


def parser_manifest() -> dict[str, object]:
    return {
        "parser_version": PARSER_VERSION,
        "scope": "EXACTLY_FOUR_FROZEN_SROC_2005_PRODUCTS_AND_WINDOW",
        "frozen_selection_commit": FROZEN_SELECTION_COMMIT,
        "frozen_selection_manifest_sha256": (
            FROZEN_SELECTION_MANIFEST_SHA256
        ),
        "products": [asdict(PRODUCTS[role]) for role in PRODUCTS],
        "header_bytes": RSR_HEADER_BYTES,
        "record_bytes": RSR_RECORD_BYTES,
        "ranges_per_request": HEADER_RANGES_PER_REQUEST,
        "window": {
            "first_sample_utc": FROZEN_WINDOW_START_UTC,
            "last_first_sample_utc": FROZEN_WINDOW_STOP_UTC,
            "records_per_stream": FROZEN_WINDOW_RECORDS,
        },
        "channel_lineage": (
            "PDS_EXTERNAL_SOURCE_PRODUCT_IDENTIFIER_SUFFIX_A_OR_B"
        ),
        "rsr_lineage": (
            "SFDU_BYTE_44_ONLY; SOURCE_SUFFIX_NUMBER_IS_NOT_ASSUMED_RSR"
        ),
        "station_rsr_subchannel_lineage": (
            "WHITELISTED_SFDU_BYTES_43_45"
        ),
        "sample_mode": {
            "layout": "PDS_LABEL_DECLARED_COMPLEX_Q_THEN_I_WORD",
            "resolution": "SFDU_BYTE_68",
            "sample_rate": "SFDU_BYTES_70_71_KSPS",
        },
        "admission_invariant": (
            "NO_DISCRETE_RF_LO_DDC_OR_OVERRIDE_STATE_TRANSITION"
        ),
        "raw_header_retention": "PROHIBITED",
        "data_chdo_access": "PROHIBITED",
        "signal_or_sample_diagnostics": "NOT_REPRESENTABLE",
        "http_policy": (
            "EXACT_206_CONTENT_RANGE_VERIFIED_BEFORE_BOUNDED_BODY_READ"
        ),
        "utc_policy": (
            "ordinary UTC only; encoded leap-second boundary is rejected"
        ),
        "qualification_claim": (
            "CONTROL_PATH_CONTINUITY_AND_CAUSAL_TOPOLOGY_ONLY_NO_RF_CLAIM"
        ),
    }


def parser_manifest_sha256() -> str:
    return sha256(strict_json(parser_manifest()).encode("ascii")).hexdigest()


def canonical_parser_source_sha256() -> str:
    data = Path(__file__).read_bytes().replace(b"\r\n", b"\n")
    return sha256(data).hexdigest()


def strict_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _finite_polynomial(
    polynomial: PolynomialState,
) -> tuple[float, ...]:
    values = tuple(value.value for value in polynomial.coefficients)
    if any(value is None or not isfinite(value) for value in values):
        raise CassiniDualRootHeaderError(
            "required receiver polynomial is not finite"
        )
    return tuple(float(value) for value in values)


def _polynomial(coefficients: Sequence[float], u: float) -> float:
    return sum(
        value * u**power
        for power, value in enumerate(coefficients)
    )


def _numeric_summary(
    values: Sequence[NumericState],
) -> dict[str, object]:
    states = sorted({value.state for value in values})
    finite = [
        float(value.value)
        for value in values
        if value.value is not None
    ]
    return {
        "states": states,
        "finite_minimum": min(finite) if finite else None,
        "finite_maximum": max(finite) if finite else None,
    }


def _single_identity(
    summary: Mapping[str, object],
) -> tuple[object, ...]:
    fields = summary["identity_and_sample_mode"]
    names = (
        "signal_processing_center_id",
        "deep_space_station_id",
        "rsr_id",
        "channel_id",
        "subchannel_id",
    )
    result = []
    for name in names:
        values = fields[name]
        if len(values) != 1:
            raise CassiniDualRootHeaderError(
                f"identity field changed within stream: {name}"
            )
        result.append(values[0])
    return tuple(result)


def _distinct_x_ka(
    x_identity: tuple[object, ...],
    ka_identity: tuple[object, ...],
) -> bool:
    return (
        x_identity[0:2] == ka_identity[0:2]
        and x_identity[3] != ka_identity[3]
        and x_identity[4] == ka_identity[4]
    )
