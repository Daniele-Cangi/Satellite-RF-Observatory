from __future__ import annotations

from pathlib import Path

from experiments.orbital_discriminability import gnss_phase_structural_contract as contract
from experiments.orbital_discriminability import gnss_phase_structural_scan as scan


def header_line(data: str, label: str) -> str:
    return f"{data:<60}{label:<20}\n"


def field(value: str | None, lli: str = " ") -> str:
    if value is None:
        return " " * 16
    return f"{value:>14}{lli} "


def fixture(
    locator: scan.ProductLocator,
    *,
    blank: tuple[int, str, str] | None = None,
    lli: tuple[int, str, str] | None = None,
    epoch_flag: tuple[int, int] | None = None,
) -> bytearray:
    config = scan.EXPECTED_CONFIGURATION[locator.station]
    lines = [
        header_line(
            "     3.04           OBSERVATION DATA    G",
            "RINEX VERSION / TYPE",
        ),
        header_line(locator.station[:4], "MARKER NAME"),
        header_line(
            f"SERIAL              {config['receiver_type']:<20}"
            f"{config['receiver_version']:<20}",
            "REC # / TYPE / VERS",
        ),
        header_line(
            f"ANTENNA             {config['antenna_type']:<20}", "ANT # / TYPE"
        ),
        header_line(" -2350000.0 -4650000.0 3670000.0", "APPROX POSITION XYZ"),
        header_line("G    6 C1C L1C S1C C2W L2W S2W", "SYS / # / OBS TYPES"),
        header_line("      30.000", "INTERVAL"),
        header_line(
            "  2026     8     4     0     0    0.0000000     GPS",
            "TIME OF FIRST OBS",
        ),
        header_line(
            "  2026     8     4    23    59   30.0000000     GPS",
            "TIME OF LAST OBS",
        ),
        header_line("", "END OF HEADER"),
    ]
    secret = "987654321.123"
    for index, epoch in enumerate(scan.expected_epochs()):
        flag = epoch_flag[1] if epoch_flag and epoch_flag[0] == index else 0
        lines.append(
            f"> {epoch.year:4d} {epoch.month:02d} {epoch.day:02d} "
            f"{epoch.hour:02d} {epoch.minute:02d} "
            f"{float(epoch.second):10.7f}  {flag:d}  2\n"
        )
        for satellite in scan.SATELLITES:
            fields = []
            for observable in scan.OBSERVABLES:
                value = (
                    None
                    if blank == (index, satellite, observable)
                    else secret
                )
                lli_token = "1" if lli == (index, satellite, observable) else " "
                fields.append(field(value, lli_token))
            lines.append(satellite + "".join(fields) + "\n")
    return bytearray("".join(lines).encode("ascii"))


def complete_scans(**kwargs):
    return tuple(
        scan.scan_decoded(fixture(locator, **kwargs), locator)
        for locator in scan.PRODUCTS
    )


def erase(scans) -> None:
    for item in scans:
        item.erase()


def test_complete_structure_reaches_only_health_review() -> None:
    scans = complete_scans()
    try:
        summary = scan.evaluate(scans)
    finally:
        erase(scans)

    assert summary["outcome"] == "GNSS_PHASE_STRUCTURE_READY_FOR_HEALTH_REVIEW"
    assert summary["coverage_rows"] == 2 * 386 * 2 * 6
    assert summary["full_joint_window"] is True
    assert summary["geometry_free_phase_health"] == (
        "NOT_EVALUATED_BY_STRUCTURAL_ONLY_AUTHORITY"
    )
    assert summary["measurement_admission"] == "NOT_EVALUATED"


def test_missing_core_breaks_segment_without_gap_bridging() -> None:
    scans = complete_scans(blank=(100, "G22", "L2W"))
    try:
        summary = scan.evaluate(scans)
    finally:
        erase(scans)

    link = next(
        row
        for row in summary["per_link_core_segments"]
        if row["station"] == "GOLD00USA" and row["satellite"] == "G22"
    )
    assert [segment["epoch_count"] for segment in link["maximal_segments"]] == [
        100,
        285,
    ]
    assert summary["outcome"] == "GNSS_PHASE_STRUCTURE_REJECTED"


def test_nonzero_lli_rejects_without_parsing_phase() -> None:
    scans = complete_scans(lli=(200, "G30", "L1C"))
    try:
        summary = scan.evaluate(scans)
        row = next(
            row
            for row in scans[0].coverage
            if row["gps_epoch"] == "2026-08-04T06:27:00 GPS"
            and row["satellite"] == "G30"
            and row["observable"] == "L1C"
        )
    finally:
        erase(scans)

    assert row["lli_state"] == "NONZERO"
    assert summary["outcome"] == "GNSS_PHASE_STRUCTURE_REJECTED"


def test_power_failure_epoch_flag_breaks_phase_continuity() -> None:
    scans = complete_scans(epoch_flag=(200, 1))
    try:
        summary = scan.evaluate(scans)
    finally:
        erase(scans)

    assert summary["full_joint_window"] is False
    assert any(
        issue["reason"] == "EPOCH_FLAG_NOT_ZERO_1"
        for issue in summary["parser_issues"]
    )
    assert summary["outcome"] == "GNSS_PHASE_STRUCTURE_REJECTED"


def test_code_witness_is_not_fatal_at_nonboundary_epoch() -> None:
    scans = complete_scans(blank=(100, "G22", "C1C"))
    try:
        summary = scan.evaluate(scans)
    finally:
        erase(scans)

    assert summary["same_path_code_witness"]["state"] == "SATISFIED"
    assert summary["outcome"] == "GNSS_PHASE_STRUCTURE_READY_FOR_HEALTH_REVIEW"


def test_code_witness_boundary_is_fatal() -> None:
    scans = complete_scans(blank=(77, "G22", "C1C"))
    try:
        summary = scan.evaluate(scans)
    finally:
        erase(scans)

    assert summary["same_path_code_witness"]["state"] == "UNSATISFIED"
    assert summary["outcome"] == "GNSS_PHASE_STRUCTURE_REJECTED"


def test_observation_tokens_never_enter_receipts() -> None:
    station = scan.scan_decoded(fixture(scan.PRODUCTS[0]), scan.PRODUCTS[0])
    try:
        encoded = scan.strict_json(station.coverage)
    finally:
        station.erase()

    assert "987654321.123" not in encoded
    assert '"value"' not in encoded


def test_live_surface_is_only_doy216_and_failure_is_not_rejection() -> None:
    assert all("/2026/216/" in product.url for product in scan.PRODUCTS)
    assert all("2026216" in product.name for product in scan.PRODUCTS)
    assert "2026220" not in scan.strict_json(scan.manifest())
    failure = scan.materialization_failure_receipt("TRANSPORT_TIMEOUT")
    assert failure["outcome"] == "GNSS_PHASE_ARTIFACT_MATERIALIZATION_FAILED"
    assert failure["structure"] == "NOT_EVALUATED"


def test_plan_and_contract_are_hash_bound() -> None:
    root = Path(scan.__file__).resolve().parent
    manifest = scan.manifest()

    assert manifest["contract_manifest_sha256"] == contract.contract_sha256()
    assert manifest["plan_canonical_sha256"] == scan.canonical_file_sha256(
        root / scan.PLAN_NAME
    )
    assert manifest["maximum_transport_attempts_per_locator"] == 2
