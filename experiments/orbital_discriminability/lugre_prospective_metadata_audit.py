"""Bounded, sample-blind LuGRE prospective metadata audit.

This module freezes only the descriptive evidence needed to decide whether the
OP73/OP76/OP74 candidate split can become a prospective experiment.  It has no
network client, archive downloader, IQS decoder, telemetry parser, carrier
detector or orbital scorer.  The real IQS members are DEFLATE-compressed, so
their 62-byte headers cannot be ranged without also consuming compressed sample
payload.  Only the small SDRX companions and public documentation were read.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from typing import Final, Mapping, Sequence
from xml.etree import ElementTree


AUDIT_VERSION: Final = "lugre-prospective-metadata-audit-v1"
RECEIPT_NAME: Final = "LUGRE_PROSPECTIVE_METADATA_AUDIT_RECEIPT.json"
OUTCOME: Final = "LUGRE_PROSPECTIVE_PLAN_BLOCKED_BY_ADC_TIME_PROVENANCE"
GEOMETRY_RECEIPT_NAME: Final = "LUGRE_SNAPSHOT_DISCRIMINABILITY_RECEIPT.json"
GEOMETRY_RECEIPT_SHA256: Final = (
    "bbe20a00fb7f11b9979a70d352f8faff9d571749256716f10c752ef0d936f2de"
)
ZENODO_OBJECT_BYTES: Final = 256_135_673
ZENODO_OBJECT_MD5: Final = "cec32df1ca17cb95887762762c16629f"
ZENODO_TAIL_BYTES: Final = 65_536
ZENODO_TAIL_SHA256: Final = (
    "fdb21440968c1198d6215b77328138811be4176dc5817bc1630e17b3469186a4"
)
ZIP_DEFLATE: Final = 8
ION_NAMESPACE: Final = "http://www.ion.org/standards/sdrwg/schema/metadata.xsd"


@dataclass(frozen=True, slots=True)
class ZipMember:
    archive_member: str
    compression_method: int
    crc32: str
    compressed_bytes: int
    uncompressed_bytes: int
    local_header_offset: int


@dataclass(frozen=True, slots=True)
class SdrxReceipt:
    operation: str
    band: str
    timestamp_utc: str
    optable_timestamp_utc: str
    sample_rate_hz: float
    duration_s: float
    quantization_bits: int
    packed_bits: int
    center_frequency_hz: float
    translated_frequency_hz: float
    spectrum_inverted: bool
    delay_bias_s: float
    header_bytes: int
    footer_bytes: int
    metadata_bytes: int
    metadata_sha256: str
    data_member: ZipMember
    metadata_member: ZipMember


DOCUMENTS: Final = (
    {
        "role": "RECEIVER_INTERFACE_CONTROL_DOCUMENT",
        "archive_member": "LuGRE/Doc/NIL-TN-QAS-024_2.0 LuGRE Receiver Interface Control Document.pdf",
        "issue": "2.0",
        "bytes": 338_641,
        "sha256": "ee7adecd0ea6dff0d20d2ddc067738c579450ddefbd6f21ea7019bb66a368642",
        "zip_crc32": "42a4fa64",
        "provenance": "INDEPENDENT_OF_TARGET_RF",
    },
    {
        "role": "PRODUCT_HANDBOOK",
        "archive_member": "LuGRE/Doc/PRODHDBK_ESC-LUGRE-HDBK-0075-Rev-.pdf",
        "effective_date": "2025-11-13",
        "bytes": 618_698,
        "sha256": "4444f679e0cc40a810b56bd68832899cce3f12b9928802ab2f66871523cd7499",
        "zip_crc32": "5cf97ff9",
        "provenance": "INDEPENDENT_OF_TARGET_RF",
    },
    {
        "role": "OPERATION_TABLE",
        "archive_member": "LuGRE/Ancillary/OPTABLE.csv",
        "bytes": 3_308,
        "sha256": "55bbf073d58147436056b67b654a38eb306efa8c14e085e1ff3105841cacc4ed",
        "zip_crc32": "9c3cbd52",
        "provenance": "INDEPENDENT_OF_TARGET_RF",
    },
    {
        "role": "ARCHIVE_README",
        "archive_member": "LuGRE/README.md",
        "bytes": 11_128,
        "sha256": "cd5976f8bc5fcbf16f22bcec4ea1090fa9796f369b7b4e7793667b0026bb9238",
        "zip_crc32": "aa4e4d9b",
        "provenance": "INDEPENDENT_OF_TARGET_RF",
    },
    {
        "role": "INDEPENDENT_PUBLIC_IQS_INTERPRETATION",
        "url": "https://github.com/daniestevez/lugre/blob/ae0bb3d0ce77cc6a924fe4e8fbd5d714f29b0494/qascom_to_sigmf.py",
        "commit": "ae0bb3d0ce77cc6a924fe4e8fbd5d714f29b0494",
        "git_blob_sha1": "20e06efeac8b4f28c3146d22e82b56dbbf9a9180",
        "bytes": 7_408,
        "sha256": "16af7bb52a3c78e0b7e61faf3f49f49e74f62d4312c4f8c0db6f05cb6f4fb02f",
        "provenance": "INDEPENDENT_OF_TARGET_RF",
    },
)


def _member(
    name: str,
    crc32: str,
    compressed: int,
    uncompressed: int,
    offset: int,
) -> ZipMember:
    return ZipMember(name, ZIP_DEFLATE, crc32, compressed, uncompressed, offset)


SDRX_RECEIPTS: Final = (
    SdrxReceipt(
        "OP73",
        "L1",
        "2025-03-14T10:09:45.209Z",
        "2025-03-14T10:09:45.210Z",
        8_000_000.0,
        2.0,
        4,
        8,
        1_575_420_000.0,
        0.0,
        False,
        0.0,
        62,
        3,
        2_335,
        "d127395ee983c228de945395845211dbb4a4ae4b195b2e56c9c527b19fe87574",
        _member(
            "LuGRE/L0/IQS/IQS_L1_20250314_100945_2000MS_S_OP73_0.bin",
            "5e96e62c",
            10_323_556,
            16_000_394,
            25_894_697,
        ),
        _member(
            "LuGRE/L0/IQS/IQS_L1_20250314_100945_2000MS_S_OP73_0.sdrx",
            "0537c54d",
            889,
            2_335,
            36_218_386,
        ),
    ),
    SdrxReceipt(
        "OP73",
        "L5",
        "2025-03-14T10:09:45.209Z",
        "2025-03-14T10:09:45.210Z",
        24_000_000.0,
        2.0,
        4,
        8,
        1_176_450_000.0,
        0.0,
        False,
        0.0,
        62,
        3,
        2_336,
        "03b8d3ed3f6715e42ec12d748b6879828d8cfb5af66f93d2df3a89523f4fadf0",
        _member(
            "LuGRE/L0/IQS/IQS_L5_20250314_100945_2000MS_S_OP73_0.bin",
            "86fed408",
            26_141_670,
            48_001_089,
            79_770_980,
        ),
        _member(
            "LuGRE/L0/IQS/IQS_L5_20250314_100945_2000MS_S_OP73_0.sdrx",
            "e707e472",
            890,
            2_336,
            105_912_783,
        ),
    ),
    SdrxReceipt(
        "OP74",
        "L1",
        "2025-03-14T12:47:17.386Z",
        "2025-03-14T12:47:17.387Z",
        8_000_000.0,
        0.5,
        4,
        8,
        1_575_420_000.0,
        0.0,
        False,
        0.0,
        62,
        3,
        2_334,
        "99a0d66765ea8ccb342fe601d4e6df0d6e87c9b58cff017d6c61ad74b2cc564f",
        _member(
            "LuGRE/L0/IQS/IQS_L1_20250314_124717_500MS_S_OP74_0.bin",
            "8eba759f",
            2_571_508,
            4_000_479,
            36_219_409,
        ),
        _member(
            "LuGRE/L0/IQS/IQS_L1_20250314_124717_500MS_S_OP74_0.sdrx",
            "cb5cbc4f",
            890,
            2_334,
            38_791_049,
        ),
    ),
    SdrxReceipt(
        "OP74",
        "L5",
        "2025-03-14T12:47:17.386Z",
        "2025-03-14T12:47:17.387Z",
        24_000_000.0,
        0.5,
        4,
        8,
        1_176_450_000.0,
        0.0,
        False,
        0.0,
        62,
        3,
        2_335,
        "a3f8edae4e52b77e842d666ee3f6c75495c33dee5b552defcc2dc7ca10e7aa9d",
        _member(
            "LuGRE/L0/IQS/IQS_L5_20250314_124717_500MS_S_OP74_0.bin",
            "764b5291",
            6_472_468,
            12_001_345,
            105_913_807,
        ),
        _member(
            "LuGRE/L0/IQS/IQS_L5_20250314_124717_500MS_S_OP74_0.sdrx",
            "cc392da4",
            892,
            2_335,
            112_386_407,
        ),
    ),
    SdrxReceipt(
        "OP76",
        "L1",
        "2025-03-15T13:07:27.163Z",
        "2025-03-15T13:07:27.164Z",
        8_000_000.0,
        2.0,
        4,
        8,
        1_575_420_000.0,
        0.0,
        False,
        0.0,
        62,
        3,
        2_335,
        "07ab58b621d653317ef443935296a191af829374155936f3dd0b371e7f7d8bae",
        _member(
            "LuGRE/L0/IQS/IQS_L1_20250315_130727_2000MS_S_OP76_0.bin",
            "68424644",
            10_438_639,
            16_000_394,
            38_792_072,
        ),
        _member(
            "LuGRE/L0/IQS/IQS_L1_20250315_130727_2000MS_S_OP76_0.sdrx",
            "4c75be02",
            888,
            2_335,
            49_230_844,
        ),
    ),
    SdrxReceipt(
        "OP76",
        "L5",
        "2025-03-15T13:07:27.163Z",
        "2025-03-15T13:07:27.164Z",
        24_000_000.0,
        2.0,
        4,
        8,
        1_176_450_000.0,
        0.0,
        False,
        0.0,
        62,
        3,
        2_336,
        "ce3d1e7bf1ad80309f9b6bb8459f0e9f9921b789d84835d6416b6b3c70df4855",
        _member(
            "LuGRE/L0/IQS/IQS_L5_20250315_130727_2000MS_S_OP76_0.bin",
            "99a735c9",
            27_290_392,
            48_001_089,
            112_387_432,
        ),
        _member(
            "LuGRE/L0/IQS/IQS_L5_20250315_130727_2000MS_S_OP76_0.sdrx",
            "ff892bd8",
            891,
            2_336,
            139_677_957,
        ),
    ),
)


class LuGreMetadataAuditError(ValueError):
    """A frozen descriptive authority or sample boundary changed."""


def strict_json(value: object, *, pretty: bool = False) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
        sort_keys=True,
    )


def canonical_sha256(path: Path) -> str:
    return sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _text(root: ElementTree.Element, path: str) -> str:
    element = root.find(path, {"s": ION_NAMESPACE})
    if element is None or element.text is None:
        raise LuGreMetadataAuditError(f"SDRX_REQUIRED_FIELD_MISSING_{path}")
    return element.text.strip()


def parse_lugre_sdrx_metadata(payload: bytes) -> dict[str, object]:
    """Parse only the frozen, non-signal LuGRE SDRX whitelist."""

    if any(
        marker in payload.lower()
        for marker in (b"amplitude", b"adc_rms", b"adc_peak", b"signal_strength")
    ):
        raise LuGreMetadataAuditError("SDRX_SIGNAL_DERIVED_FIELD_FORBIDDEN")
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError as exc:
        raise LuGreMetadataAuditError("SDRX_DESCRIPTION_ERROR") from exc
    if root.tag != f"{{{ION_NAMESPACE}}}metadata":
        raise LuGreMetadataAuditError("SDRX_NAMESPACE_CHANGED")

    band_ref = root.find(".//s:stream/s:band", {"s": ION_NAMESPACE})
    if band_ref is None or not band_ref.get("id"):
        raise LuGreMetadataAuditError("SDRX_BAND_REFERENCE_MISSING")
    band = str(band_ref.get("id"))
    band_node = root.find(f"s:band[@id='{band}']", {"s": ION_NAMESPACE})
    if band_node is None:
        raise LuGreMetadataAuditError("SDRX_BAND_DEFINITION_MISSING")

    def band_text(name: str) -> str:
        node = band_node.find(f"s:{name}", {"s": ION_NAMESPACE})
        if node is None or node.text is None:
            raise LuGreMetadataAuditError(f"SDRX_REQUIRED_BAND_FIELD_MISSING_{name}")
        return node.text.strip()

    result = {
        "toa": _text(root, ".//s:session/s:toa"),
        "file_timestamp": _text(root, ".//s:file/s:timestamp"),
        "data_file": _text(root, ".//s:file/s:url"),
        "band": band,
        "sample_rate_hz": float(_text(root, ".//s:system/s:freqbase")) * 1.0e6,
        "quantization_bits": int(_text(root, ".//s:stream/s:quantization")),
        "packed_bits": int(_text(root, ".//s:stream/s:packedbits")),
        "sample_format": _text(root, ".//s:stream/s:format"),
        "encoding": _text(root, ".//s:stream/s:encoding"),
        "header_bytes": int(_text(root, ".//s:block/s:sizeheader")),
        "footer_bytes": int(_text(root, ".//s:block/s:sizefooter")),
        "center_frequency_hz": float(band_text("centerfreq")) * 1.0e6,
        "translated_frequency_hz": float(band_text("translatedfreq")) * 1.0e6,
        "spectrum_inverted": band_text("inverted").lower() == "true",
        "delay_bias_s": float(band_text("delaybias")),
    }
    if result["toa"] != result["file_timestamp"]:
        raise LuGreMetadataAuditError("SDRX_TIME_FIELDS_DISAGREE")
    if result["sample_format"] != "IQ" or result["encoding"] != "TC":
        raise LuGreMetadataAuditError("SDRX_SAMPLE_DESCRIPTION_CHANGED")
    if result["header_bytes"] != 62 or result["footer_bytes"] != 3:
        raise LuGreMetadataAuditError("SDRX_ENVELOPE_CHANGED")
    strict_json(result)
    return result


def data_header_access_state(member: ZipMember) -> str:
    """Return whether a payload header is byte-separable from sample content."""

    if member.compression_method == 0:
        return "DIRECT_RANGE_SEPARABLE_NOT_AUTHORIZED_IN_THIS_AUDIT"
    if member.compression_method == ZIP_DEFLATE:
        return "NOT_SEPARABLE_FROM_COMPRESSED_SAMPLE_PAYLOAD"
    return "UNKNOWN_COMPRESSION_METHOD"


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _geometry_rows(root: Path) -> Mapping[str, Mapping[str, object]]:
    path = root / GEOMETRY_RECEIPT_NAME
    if canonical_sha256(path) != GEOMETRY_RECEIPT_SHA256:
        raise LuGreMetadataAuditError("FROZEN_GEOMETRY_RECEIPT_CHANGED")
    receipt = json.loads(path.read_text(encoding="ascii"))
    return {str(row["operation"]): row for row in receipt["ranked_operations"]}


def _instrument_rows(
    geometry: Mapping[str, Mapping[str, object]],
) -> list[dict[str, object]]:
    roles = {
        "OP73": "DEVELOPMENT_CANDIDATE_NOT_FROZEN",
        "OP76": "PRIMARY_CANDIDATE_NOT_FROZEN",
        "OP74": "RESERVE_CANDIDATE_NOT_FROZEN",
    }
    rows: list[dict[str, object]] = []
    for operation in ("OP73", "OP76", "OP74"):
        bands = [row for row in SDRX_RECEIPTS if row.operation == operation]
        if len(bands) != 2 or {row.band for row in bands} != {"L1", "L5"}:
            raise LuGreMetadataAuditError(f"{operation}_DUAL_BAND_METADATA_INCOMPLETE")
        if len({row.timestamp_utc for row in bands}) != 1:
            raise LuGreMetadataAuditError(f"{operation}_BAND_TIMESTAMPS_DIFFER")
        if any(data_header_access_state(row.data_member).startswith("DIRECT") for row in bands):
            raise LuGreMetadataAuditError("UNEXPECTED_DIRECT_IQS_HEADER_PATH")

        l1 = next(row for row in bands if row.band == "L1")
        delta = (_parse_utc(l1.timestamp_utc) - _parse_utc(l1.optable_timestamp_utc)).total_seconds()
        candidate = geometry[operation]["candidate_family"]
        controlling = candidate["controlling_separation"]  # type: ignore[index]
        separation = float(controlling["affine_projected_rmse_hz"])  # type: ignore[index]
        rows.append(
            {
                "operation": operation,
                "candidate_role": roles[operation],
                "sdrx_timestamp_utc": l1.timestamp_utc,
                "optable_timestamp_utc": l1.optable_timestamp_utc,
                "sdrx_minus_optable_s": delta,
                "bands_share_sdrx_timestamp": True,
                "duration_s": l1.duration_s,
                "native_whole_window_fft_spacing_hz": 1.0 / l1.duration_s,
                "geometry_controlling_separation_hz": separation,
                "maximum_symmetric_total_per_track_rms_envelope_hz": separation / 2.0,
                "metadata": [asdict(row) for row in bands],
            }
        )
    return rows


def build_receipt(root: Path, source_commit: str) -> dict[str, object]:
    geometry = _geometry_rows(root)
    instruments = _instrument_rows(geometry)
    result: dict[str, object] = {
        "schema": "lugre-prospective-metadata-audit-receipt-v1",
        "audit_version": AUDIT_VERSION,
        "source_commit": source_commit,
        "source_sha256": canonical_sha256(Path(__file__)),
        "physical_question": (
            "CAN_OP76_PRODUCE_AN_INTERPRETABLE_NEGATIVE_FOR_THE_FROZEN_"
            "FOUR_SIGNAL_ORBITAL_SHAPE_WITHOUT_DERIVING_ABSOLUTE_TIME_FROM_TARGET_RF"
        ),
        "archive": {
            "record": "https://zenodo.org/records/16411687",
            "doi": "10.5281/zenodo.16411687",
            "version": "v1",
            "license": "CC-BY-4.0",
            "object": "LuGRE.zip",
            "bytes": ZENODO_OBJECT_BYTES,
            "published_md5": ZENODO_OBJECT_MD5,
            "zip_entries": 224,
            "central_directory_offset": 256_108_345,
            "central_directory_bytes": 27_306,
            "eocd_offset": 256_135_651,
            "tail_range_bytes": ZENODO_TAIL_BYTES,
            "tail_range_sha256": ZENODO_TAIL_SHA256,
        },
        "authorities": list(DOCUMENTS),
        "candidate_split": instruments,
        "time_semantics": {
            "iqs_icd_rx_time": "RECEIVER_TIME_MISSION_USED_GPST",
            "product_handbook_sc_start": "ACTUAL_SAMPLE_CAPTURE_START_DERIVED_FROM_IQS_HEADER",
            "filename": "SAMPLE_CAPTURE_START_TO_ONE_SECOND",
            "sdrx_and_optable_resolution_s": 0.001,
            "repeated_sdrx_minus_optable_s": -0.001,
            "resolution_is_accuracy": False,
            "generic_qn400_timing_accuracy_s": 50.0e-9,
            "generic_qn400_bound_product_applicable": False,
            "adc_to_true_gpst_error_bound_s": None,
            "state": "UNRESOLVED_FINITE_ABSOLUTE_TIME_BOUND",
        },
        "frequency_transform": {
            "l1": {
                "sample_rate_hz": 8_000_000.0,
                "center_frequency_hz": 1_575_420_000.0,
            },
            "l5": {
                "sample_rate_hz": 24_000_000.0,
                "center_frequency_hz": 1_176_450_000.0,
            },
            "translated_frequency_hz": 0.0,
            "spectrum_inverted": False,
            "sample_format": "COMPLEX_IQ_TWO_COMPLEMENT_4_BIT_PACKED_IN_8_BITS",
            "same_l1_file_for_all_four_future_coordinates": True,
            "common_frequency_offset": "PROJECTED_BY_FROZEN_GEOMETRY_SCORE",
            "common_positive_frequency_scale": "PROJECTED_BY_FROZEN_GEOMETRY_SCORE",
            "exact_iqs_header": "NOT_ACCESSED",
            "iqs_header_access_state": "NOT_SEPARABLE_FROM_COMPRESSED_SAMPLE_PAYLOAD",
            "header_only_range_authorized": False,
        },
        "detectability": {
            "controlling_primary_separation_hz": 11.019310141609873,
            "maximum_symmetric_total_per_track_rms_envelope_hz": 5.5096550708049365,
            "primary_native_whole_window_fft_spacing_hz": 0.5,
            "native_spacing_within_geometry_envelope": True,
            "native_spacing_is_detector_error_bound": False,
            "detector": "NOT_IMPLEMENTED",
            "four_frozen_signal_presence": "NOT_EVALUATED_PRE_SCORE",
            "satellite_clock_residual": "OPEN_TERM_NOT_EVALUATED_AFTER_TIME_BLOCKER",
            "differential_media": "OPEN_TERM_NOT_EVALUATED_AFTER_TIME_BLOCKER",
            "non_affine_estimator_weighting_of_common_clock": "OPEN_TERM_FOR_FUTURE_DETECTOR_MANIFEST",
            "l5_dispersive_witness": "AVAILABLE_AS_SIMULTANEOUS_BAND_NOT_ADMITTED_FOR_ANY_SATELLITE",
        },
        "clauses": [
            {
                "clause": "ARCHIVE_IDENTITY",
                "state": "SUPPORTED_AT_ARCHIVE_LEVEL",
            },
            {
                "clause": "L1_L5_SIMULTANEITY",
                "state": "SUPPORTED_DESCRIPTIVELY",
            },
            {
                "clause": "FREQUENCY_AXIS_TRANSFORM",
                "state": "SUPPORTED_BY_SDRX_METADATA",
            },
            {
                "clause": "IQS_HEADER_IDENTITY",
                "state": "NOT_EVALUATED_SAMPLE_BOUNDARY",
            },
            {
                "clause": "SAMPLE_CAPTURE_START_SEMANTICS",
                "state": "SUPPORTED_DESCRIPTIVELY",
            },
            {
                "clause": "FINITE_ADC_TO_TRUE_GPST_BOUND",
                "state": "UNRESOLVED",
            },
            {
                "clause": "MODEL_BLIND_DETECTOR_ERROR",
                "state": "NOT_EVALUATED",
            },
            {
                "clause": "FOUR_FROZEN_L1_CARRIERS_PRESENT",
                "state": "NOT_EVALUATED_PRE_SCORE",
            },
            {
                "clause": "PHYSICAL_CORRECTION_ENVELOPE",
                "state": "NOT_EVALUATED_AFTER_BLOCKING_CLAUSE",
            },
        ],
        "access_boundary": {
            "zenodo_record_metadata": True,
            "zip_central_directory": True,
            "sdrx_companions": 6,
            "public_documentation": True,
            "iqs_local_zip_headers": False,
            "iqs_compressed_payload_bytes": 0,
            "iqs_uncompressed_bytes": 0,
            "iq_sample_values": 0,
            "telemetry_bytes": 0,
            "signal_derived_diagnostics": 0,
            "primary_opened": False,
            "reserve_opened": False,
        },
        "roles_frozen": False,
        "prospective_plan_frozen": False,
        "maximum_authorized_claim": (
            "THE_PUBLIC_SDRX_PRODUCTS_DESCRIBE_A_REVERSIBLE_COMMON_L1_FREQUENCY_"
            "COORDINATE_BUT_DO_NOT_SUPPLY_A_FINITE_PRODUCT_APPLICABLE_ADC_TO_UTC_BOUND"
        ),
        "outcome": OUTCOME,
        "minimum_next_physical_step": (
            "OBTAIN_OUTCOME_INDEPENDENT_PRODUCT_APPLICABLE_ADC_TIME_PROVENANCE_OR_CLOSE_LUGRE_ROUTE"
        ),
    }
    strict_json(result)
    return result


def _git_commit(root: Path) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parent
    )
    parser.add_argument(
        "--repo-root", type=Path, default=Path(__file__).resolve().parents[2]
    )
    parser.add_argument("--source-commit")
    parser.add_argument(
        "--output", type=Path, default=Path(__file__).with_name(RECEIPT_NAME)
    )
    args = parser.parse_args(argv)
    receipt = build_receipt(
        args.root, args.source_commit or _git_commit(args.repo_root)
    )
    args.output.write_text(
        strict_json(receipt, pretty=True) + "\n", encoding="ascii", newline="\n"
    )
    print(
        strict_json(
            {
                "outcome": receipt["outcome"],
                "receipt": str(args.output),
                "iq_sample_bytes": 0,
                "roles_frozen": False,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
