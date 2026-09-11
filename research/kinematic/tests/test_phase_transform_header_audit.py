"""Offline boundaries for the frozen header-only phase-transform audit."""
from copy import deepcopy
import gzip
import json
from pathlib import Path

import pytest

from research.kinematic.phase_transform_header_audit import (
    HeaderRejected,
    _strict_json,
    audit_header,
    extract_crinex_header,
    validate_plan,
)


ROOT = Path(__file__).resolve().parents[3]
PLAN = json.loads((ROOT / "research/kinematic/phase_transform_header_audit_plan.json").read_text())


def _h(value: str, label: str) -> str:
    return f"{value:<60}{label:<20}"


def _phase_shift(code: str, shift: float | None = None, satellites=()) -> str:
    value = [" "] * 60
    value[0] = "G"
    value[2:5] = code
    if shift is not None:
        value[6:14] = f"{shift:8.5f}"
    value[16:18] = f"{len(satellites):2d}"
    for index, satellite in enumerate(satellites):
        offset = 18 + 4 * index
        value[offset + 1:offset + 4] = satellite
    return _h("".join(value), "SYS / PHASE SHIFT")


def _scale(factor: int, types=()) -> str:
    value = [" "] * 60
    value[0] = "G"
    value[2:6] = f"{factor:4d}"
    value[8:10] = f"{len(types):2d}"
    for index, observable in enumerate(types):
        offset = 10 + 4 * index
        value[offset + 1:offset + 4] = observable
    return _h("".join(value), "SYS / SCALE FACTOR")


def _wavelength(l1: int, l2: int, satellites=()) -> str:
    value = [" "] * 60
    value[0:6] = f"{l1:6d}"
    value[6:12] = f"{l2:6d}"
    value[12:18] = f"{len(satellites):6d}"
    for index, satellite in enumerate(satellites):
        offset = 18 + 6 * index
        value[offset + 3:offset + 6] = satellite
    return _h("".join(value), "WAVELENGTH FACT L1/2")


def _header(extra=(), phase=True) -> list[str]:
    first = "     3.05           OBSERVATION DATA    M (MIXED)"
    types = "G    4 C1C C2W L1C L2W"
    rows = [
        _h(first, "RINEX VERSION / TYPE"),
        _h("TEST", "MARKER NAME"),
        _h("Geodetic", "MARKER TYPE"),
        _h(f"{'SERIAL':<20}{'RECEIVER':<20}{'1.0':<20}", "REC # / TYPE / VERS"),
        _h(types, "SYS / # / OBS TYPES"),
        _h("    30.000", "INTERVAL"),
        _h("  2026     9     8     0     0    0.0000000     GPS", "TIME OF FIRST OBS"),
        _h("  2026     9     8    23    59   30.0000000     GPS", "TIME OF LAST OBS"),
        _h("     0", "RCV CLOCK OFFS APPL"),
    ]
    rows.extend(extra)
    if phase:
        rows.extend((_phase_shift("L1C"), _phase_shift("L2W")))
    rows.append(_h("", "END OF HEADER"))
    return rows


def _crx(lines: list[str]) -> bytes:
    text = "\n".join([
        _h("3.0", "CRINEX VERS / TYPE"),
        _h("TEST", "CRINEX PROG / DATE"),
        *lines,
        "> POISONED OBSERVATION BODY nan inf SECRET",
    ]) + "\n"
    return gzip.compress(text.encode("ascii"))


def test_frozen_plan_is_header_only_and_exact():
    validate_plan(PLAN)
    assert len(PLAN["stations"]) == 8
    assert PLAN["execution"]["hatanaka_body_decoder_forbidden"]
    assert PLAN["persistence"]["observation_values"] is False


def test_gzip_reader_stops_before_first_observation_record():
    lines, receipt = extract_crinex_header(_crx(_header()), maximum_lines=2000)
    assert lines[-1][60:80].strip() == "END OF HEADER"
    assert all("POISONED" not in line for line in lines)
    assert receipt["observation_body_lines_exposed"] == 0
    assert receipt["crinex_preamble"] == ["CRINEX VERS / TYPE", "CRINEX PROG / DATE"]


def test_standard_rinex_phase_coordinate_is_explicit():
    result = audit_header(_header(), PLAN, "ALGO00CAN")
    ledger = result["transform_ledger"]
    assert result["status"] == "HEADER_PHASE_TRANSFORMS_QUALIFIED"
    assert ledger["stored_value_scale_divisor"] == {name: 1 for name in ("C1C", "C2W", "L1C", "L2W")}
    assert ledger["legacy_wavelength_factor"]["present"] is False
    assert ledger["legacy_wavelength_factor"]["numeric_phase_rescaling_authorized"] is False


def test_legacy_factor_two_changes_ambiguity_not_stored_cycle_scale():
    result = audit_header(_header(extra=[_wavelength(1, 2)]), PLAN, "DRAO00CAN")
    legacy = result["transform_ledger"]["legacy_wavelength_factor"]
    assert legacy["default_ambiguity_wavelength_divisor"] == {"L1": 1, "L2": 2}
    assert legacy["numeric_phase_unit"] == "carrier_cycles"
    assert legacy["numeric_phase_rescaling_authorized"] is False
    assert legacy["future_nonzero_lli_breaks_segment"] is True


def test_legacy_satellite_override_is_retained_exactly():
    result = audit_header(
        _header(extra=[_wavelength(1, 1), _wavelength(1, 2, ("G07", "G14"))]),
        PLAN,
        "DRAO00CAN",
    )
    overrides = result["transform_ledger"]["legacy_wavelength_factor"]["satellite_overrides"]
    assert overrides == {"G07": {"L1": 1, "L2": 2}, "G14": {"L1": 1, "L2": 2}}


def test_legacy_factor_zero_rejects_required_l2():
    with pytest.raises(HeaderRejected, match="REQUIRED_L2_WAVELENGTH_UNAVAILABLE"):
        audit_header(_header(extra=[_wavelength(1, 0)]), PLAN, "DRAO00CAN")


def test_rinex_scale_factor_is_an_exact_divisor():
    result = audit_header(_header(extra=[_scale(10, ("L1C", "L2W"))]), PLAN, "TEST00XXX")
    assert result["transform_ledger"]["stored_value_scale_divisor"] == {
        "C1C": 1, "C2W": 1, "L1C": 10, "L2W": 10,
    }


def test_unknown_or_missing_required_phase_alignment_rejects():
    with pytest.raises(HeaderRejected, match="MISSING_REQUIRED_PHASE_SHIFT"):
        audit_header(_header(phase=False), PLAN, "TEST00XXX")
    unknown = _header(phase=False, extra=[_h("G", "SYS / PHASE SHIFT")])
    with pytest.raises(HeaderRejected, match="UNKNOWN_GPS_PHASE_ALIGNMENT"):
        audit_header(unknown, PLAN, "TEST00XXX")


def test_applied_external_gps_correction_needs_its_own_frozen_product():
    row = _h(f"G {'PROGRAM':<17} {'https://example.invalid/model':<40}", "SYS / DCBS APPLIED")
    with pytest.raises(HeaderRejected, match="UNQUALIFIED_APPLIED_EXTERNAL_CORRECTION"):
        audit_header(_header(extra=[row]), PLAN, "TEST00XXX")


def test_marker_type_is_descriptive_and_strict_json_rejects_nonfinite():
    lines = _header()
    index = next(i for i, row in enumerate(lines) if row[60:80].strip() == "MARKER TYPE")
    lines[index] = _h("NON_GEODETIC", "MARKER TYPE")
    assert audit_header(lines, PLAN, "TEST00XXX")["marker_type"] == "NON_GEODETIC"
    for value in (float("nan"), float("inf"), -float("inf")):
        with pytest.raises(ValueError):
            _strict_json({"bad": value})


def test_time_and_plan_scope_cannot_be_shifted_post_hoc():
    shifted = deepcopy(PLAN)
    shifted["date_gpst"] = "2026-09-09"
    with pytest.raises(ValueError, match="date/day-of-year"):
        validate_plan(shifted)
    lines = _header()
    index = next(i for i, row in enumerate(lines) if row[60:80].strip() == "TIME OF LAST OBS")
    lines[index] = _h("  2026     9     8    23    59    0.0000000     GPS", "TIME OF LAST OBS")
    with pytest.raises(HeaderRejected, match="HEADER_DOES_NOT_COVER_FROZEN_DAY"):
        audit_header(lines, PLAN, "TEST00XXX")
