"""Bounded DSS-45 metadata-only header spike and reconstructed-SPK compiler run.

This module contains exactly one RSR product URL: the frozen DSS-45 development
product. HTTP access is limited to selected 260-byte SFDU header ranges. A
response that could contain the data CHDO is refused before its body is read.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import tempfile
from typing import Callable, Final
import urllib.request

from experiments.orbital_discriminability.maven_dsn_two_way import (
    PiecewiseRamp,
    RampSegment,
    RsrReceiverTransform,
    StateVector,
    predict_frozen_nulls,
)
from experiments.orbital_discriminability.maven_rsr_header import (
    DEVELOPMENT_LIDVID,
    RSR_HEADER_BYTES,
    RSR_RECORD_BYTES,
    RsrHeaderReceipt,
    parse_dss45_header,
    parser_manifest,
    parser_manifest_sha256,
    strict_json,
)


DEVELOPMENT_DATA_URL: Final = (
    "https://pds-ppi.igpp.ucla.edu/data/maven-rose-raw/data/rsr/2016/07/"
    "mvn_rse_l0_rsr_20160712T124201_v01_r00.dat"
)
DEVELOPMENT_FILE_BYTES: Final = 4_600_800
DEVELOPMENT_RECORDS: Final = 1_080
SCIENCE_LAST_RECORD_INDEX: Final = 736
HEADER_CADENCE_RECORDS: Final = 10
HEADER_INDICES: Final = tuple(
    sorted(
        {
            *range(0, SCIENCE_LAST_RECORD_INDEX + 1, HEADER_CADENCE_RECORDS),
            SCIENCE_LAST_RECORD_INDEX,
        }
    )
)
FUP_URL: Final = (
    "https://pds-ppi.igpp.ucla.edu/data/maven-rose-calibrated/calibration/fup/"
    "2016/07/mvn_rse_l2_fup_20160712T082035_v01_r01.tab"
)
FUP_SHA256: Final = "f06d91a4c88c54e72eaec8caebe705c1c15aacace3fe3df107531b9f4b589286"
USER_AGENT: Final = "Satellite-RF-Observatory-DSS45-header-only/1"


@dataclass(frozen=True, slots=True)
class KernelSpec:
    name: str
    role: str
    url: str
    independence: str


KERNELS: Final = (
    KernelSpec(
        "naif0012.tls",
        "UTC_TO_TDB",
        "https://naif.jpl.nasa.gov/pub/naif/pds/pds4/maven/maven_spice/"
        "spice_kernels/lsk/naif0012.tls",
        "TIME_SCALE_CONTROL",
    ),
    KernelSpec(
        "pck00010.tpc",
        "BODY_CONSTANTS",
        "https://naif.jpl.nasa.gov/pub/naif/pds/pds4/maven/maven_spice/"
        "spice_kernels/pck/pck00010.tpc",
        "MODEL_CONTROL",
    ),
    KernelSpec(
        "de430s.bsp",
        "EARTH_AND_SOLAR_SYSTEM_EPHEMERIS",
        "https://naif.jpl.nasa.gov/pub/naif/pds/pds4/maven/maven_spice/"
        "spice_kernels/spk/de430s.bsp",
        "PLANETARY_EPHEMERIS",
    ),
    KernelSpec(
        "mar097s.bsp",
        "MARS_SYSTEM_EPHEMERIS",
        "https://naif.jpl.nasa.gov/pub/naif/pds/pds4/maven/maven_spice/"
        "spice_kernels/spk/mar097s.bsp",
        "MARS_SYSTEM_EPHEMERIS",
    ),
    KernelSpec(
        "maven_orb_rec_160701_161001_v1.bsp",
        "MAVEN_TRAJECTORY",
        "https://naif.jpl.nasa.gov/pub/naif/pds/pds4/maven/maven_spice/"
        "spice_kernels/spk/maven_orb_rec_160701_161001_v1.bsp",
        "RECONSTRUCTED_POST_PASS_TARGET_PASS_ASSIMILATION_NOT_EXCLUDED",
    ),
    KernelSpec(
        "earthstns_itrf93_050714.bsp",
        "DSS45_ITRF93_POSITION_AND_PLATE_MOTION",
        "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/stations/"
        "a_old_versions/earthstns_itrf93_050714.bsp",
        "STATION_MODEL_CREATED_2005_PRE_PASS",
    ),
    KernelSpec(
        "earth_1962_260806_2126_combined.bpc",
        "EARTH_ORIENTATION_ITRF93_TO_J2000",
        "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/"
        "earth_1962_260806_2126_combined.bpc",
        "RECONSTRUCTED_HISTORICAL_EARTH_ORIENTATION_POST_PASS_ARCHIVE",
    ),
)


class HeaderSpikeError(RuntimeError):
    """A bounded metadata access or predictor precondition failed."""


def fetch_header(record_index: int) -> RsrHeaderReceipt:
    """Fetch exactly one 260-byte header; never read a non-range response."""

    if record_index not in HEADER_INDICES:
        raise HeaderSpikeError("record index is outside the frozen header plan")
    start = record_index * RSR_RECORD_BYTES
    stop = start + RSR_HEADER_BYTES - 1
    request = urllib.request.Request(
        DEVELOPMENT_DATA_URL,
        headers={
            "Range": f"bytes={start}-{stop}",
            "User-Agent": USER_AGENT,
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        expected_range = f"bytes {start}-{stop}/{DEVELOPMENT_FILE_BYTES}"
        length = int(response.headers.get("Content-Length", "0"))
        if (
            response.getcode() != 206
            or response.headers.get("Content-Range") != expected_range
            or length != RSR_HEADER_BYTES
        ):
            raise HeaderSpikeError("server did not return the exact authorized header range")
        raw = bytearray(response.read(RSR_HEADER_BYTES + 1))
    if len(raw) != RSR_HEADER_BYTES:
        raw[:] = bytes(len(raw))
        raise HeaderSpikeError("authorized header response had an unexpected length")
    try:
        return parse_dss45_header(raw)
    finally:
        raw[:] = bytes(len(raw))


def fetch_headers() -> tuple[RsrHeaderReceipt, ...]:
    receipts = tuple(fetch_header(index) for index in HEADER_INDICES)
    for left_index, right_index, left, right in zip(
        HEADER_INDICES,
        HEADER_INDICES[1:],
        receipts,
        receipts[1:],
    ):
        delta = right_index - left_index
        if (right.record_sequence_number - left.record_sequence_number) % 65536 != delta:
            raise HeaderSpikeError("sampled SFDU record sequence is discontinuous")
        if abs(
            _parse_utc(right.first_sample_utc).timestamp()
            - _parse_utc(left.first_sample_utc).timestamp()
            - delta
        ) > 1e-6:
            raise HeaderSpikeError("sampled first-sample UTC tags are discontinuous")
    return receipts


def fetch_fup() -> bytes:
    request = urllib.request.Request(FUP_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        body = response.read()
    if sha256(body).hexdigest() != FUP_SHA256:
        raise HeaderSpikeError("FUP content hash differs from the frozen control")
    return body


def _download_kernel(spec: KernelSpec, directory: Path) -> dict[str, object]:
    target = directory / spec.name
    digest = sha256()
    size = 0
    request = urllib.request.Request(spec.url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=180) as response, target.open("wb") as sink:
        while chunk := response.read(1024 * 1024):
            sink.write(chunk)
            digest.update(chunk)
            size += len(chunk)
    return {
        "name": spec.name,
        "role": spec.role,
        "url": spec.url,
        "bytes": size,
        "sha256": digest.hexdigest(),
        "independence": spec.independence,
    }


def _parse_fup(spice, body: bytes) -> PiecewiseRamp:
    points: list[tuple[float, float, float]] = []
    for line in body.decode("ascii").splitlines():
        year, day, second, rate, frequency = line.split()
        utc = _year_day_second_utc(int(year), int(day), float(second))
        points.append((spice.utc2et(utc), float(rate), float(frequency)))
    segments = tuple(
        RampSegment(start, following[0], frequency, rate)
        for (start, rate, frequency), following in zip(points, points[1:])
    )
    ramp = PiecewiseRamp(segments)
    ramp.validate()
    return ramp


def _state_provider(spice, target: str) -> Callable[[float], StateVector]:
    def state(epoch_tdb_s: float) -> StateVector:
        vector, _ = spice.spkezr(
            target,
            epoch_tdb_s,
            "J2000",
            "NONE",
            "SOLAR SYSTEM BARYCENTER",
        )
        return StateVector(
            tuple(float(value) * 1_000.0 for value in vector[:3]),
            tuple(float(value) * 1_000.0 for value in vector[3:]),
        )

    return state


def _finite(state, name: str) -> float:
    if state.state != "FINITE" or state.value is None:
        raise HeaderSpikeError(f"required SFDU field is not calculable: {name}")
    return float(state.value)


def _receiver(spice, receipt: RsrHeaderReceipt) -> RsrReceiverTransform:
    frequency = receipt.frequency_polynomial.coefficients
    return RsrReceiverTransform(
        record_start_time_s=spice.utc2et(receipt.first_sample_utc),
        rf_to_if_lo_hz=float(receipt.rf_to_if_lo_hz),
        ddc_lo_hz=float(receipt.ddc_lo_hz),
        nco_f1_hz=_finite(frequency[0], "F1"),
        nco_f2_hz=_finite(frequency[1], "F2"),
        nco_f3_hz=_finite(frequency[2], "F3"),
        sample_rate_hz=receipt.sample_rate_hz,
        sample_resolution_bits=receipt.sample_resolution_bits,
        receiver_id=f"RSR{receipt.rsr_id}",
        subchannel_id=receipt.subchannel_id,
        predicts_time_shift_s=_finite(receipt.predicts_time_shift_s, "time shift"),
        predicts_frequency_rate_hz_s=_finite(
            receipt.predicts_frequency_rate_hz_s, "frequency rate"
        ),
        predicts_frequency_offset_hz=_finite(
            receipt.predicts_frequency_offset_hz, "frequency offset"
        ),
        subchannel_frequency_offset_hz=_finite(
            receipt.subchannel_frequency_offset_hz, "subchannel offset"
        ),
        frequency_override_active=receipt.frequency_override_active,
        predicts_frequency_override_hz=(
            _finite(receipt.predicts_frequency_override_hz, "frequency override")
            if receipt.frequency_override_active
            else None
        ),
        filter_bandwidth_hz=float(receipt.filter_decimation.output_bandwidth_hz),
        decimation=receipt.filter_decimation.decimation,
    )


def compile_metadata_curve(
    spice,
    receipts: tuple[RsrHeaderReceipt, ...],
    fup: bytes,
) -> list[dict[str, object]]:
    ramp = _parse_fup(spice, fup)
    station = _state_provider(spice, "DSS-45")
    maven = _state_provider(spice, "MAVEN")
    mars = _state_provider(spice, "MARS")
    curve: list[dict[str, object]] = []
    for receipt in receipts:
        receiver = _receiver(spice, receipt)
        receive_tdb = receiver.record_start_time_s + 0.5005
        predictions = predict_frozen_nulls(
            receive_tdb,
            ramp,
            receiver,
            station,
            maven,
            mars,
            station,
        )
        curve.append(
            {
                "record_sequence_number": receipt.record_sequence_number,
                "record_first_sample_utc": receipt.first_sample_utc,
                "prediction_epoch_offset_s": 0.5005,
                "nominal_reconstructed_spk": asdict(predictions.nominal),
                "null_ramp_nco_only": asdict(predictions.ramp_nco_only),
                "null_mars_center_geometry": asdict(predictions.geometry_destroying),
                "nominal_minus_ramp_nco_hz": (
                    predictions.nominal.recorded_baseband_frequency_hz
                    - predictions.ramp_nco_only.recorded_baseband_frequency_hz
                ),
                "nominal_minus_mars_center_hz": (
                    predictions.nominal.recorded_baseband_frequency_hz
                    - predictions.geometry_destroying.recorded_baseband_frequency_hz
                ),
            }
        )
    return curve


def run_metadata_spike() -> dict[str, object]:
    """Perform the frozen bounded run; imported spiceypy is an explicit dependency."""

    import spiceypy as spice

    receipts = fetch_headers()
    fup = fetch_fup()
    with tempfile.TemporaryDirectory(prefix="maven-dss45-kernels-") as temporary:
        directory = Path(temporary)
        lineage = [_download_kernel(spec, directory) for spec in KERNELS]
        try:
            for spec in KERNELS:
                spice.furnsh(str(directory / spec.name))
            curve = compile_metadata_curve(spice, receipts, fup)
        finally:
            spice.kclear()
    receipt_objects = [receipt.as_json_object() for receipt in receipts]
    header_ledger_sha = sha256(
        strict_json(receipt_objects).encode("utf-8")
    ).hexdigest()
    result = {
        "outcome": "READY_FOR_DSS45_DEVELOPMENT_IQ",
        "claim_scope": "DEVELOPMENT_ONLY_FOR_TWO_WAY_RSR_COMPILER",
        "development_lidvid": DEVELOPMENT_LIDVID,
        "header_access": {
            "records_total": DEVELOPMENT_RECORDS,
            "records_requested": list(HEADER_INDICES),
            "request_count": len(HEADER_INDICES),
            "bytes_per_request": RSR_HEADER_BYTES,
            "sample_chdo_bytes_read": 0,
            "raw_headers_retained": 0,
            "selection": "science interval every 10 records plus final record",
        },
        "parser_manifest": parser_manifest(),
        "parser_manifest_sha256": parser_manifest_sha256(),
        "header_transform_ledger_sha256": header_ledger_sha,
        "header_receipts": receipt_objects,
        "fup": {
            "url": FUP_URL,
            "sha256": FUP_SHA256,
            "bytes": len(fup),
            "provenance": "PDS FUP extracted from development TNF",
        },
        "kernel_lineage": lineage,
        "spk_independence": {
            "result": "NO_PREDICTED_OR_PRE_PASS_2016_MAVEN_ORBIT_FOUND",
            "classification": "DEVELOPMENT_ONLY_FOR_TWO_WAY_RSR_COMPILER",
            "nominal_curve_spk": "RECONSTRUCTED_POST_PASS",
            "target_pass_assimilation_excluded": False,
            "independent_orbital_prediction_authorized": False,
        },
        "transform_ledger": [
            "SFDU first-sample UTC --naif0012.tls--> TDB",
            "DSS-45 ITRF93 station SPK --binary Earth PCK--> J2000 state",
            "reconstructed MAVEN SPK + DE430s + MAR097s --> J2000 state",
            "FUP at solved Earth-transmit epoch --> uplink sky frequency",
            "uplink geometric frequency factor --> spacecraft receive frequency",
            "coherent 880/749 turnaround --> spacecraft transmit frequency",
            "downlink geometric frequency factor --> received sky frequency",
            "SFDU RF-to-IF LO + DDC LO - millisecond NCO --> recorded baseband",
            "VDP FIR 16 Msps to 1 ksps --> 1 kHz output mode, decimation 16000",
        ],
        "explicit_open_terms": [
            "solar gravitational light-time correction",
            "neutral atmosphere and ionosphere",
            "interplanetary plasma and Mars occultation media",
            "station hardware delay and spacecraft transponder delay",
            "FIR coefficient shape (not encoded in SFDU)",
        ],
        "curve": curve,
    }
    strict_json(result)
    return result


def write_result(path: Path) -> str:
    result = run_metadata_spike()
    rendered = json.dumps(
        result,
        allow_nan=False,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    ) + "\n"
    path.write_text(rendered, encoding="utf-8", newline="\n")
    return sha256(rendered.encode("utf-8")).hexdigest()


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _year_day_second_utc(year: int, day: int, second: float) -> str:
    instant = datetime(year, 1, 1, tzinfo=timezone.utc) + timedelta(
        days=day - 1,
        seconds=second,
    )
    return instant.isoformat(timespec="microseconds").replace("+00:00", "Z")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    print(write_result(arguments.output))
