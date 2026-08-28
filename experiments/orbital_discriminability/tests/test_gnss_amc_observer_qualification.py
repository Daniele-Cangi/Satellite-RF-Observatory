from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.orbital_discriminability import gnss_amc_observer_qualification as amc


SECRET_OBSERVATION_TOKEN = "987654321.123"
ROOT = Path(amc.__file__).resolve().parent
FROZEN_SOURCE_COMMIT = "d8281f2d183b274c5d8f94a7769051440ad95da0"
FROZEN_SOURCE_SHA256 = (
    "6bc2044f78e8afeb2f31a74d47b716ebbbde86350b78503ce135c8bf8f6d3fa6"
)
FROZEN_MANIFEST_SHA256 = (
    "5f06900060478f72993a801db5a47ad6aef674b36b847e6aa10ed869abe7cc40"
)
FROZEN_SEAL_SHA256 = "ffd6b009a9e13d05c7b879b5cbb795376d2f9ba1ddeb0ac17bd66ffff3b523ad"
AUTHORITY_MARKER_SHA256 = (
    "7379ed30f51d06f6a3b2cffdf2e5b22d4ce0425ae99383f8e3c589558caa4310"
)
OUTCOME_SHA256 = "8c543bbd5d00128c70feab66574df4b878983f036daab932ba7cb6714ee829c4"
SUMMARY_SHA256 = "3e1be4ca9ef741690af99d6206ff94719fbae32b97fe6792034ac87ac9efca69"
COVERAGE_SHA256 = "bfaccd2ca742f329fe56d6df5e88774c73790040eca2bee5eb3c6ca907718077"


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
        amc.OBSERVABLES
        if optional_declared
        else tuple(
            item for item in amc.OBSERVABLES if item not in amc.OPTIONAL_DIAGNOSTIC
        )
    )
    config = amc.EXPECTED_CONFIGURATION
    receiver = (
        f"{config['receiver_serial']:<20}{config['receiver_type']:<20}"
        f"{config['receiver_version']:<20}"
    )
    antenna = f"{config['antenna_serial']:<20}{config['antenna_type']:<20}{'':<20}"
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
            "  2026     8    10     0     0    0.0000000     GPS",
            "TIME OF FIRST OBS",
        ),
        header_line(
            "  2026     8    10    23    59   30.0000000     GPS",
            "TIME OF LAST OBS",
        ),
        header_line("", "END OF HEADER"),
    ]
    for index, epoch in enumerate(amc.expected_epochs()):
        flag = epoch_flag[1] if epoch_flag and epoch_flag[0] == index else 0
        lines.append(
            f"> {epoch.year:4d} {epoch.month:02d} {epoch.day:02d} "
            f"{epoch.hour:02d} {epoch.minute:02d} "
            f"{float(epoch.second):10.7f}  {flag:d}  2\n"
        )
        for satellite in amc.SATELLITES:
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


def scanned(**kwargs) -> amc.StationScan:
    return amc.scan_decoded(fixture(**kwargs))


def test_manifest_freezes_only_doy222_and_has_no_primary_locator() -> None:
    manifest = amc.manifest()
    encoded = amc.strict_json(manifest)

    assert "/2026/222/" in manifest["qualification_product"]["url"]
    assert "2026222" in manifest["qualification_product"]["name"]
    assert "/221/" not in encoded
    assert "2026221" not in encoded
    assert manifest["admission"]["code_required_raw_indices"] == [0, 78, 79, 138]
    assert manifest["parser_boundary"].endswith("NO_OBSERVATION_SCALAR_CONVERSION")
    assert manifest["transport_repair"] == {
        "reason": "CDDIS_GET_REDIRECTED_TO_EARTHDATA_LOGIN_HTML",
        "source": "GSSC_OFFICIAL_GLOBAL_DATA_CENTER",
        "authentication": "DOCUMENTED_ANONYMOUS_WEB_SESSION",
        "client": "REQUESTS_SESSION_WITH_EXPLICIT_COOKIE_CONTINUITY",
        "web_root": "https://gssc.esa.int/webftp/",
        "directory_components": ["gnss", "data", "daily", "2026", "222"],
        "same_frozen_product_name": True,
        "physical_contract_changed": False,
    }


def test_frozen_grid_and_heldout_boundary_are_exact() -> None:
    epochs = amc.expected_epochs()

    assert len(epochs) == 139
    assert epochs[0] == amc.QUALIFICATION_RAW_START_GPS
    assert epochs[79] == amc.HELDOUT_BOUNDARY_GPS
    assert epochs[-1] == amc.QUALIFICATION_RAW_STOP_GPS


def test_gssc_directory_parser_accepts_only_exact_product_and_size() -> None:
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<alldata><nowdir>/gnss/data/daily/2026/222</nowdir><dirdata>
<rowdata><perm>-rw-r--r--</perm><dir>0</dir>
<size>{amc.EXPECTED_COMPRESSED_BYTES}</size>
<date>{amc.EXPECTED_DIRECTORY_MODIFIED}</date>
<name>{amc.QUALIFICATION_PRODUCT.name}</name>
<md5>1</md5></rowdata>
</dirdata></alldata>""".encode("ascii")

    result = amc._gssc_product_metadata(xml)

    assert result["name"] == amc.QUALIFICATION_PRODUCT.name
    assert result["bytes"] == amc.EXPECTED_COMPRESSED_BYTES
    assert result["md5"] == "1"

    changed = xml.replace(str(amc.EXPECTED_COMPRESSED_BYTES).encode("ascii"), b"123")
    with pytest.raises(amc.MaterializationError, match="GSSC_DECLARED_SIZE_CHANGED"):
        amc._gssc_product_metadata(changed)


def test_gssc_download_url_preserves_bare_wingftp_flag() -> None:
    assert amc._gssc_download_url() == (
        "https://gssc.esa.int/webftp/?download&filename="
        "AMC400USA_R_20262220000_01D_30S_MO.crx.gz"
    )
    assert "download=" not in amc._gssc_download_url()


def test_offline_manifest_does_not_load_live_transport(monkeypatch) -> None:
    def forbidden_import(name: str):
        raise AssertionError(f"offline manifest attempted import: {name}")

    monkeypatch.setattr(amc, "import_module", forbidden_import)

    assert amc.manifest()["qualification_product"]["name"] == (
        "AMC400USA_R_20262220000_01D_30S_MO.crx.gz"
    )


def test_complete_structure_passes_without_measurement_or_score() -> None:
    scan = scanned()
    try:
        summary = amc.evaluate(scan)
    finally:
        scan.erase()

    assert summary["outcome"] == "AMC_OBSERVER_QUALIFICATION_PASSED"
    assert summary["coverage_rows"] == 139 * 2 * 6
    assert summary["full_joint_window"] is True
    assert summary["same_path_code_witness"]["state"] == "SATISFIED"
    assert summary["measurement_admission"] == "NOT_EVALUATED"
    assert summary["orbital_score"] == "NOT_EVALUATED"
    assert summary["observation_values_parsed"] == 0


def test_missing_core_breaks_segment_without_gap_bridging() -> None:
    scan = scanned(blank=(100, "G22", "L2W"))
    try:
        summary = amc.evaluate(scan)
    finally:
        scan.erase()

    link = next(
        row for row in summary["per_link_core_segments"] if row["satellite"] == "G22"
    )
    assert [segment["epoch_count"] for segment in link["maximal_segments"]] == [
        100,
        38,
    ]
    assert summary["outcome"] == "AMC_OBSERVER_QUALIFICATION_FAILED"


def test_nonzero_lli_breaks_continuity_without_parsing_phase() -> None:
    scan = scanned(lli=(79, "G30", "L1C"))
    try:
        summary = amc.evaluate(scan)
        row = next(
            row
            for row in scan.coverage
            if row["gps_epoch"] == "2026-08-10T06:17:00 GPS"
            and row["satellite"] == "G30"
            and row["observable"] == "L1C"
        )
    finally:
        scan.erase()

    assert row["lli_state"] == "NONZERO"
    assert summary["outcome"] == "AMC_OBSERVER_QUALIFICATION_FAILED"


def test_code_witness_policy_is_quantitative_and_boundary_sensitive() -> None:
    nonboundary = scanned(blank=(100, "G22", "C1C"))
    boundary = scanned(blank=(79, "G22", "C1C"))
    try:
        nonboundary_summary = amc.evaluate(nonboundary)
        boundary_summary = amc.evaluate(boundary)
    finally:
        nonboundary.erase()
        boundary.erase()

    assert nonboundary_summary["same_path_code_witness"]["state"] == "SATISFIED"
    assert nonboundary_summary["outcome"] == "AMC_OBSERVER_QUALIFICATION_PASSED"
    assert boundary_summary["same_path_code_witness"]["state"] == "UNSATISFIED"
    assert boundary_summary["outcome"] == "AMC_OBSERVER_QUALIFICATION_FAILED"


def test_optional_diagnostics_are_not_fatal_when_not_declared() -> None:
    scan = scanned(optional_declared=False)
    try:
        summary = amc.evaluate(scan)
    finally:
        scan.erase()

    assert summary["outcome"] == "AMC_OBSERVER_QUALIFICATION_PASSED"
    assert summary["optional_diagnostic_policy"] == "DESCRIPTIVE_ONLY_NEVER_FATAL"


def test_observation_tokens_never_enter_receipts() -> None:
    scan = scanned()
    try:
        encoded = amc.strict_json(
            {"coverage": scan.coverage, "summary": amc.evaluate(scan)}
        )
    finally:
        scan.erase()

    assert SECRET_OBSERVATION_TOKEN not in encoded
    assert '"value"' not in encoded


def test_parent_hashes_are_bound_and_tampering_is_descriptive(monkeypatch) -> None:
    root = Path(amc.__file__).resolve().parent
    amc.verify_parent_artifacts(root)

    original = amc.canonical_sha256

    def tampered(path: Path) -> str:
        if Path(path).name == amc.PARENT_REPORT_NAME:
            return "0" * 64
        return original(path)

    monkeypatch.setattr(amc, "canonical_sha256", tampered)

    with pytest.raises(amc.DescriptionError, match="FROZEN_PARENT_CHANGED"):
        amc.verify_parent_artifacts(root)


def test_outcome_receipt_keeps_primary_and_values_at_zero(monkeypatch) -> None:
    monkeypatch.setattr(amc, "_git_commit", lambda: "a" * 40)
    outcome = amc._base_outcome("AMC_OBSERVER_QUALIFICATION_FAILED", None)

    assert outcome["primary_doy221_access"] == {
        "locator_requests": 0,
        "headers": 0,
        "payload_bytes": 0,
        "values": 0,
    }
    assert outcome["persistence"]["observation_values"] == 0
    assert outcome["orbital_scores_produced"] == 0


def frozen_seal(tmp_path: Path, monkeypatch) -> tuple[Path, str]:
    monkeypatch.setattr(amc, "_git_commit", lambda: "a" * 40)
    root = Path(amc.__file__).resolve().parent
    seal = amc.build_executor_seal(root)
    path = tmp_path / amc.EXECUTOR_SEAL_NAME
    amc._write_json(path, seal)
    return path, amc.canonical_sha256(path)


def test_executor_seal_binds_source_manifest_parents_and_zero_access(
    tmp_path, monkeypatch
) -> None:
    seal_path, seal_sha = frozen_seal(tmp_path, monkeypatch)
    root = Path(amc.__file__).resolve().parent

    seal = amc.validate_executor_seal(root, seal_path, seal_sha)
    encoded = amc.strict_json(seal)

    assert seal["state"] == "AMC_OBSERVER_QUALIFICATION_EXECUTOR_FROZEN_UNOPENED"
    assert seal["source_sha256"] == amc.source_sha256()
    assert seal["manifest_sha256"] == amc.manifest_sha256()
    assert not any(seal["access_at_seal"].values())
    assert seal["authority"]["live_execution_authorized_by_seal"] is False
    assert "/221/" not in encoded
    assert "2026221" not in encoded


def test_committed_executor_seal_is_exact_and_was_frozen_unopened() -> None:
    seal_path = ROOT / amc.EXECUTOR_SEAL_NAME

    assert amc.source_sha256() == FROZEN_SOURCE_SHA256
    assert amc.manifest_sha256() == FROZEN_MANIFEST_SHA256
    assert amc.canonical_sha256(seal_path) == FROZEN_SEAL_SHA256

    seal = amc.validate_executor_seal(ROOT, seal_path, FROZEN_SEAL_SHA256)

    assert seal["source_commit"] == FROZEN_SOURCE_COMMIT
    assert seal["source_sha256"] == FROZEN_SOURCE_SHA256
    assert seal["manifest_sha256"] == FROZEN_MANIFEST_SHA256
    assert not any(seal["access_at_seal"].values())
    assert seal["stop"] == "SEPARATE_EXPLICIT_LIVE_QUALIFICATION_AUTHORITY_REQUIRED"


def test_single_committed_qualification_outcome_is_exact_and_value_blind() -> None:
    marker_path = ROOT / amc.AUTHORITY_MARKER_NAME
    outcome_path = ROOT / amc.OUTCOME_NAME
    summary_path = ROOT / amc.SUMMARY_NAME
    coverage_path = ROOT / amc.COVERAGE_NAME

    assert amc.canonical_sha256(marker_path) == AUTHORITY_MARKER_SHA256
    assert amc.canonical_sha256(outcome_path) == OUTCOME_SHA256
    assert amc.canonical_sha256(summary_path) == SUMMARY_SHA256
    assert amc.canonical_sha256(coverage_path) == COVERAGE_SHA256

    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    outcome = json.loads(outcome_path.read_text(encoding="utf-8"))
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    coverage = coverage_path.read_bytes().replace(b"\r\n", b"\n")

    assert marker["state"] == "ONE_SHOT_AUTHORITY_CONSUMED_BEFORE_NETWORK"
    assert marker["executor_seal_sha256"] == FROZEN_SEAL_SHA256
    assert marker["network_requests_before_marker"] == 0
    assert marker["primary_doy221_access_before_marker"] == 0

    assert outcome["outcome"] == "AMC_OBSERVER_QUALIFICATION_PASSED"
    assert outcome["artifact"]["attempts"] == 1
    assert outcome["artifact"]["complete_file_bytes"] == 3_455_043
    assert outcome["artifact"]["complete_file_sha256"] == (
        "1b2257350a6cadb5713c5db9316b87bc1cd61dc49e71533189741e3b1a45cea8"
    )
    assert outcome["artifact"]["hash_before_any_decompression_or_record_scan"] is True
    assert outcome["clause_states"]["core_phase_and_lli"] == "SATISFIED"
    assert outcome["clause_states"]["same_path_code_witness"] == "SATISFIED"
    assert outcome["clause_states"]["measurement_admission"] == "NOT_EVALUATED"
    assert outcome["clause_states"]["primary_orbital_comparison"] == "NOT_EVALUATED"
    assert outcome["observation_access"]["observation_values_parsed"] == 0
    assert outcome["observation_access"]["observation_values_persisted"] == 0
    assert outcome["persistence"]["compressed_rinex_bytes"] == 0
    assert outcome["persistence"]["decoded_rinex_bytes"] == 0
    assert not any(outcome["primary_doy221_access"].values())
    assert outcome["orbital_scores_produced"] == 0

    assert summary["outcome"] == "AMC_OBSERVER_QUALIFICATION_PASSED"
    assert summary["structural_counts"] == {"PRESENT": 1668}
    assert summary["coverage_rows"] == 1668
    assert summary["full_joint_window"] is True
    assert summary["parser_issues"] == []
    assert summary["same_path_code_witness"]["state"] == "SATISFIED"
    assert summary["geometry_free_phase_health"] == (
        "NOT_EVALUATED_BY_VALUE_BLIND_AUTHORITY"
    )

    assert coverage.count(b"\n") == 1668
    assert b'"value"' not in coverage
    assert b"NaN" not in coverage and b"Infinity" not in coverage
    assert not (ROOT / amc.QUALIFICATION_PRODUCT.name).exists()


def test_wrong_authority_stops_before_seal_and_network(tmp_path, monkeypatch) -> None:
    touched = {"seal": False, "network": False}

    def seal_forbidden(*_args):
        touched["seal"] = True
        raise AssertionError("seal should not be read")

    def network_forbidden():
        touched["network"] = True
        raise AssertionError("network should not be used")

    monkeypatch.setattr(amc, "validate_executor_seal", seal_forbidden)

    with pytest.raises(PermissionError, match="AUTHORITY_REQUIRED"):
        amc.run_once(
            tmp_path,
            "WRONG",
            "0" * 64,
            tmp_path / "missing.json",
            materializer=network_forbidden,
        )

    assert touched == {"seal": False, "network": False}


def test_one_shot_marker_precedes_materialization_and_blocks_second_run(
    tmp_path, monkeypatch
) -> None:
    seal_path, seal_sha = frozen_seal(tmp_path, monkeypatch)
    compressed = bytearray(b"compressed")
    calls = 0

    def materializer():
        nonlocal calls
        calls += 1
        marker_path = tmp_path / amc.AUTHORITY_MARKER_NAME
        assert marker_path.is_file()
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        assert marker["network_requests_before_marker"] == 0
        return compressed, {
            "complete_file_sha256": "b" * 64,
            "complete_file_bytes": len(compressed),
            "attempts": 1,
        }

    result = amc.run_once(
        tmp_path,
        amc.AUTHORITY_TOKEN,
        seal_sha,
        seal_path,
        materializer=materializer,
        decompressor=lambda _payload: fixture(),
    )

    assert calls == 1
    assert result["outcome"] == "AMC_OBSERVER_QUALIFICATION_PASSED"
    assert result["executor_seal_sha256"] == seal_sha
    assert result["primary_doy221_access"]["payload_bytes"] == 0
    assert compressed == bytearray(len(compressed))
    written = (tmp_path / amc.OUTCOME_NAME).read_text(encoding="utf-8")
    assert SECRET_OBSERVATION_TOKEN not in written

    with pytest.raises(PermissionError, match="ALREADY_CONSUMED"):
        amc.run_once(
            tmp_path,
            amc.AUTHORITY_TOKEN,
            seal_sha,
            seal_path,
            materializer=materializer,
        )
    assert calls == 1


def test_transport_only_retry_is_bounded_before_complete_hash(monkeypatch) -> None:
    class Session:
        def close(self):
            pass

    attempts = 0

    def session():
        return Session()

    def navigate(_session):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise amc.TransportInterruption("TIMEOUT")
        return {
            "directory": "/gnss/data/daily/2026/222",
            "md5": "1",
            "modified": amc.EXPECTED_DIRECTORY_MODIFIED,
        }

    monkeypatch.setattr(amc, "EXPECTED_COMPRESSED_BYTES", 4)
    monkeypatch.setattr(amc, "_new_gssc_session", session)
    monkeypatch.setattr(amc, "_navigate_gssc", navigate)
    monkeypatch.setattr(
        amc,
        "_download_gssc",
        lambda _session: (bytearray(b"\x1f\x8bxx"), {}),
    )

    payload, receipt = amc.materialize()

    assert payload == b"\x1f\x8bxx"
    assert receipt["attempts"] == 2
    assert attempts == 2


def test_description_failure_is_not_retried(monkeypatch) -> None:
    class Session:
        def close(self):
            pass

    calls = 0

    def navigate(_session):
        nonlocal calls
        calls += 1
        raise amc.MaterializationError("GSSC_PRODUCT_MATCH_COUNT:0")

    monkeypatch.setattr(amc, "_new_gssc_session", Session)
    monkeypatch.setattr(amc, "_navigate_gssc", navigate)

    with pytest.raises(amc.MaterializationError, match="GSSC_PRODUCT_MATCH_COUNT"):
        amc.materialize()
    assert calls == 1
