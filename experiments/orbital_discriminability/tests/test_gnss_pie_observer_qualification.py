from __future__ import annotations

from pathlib import Path

import pytest

from experiments.orbital_discriminability import gnss_pie_observer_qualification as pie


SECRET_OBSERVATION_TOKEN = "987654321.123"


def header_line(data: str, label: str) -> str:
    return f"{data:<60}{label:<20}\n"


def field(value: str | None, lli: str = " ") -> str:
    if value is None:
        return " " * 16
    return f"{value:>14}{lli} "


def fixture(
    *,
    blank: tuple[int, str, str] | None = None,
    lli: tuple[int, str, str] | None = None,
    epoch_flag: tuple[int, int] | None = None,
    optional_declared: bool = True,
) -> bytearray:
    observables = (
        pie.OBSERVABLES
        if optional_declared
        else tuple(
            item for item in pie.OBSERVABLES if item not in pie.OPTIONAL_DIAGNOSTIC
        )
    )
    config = pie.EXPECTED_CONFIGURATION
    receiver = (
        f"{config['receiver_serial']:<20}{config['receiver_type']:<20}"
        f"{config['receiver_version']:<20}"
    )
    antenna = f"{config['antenna_serial']:<20}{config['antenna_type']:<20}" f"{'':<20}"
    obs_declaration = f"G  {len(observables):3d} " + " ".join(observables)
    lines = [
        header_line(
            "     3.04           OBSERVATION DATA    G",
            "RINEX VERSION / TYPE",
        ),
        header_line(config["marker_name"], "MARKER NAME"),
        header_line(receiver, "REC # / TYPE / VERS"),
        header_line(antenna, "ANT # / TYPE"),
        header_line(" -1640916.0 -5014782.0 3575447.0", "APPROX POSITION XYZ"),
        header_line(obs_declaration, "SYS / # / OBS TYPES"),
        header_line("      30.000", "INTERVAL"),
        header_line(
            "  2026     8     9     0     0    0.0000000     GPS",
            "TIME OF FIRST OBS",
        ),
        header_line(
            "  2026     8     9    23    59   30.0000000     GPS",
            "TIME OF LAST OBS",
        ),
        header_line("", "END OF HEADER"),
    ]
    for index, epoch in enumerate(pie.expected_epochs()):
        flag = epoch_flag[1] if epoch_flag and epoch_flag[0] == index else 0
        lines.append(
            f"> {epoch.year:4d} {epoch.month:02d} {epoch.day:02d} "
            f"{epoch.hour:02d} {epoch.minute:02d} "
            f"{float(epoch.second):10.7f}  {flag:d}  2\n"
        )
        for satellite in pie.SATELLITES:
            fields = []
            for observable in observables:
                value = (
                    None
                    if blank == (index, satellite, observable)
                    else SECRET_OBSERVATION_TOKEN
                )
                lli_token = "1" if lli == (index, satellite, observable) else " "
                fields.append(field(value, lli_token))
            lines.append(satellite + "".join(fields) + "\n")
    return bytearray("".join(lines).encode("ascii"))


def scanned(**kwargs) -> pie.StationScan:
    return pie.scan_decoded(fixture(**kwargs))


def test_manifest_freezes_only_doy221_and_has_no_primary_locator() -> None:
    manifest = pie.manifest()
    encoded = pie.strict_json(manifest)

    assert "/2026/221/" in manifest["qualification_product"]["url"]
    assert "2026221" in manifest["qualification_product"]["name"]
    assert "/223/" not in encoded
    assert "2026223" not in encoded
    assert manifest["admission"]["code_required_raw_indices"] == [0, 78, 79, 138]
    assert manifest["parser_boundary"].endswith("NO_OBSERVATION_SCALAR_CONVERSION")
    assert manifest["transport_repair"] == {
        "reason": "CDDIS_GET_REDIRECTED_TO_EARTHDATA_LOGIN_HTML",
        "source": "GSSC_OFFICIAL_GLOBAL_DATA_CENTER",
        "authentication": "DOCUMENTED_ANONYMOUS_WEB_SESSION",
        "web_root": "https://gssc.esa.int/webftp/",
        "directory_components": ["gnss", "data", "daily", "2026", "221"],
        "same_frozen_product_name": True,
        "physical_contract_changed": False,
    }


def test_frozen_grid_and_heldout_boundary_are_exact() -> None:
    epochs = pie.expected_epochs()

    assert len(epochs) == 139
    assert epochs[0] == pie.QUALIFICATION_RAW_START_GPS
    assert epochs[79] == pie.HELDOUT_BOUNDARY_GPS
    assert epochs[-1] == pie.QUALIFICATION_RAW_STOP_GPS


def test_gssc_directory_parser_accepts_only_exact_product_and_size() -> None:
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<alldata><nowdir>/gnss/data/daily/2026/221</nowdir><dirdata>
<rowdata><perm>-rw-r--r--</perm><dir>0</dir>
<size>{pie.EXPECTED_HEAD_CONTENT_LENGTH}</size><date>2026-08-10</date>
<name>{pie.QUALIFICATION_PRODUCT.name}</name>
<md5>{'a' * 32}</md5></rowdata>
</dirdata></alldata>""".encode(
        "ascii"
    )

    result = pie._gssc_product_metadata(xml)

    assert result["name"] == pie.QUALIFICATION_PRODUCT.name
    assert result["bytes"] == pie.EXPECTED_HEAD_CONTENT_LENGTH
    assert result["md5"] == "a" * 32

    changed = xml.replace(str(pie.EXPECTED_HEAD_CONTENT_LENGTH).encode("ascii"), b"123")
    with pytest.raises(pie.MaterializationError, match="GSSC_AND_CDDIS_SIZE_DISAGREE"):
        pie._gssc_product_metadata(changed)


def test_complete_structure_passes_without_measurement_or_score() -> None:
    scan = scanned()
    try:
        summary = pie.evaluate(scan)
    finally:
        scan.erase()

    assert summary["outcome"] == "PIE_OBSERVER_QUALIFICATION_PASSED"
    assert summary["coverage_rows"] == 139 * 2 * 6
    assert summary["full_joint_window"] is True
    assert summary["same_path_code_witness"]["state"] == "SATISFIED"
    assert summary["measurement_admission"] == "NOT_EVALUATED"
    assert summary["orbital_score"] == "NOT_EVALUATED"
    assert summary["observation_values_parsed"] == 0


def test_missing_core_breaks_segment_without_gap_bridging() -> None:
    scan = scanned(blank=(100, "G22", "L2W"))
    try:
        summary = pie.evaluate(scan)
    finally:
        scan.erase()

    link = next(
        row for row in summary["per_link_core_segments"] if row["satellite"] == "G22"
    )
    assert [segment["epoch_count"] for segment in link["maximal_segments"]] == [
        100,
        38,
    ]
    assert summary["outcome"] == "PIE_OBSERVER_QUALIFICATION_FAILED"


def test_nonzero_lli_breaks_continuity_without_parsing_phase() -> None:
    scan = scanned(lli=(79, "G30", "L1C"))
    try:
        summary = pie.evaluate(scan)
        row = next(
            row
            for row in scan.coverage
            if row["gps_epoch"] == "2026-08-09T06:30:00 GPS"
            and row["satellite"] == "G30"
            and row["observable"] == "L1C"
        )
    finally:
        scan.erase()

    assert row["lli_state"] == "NONZERO"
    assert summary["outcome"] == "PIE_OBSERVER_QUALIFICATION_FAILED"


def test_code_witness_policy_is_quantitative_and_boundary_sensitive() -> None:
    nonboundary = scanned(blank=(100, "G22", "C1C"))
    boundary = scanned(blank=(79, "G22", "C1C"))
    try:
        nonboundary_summary = pie.evaluate(nonboundary)
        boundary_summary = pie.evaluate(boundary)
    finally:
        nonboundary.erase()
        boundary.erase()

    assert nonboundary_summary["same_path_code_witness"]["state"] == "SATISFIED"
    assert nonboundary_summary["outcome"] == "PIE_OBSERVER_QUALIFICATION_PASSED"
    assert boundary_summary["same_path_code_witness"]["state"] == "UNSATISFIED"
    assert boundary_summary["outcome"] == "PIE_OBSERVER_QUALIFICATION_FAILED"


def test_optional_diagnostics_are_not_fatal_when_not_declared() -> None:
    scan = scanned(optional_declared=False)
    try:
        summary = pie.evaluate(scan)
    finally:
        scan.erase()

    assert summary["outcome"] == "PIE_OBSERVER_QUALIFICATION_PASSED"
    assert summary["optional_diagnostic_policy"] == "DESCRIPTIVE_ONLY_NEVER_FATAL"


def test_observation_tokens_never_enter_receipts() -> None:
    scan = scanned()
    try:
        encoded = pie.strict_json(
            {"coverage": scan.coverage, "summary": pie.evaluate(scan)}
        )
    finally:
        scan.erase()

    assert SECRET_OBSERVATION_TOKEN not in encoded
    assert '"value"' not in encoded


def test_parent_hashes_are_bound_and_tampering_is_descriptive(monkeypatch) -> None:
    root = Path(pie.__file__).resolve().parent
    pie.verify_parent_artifacts(root)

    original = pie.canonical_sha256

    def tampered(path: Path) -> str:
        if Path(path).name == pie.PARENT_REPORT_NAME:
            return "0" * 64
        return original(path)

    monkeypatch.setattr(pie, "canonical_sha256", tampered)

    with pytest.raises(pie.DescriptionError, match="FROZEN_PARENT_CHANGED"):
        pie.verify_parent_artifacts(root)


def test_outcome_receipt_keeps_primary_and_values_at_zero(monkeypatch) -> None:
    monkeypatch.setattr(pie, "_git_commit", lambda: "a" * 40)
    outcome = pie._base_outcome("PIE_OBSERVER_QUALIFICATION_FAILED", None)

    assert outcome["primary_doy223_access"] == {
        "locator_requests": 0,
        "headers": 0,
        "payload_bytes": 0,
        "values": 0,
    }
    assert outcome["persistence"]["observation_values"] == 0
    assert outcome["orbital_scores_produced"] == 0
