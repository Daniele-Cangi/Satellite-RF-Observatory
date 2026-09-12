"""Offline boundaries for the frozen DRAO code-only header qualification."""
from copy import deepcopy
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path

import pytest

from research.kinematic.drao_code_header_qualification import (
    HeaderRejected,
    admit_archive_age,
    audit_header,
    validate_plan,
)
from research.kinematic.phase_transform_header_audit import extract_crinex_header


ROOT = Path(__file__).resolve().parents[3]
PLAN_PATH = ROOT / "research/kinematic/drao_code_header_qualification_plan.json"
PLAN = json.loads(PLAN_PATH.read_text())


def _h(value: str, label: str) -> str:
    return f"{value:<60}{label:<20}"


def _scale(factor: int, names=("C1C", "C2W")) -> str:
    value = [" "] * 60
    value[0] = "G"
    value[2:6] = f"{factor:4d}"
    value[8:10] = f"{len(names):2d}"
    for index, name in enumerate(names):
        offset = 10 + 4 * index
        value[offset + 1:offset + 4] = name
    return _h("".join(value), "SYS / SCALE FACTOR")


def _header(extra=(), types="G    4 C1C C2W L1C L2W") -> list[str]:
    rows = [
        _h("     3.05           OBSERVATION DATA    M (MIXED)", "RINEX VERSION / TYPE"),
        _h("DRAO", "MARKER NAME"),
        _h("GEODETIC", "MARKER TYPE"),
        _h(f"{'RX-SERIAL':<20}{'RECEIVER':<20}{'1.0':<20}", "REC # / TYPE / VERS"),
        _h(f"{'ANT-SERIAL':<20}{'ANTENNA':<20}", "ANT # / TYPE"),
        _h(" -2059164.0 -3621108.0 4814433.0", "APPROX POSITION XYZ"),
        _h("        0.1000        0.0000        0.0000", "ANTENNA: DELTA H/E/N"),
        _h(types, "SYS / # / OBS TYPES"),
        _h("    30.000", "INTERVAL"),
        _h("  2026     8    30     0     0    0.0000000     GPS", "TIME OF FIRST OBS"),
        _h("  2026     8    30    23    59   30.0000000     GPS", "TIME OF LAST OBS"),
        _h("     0", "RCV CLOCK OFFS APPL"),
        *extra,
        _h("", "END OF HEADER"),
    ]
    return rows


def _crx(lines: list[str]) -> bytes:
    text = "\n".join([
        _h("3.0                 COMPACT RINEX FORMAT", "CRINEX VERS   / TYPE"),
        _h("TEST", "CRINEX PROG / DATE"),
        *lines,
        "> 2026 08 30 00 00 00.0000000  0  1",
        "G14 SECRET_TARGET_VALUE nan inf",
    ]) + "\n"
    return gzip.compress(text.encode("ascii"))


def test_plan_is_single_source_code_only_and_mature():
    validate_plan(PLAN)
    assert PLAN["source"]["required_gps_code_observables"] == ["C1C", "C2W"]
    assert PLAN["execution"]["hatanaka_body_decoder_forbidden"]
    assert PLAN["persistence"]["observation_values"] is False
    admit_archive_age(PLAN, now_utc=datetime(2026, 9, 2, 23, 59, 31, tzinfo=timezone.utc))


def test_reader_stops_before_target_record():
    lines, receipt = extract_crinex_header(_crx(_header()), maximum_lines=2000)
    assert all("SECRET_TARGET" not in line for line in lines)
    assert receipt["observation_body_lines_exposed"] == 0


def test_code_coordinate_is_explicit_and_phase_headers_are_irrelevant():
    phase = _h("G L1C  0.25000  0", "SYS / PHASE SHIFT")
    legacy = _h("     1     2     0", "WAVELENGTH FACT L1/2")
    result = audit_header(_header(extra=[phase, legacy]), PLAN)
    ledger = result["transform_ledger"]
    assert result["status"] == "HEADER_CODE_COORDINATE_QUALIFIED"
    assert ledger["stored_value_scale_divisor"] == {"C1C": 1, "C2W": 1}
    assert ledger["phase_transform_headers_inspected_for_admission"] is False
    assert ledger["ionosphere_free_code"]["coefficients"]["C1C"] == pytest.approx(2.54572778016316)
    assert ledger["ionosphere_free_code"]["coefficients"]["C2W"] == pytest.approx(-1.54572778016316)


def test_code_scale_factor_is_retained_without_phase_requirements():
    result = audit_header(_header(extra=[_scale(10)]), PLAN)
    assert result["transform_ledger"]["stored_value_scale_divisor"] == {"C1C": 10, "C2W": 10}


def test_missing_named_code_or_legacy_format_rejects():
    with pytest.raises(HeaderRejected, match="MISSING_REQUIRED_GPS_CODE_OBSERVABLE"):
        audit_header(_header(types="G    3 C1C L1C L2W"), PLAN)
    legacy = _header()
    legacy[0] = _h("     2.11           OBSERVATION DATA    G (GPS)", "RINEX VERSION / TYPE")
    with pytest.raises(HeaderRejected, match="UNSUPPORTED_NAMED_CODE_FORMAT"):
        audit_header(legacy, PLAN)


def test_applied_clock_or_external_correction_rejects():
    clock = _header()
    index = next(i for i, row in enumerate(clock) if row[60:80].strip() == "RCV CLOCK OFFS APPL")
    clock[index] = _h("     1", "RCV CLOCK OFFS APPL")
    with pytest.raises(HeaderRejected, match="APPLIED_RECEIVER_CLOCK_CORRECTION"):
        audit_header(clock, PLAN)
    dcbs = _h(f"G {'PROGRAM':<17} {'MODEL':<40}", "SYS / DCBS APPLIED")
    with pytest.raises(HeaderRejected, match="UNQUALIFIED_APPLIED_EXTERNAL_CORRECTION"):
        audit_header(_header(extra=[dcbs]), PLAN)


def test_header_coverage_cannot_be_substituted():
    lines = _header()
    index = next(i for i, row in enumerate(lines) if row[60:80].strip() == "TIME OF LAST OBS")
    lines[index] = _h("  2026     8    30    23    59    0.0000000     GPS", "TIME OF LAST OBS")
    with pytest.raises(HeaderRejected, match="HEADER_DOES_NOT_COVER_FROZEN_DAY"):
        audit_header(lines, PLAN)
    shifted = deepcopy(PLAN)
    shifted["date_gpst"] = "2026-08-31"
    with pytest.raises(ValueError, match="date/day-of-year"):
        validate_plan(shifted)


def test_frozen_outcome_is_hash_bound_value_blind_rejection():
    path = ROOT / "research/kinematic/results/drao_code_header_qualification_2026242_v1.json"
    result = json.loads(path.read_text())
    assert hashlib.sha256(path.read_bytes()).hexdigest() == (
        "214cbc3c19f059d933b381a33aa003dcda3952ad32f8b8e8e955ec94c371c242"
    )
    assert result["status"] == "DRAO_CODE_HEADERS_NOT_QUALIFIED"
    assert result["failures"] == [{
        "stage": "HEADER_ADMISSION",
        "classification": "CAPABILITY_REJECTED",
        "reason": "UNSUPPORTED_NAMED_CODE_FORMAT",
    }]
    assert result["source_receipt"]["bytes"] == 2_891_896
    assert result["source_receipt"]["sha256"] == (
        "5064142f469f2adba4d5b2e561007794fa59f4a50f1b12549830ebb0bb321de1"
    )
    assert result["source_receipt"]["observation_body_lines_exposed"] == 0
    assert result["freeze"]["observation_record_access"] is False
    assert result["freeze"]["target_identity_or_value_access"] is False
    assert result["persistence"]["raw_payload_bytes"] == 0
