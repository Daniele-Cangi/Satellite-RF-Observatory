from __future__ import annotations

from datetime import datetime, timedelta, timezone

from experiments.orbital_discriminability import (
    gnss_drao_labelled_forward_structural_runner as runner,
)


SATELLITES = ("G14", "G15", "G17", "G20", "G24", "G30")
SECRET = "987654321.123"


def header_line(data: str, label: str) -> str:
    return f"{data:<60}{label:<20}\n"


def observation_time(epoch: datetime) -> str:
    data = (
        f"{epoch.year:6d}{epoch.month:6d}{epoch.day:6d}"
        f"{epoch.hour:6d}{epoch.minute:6d}{float(epoch.second):13.7f}"
    )
    return data.ljust(48) + "GPS"


def phase_shift(observable: str) -> str:
    return (
        f"G {observable:<3} {0.0:8.5f}  {len(SATELLITES):2d} "
        + " ".join(SATELLITES)
    )


def field(token: str | None, *, lli: str = " ") -> str:
    value = "" if token is None else token
    return f"{value:>14}{lli} "


def fixture(
    *,
    blank: tuple[int, str, str] | None = None,
    nonzero_lli: tuple[int, str, str] | None = None,
    include_extra: bool = False,
) -> bytearray:
    start = datetime(2026, 8, 25, 4, 55, tzinfo=timezone.utc)
    stop = start + timedelta(seconds=30 * 138)
    receiver = f"{'RX123':<20}{'SEPT POLARX5':<20}{'5.2.0':<20}"
    antenna = f"{'ANT123':<20}{'TWIVC6050':<16}{'SCIS':<4}{'':<20}"
    obs = ("C1C", "L1C", "C2W", "L2W")
    lines = [
        header_line("     3.04           OBSERVATION DATA    G", "RINEX VERSION / TYPE"),
        header_line("DRAO", "MARKER NAME"),
        header_line("40105M002", "MARKER NUMBER"),
        header_line(receiver, "REC # / TYPE / VERS"),
        header_line(antenna, "ANT # / TYPE"),
        header_line("  -2059164.0  -3621108.0   4814431.0", "APPROX POSITION XYZ"),
        header_line("30.0", "INTERVAL"),
        header_line(observation_time(start), "TIME OF FIRST OBS"),
        header_line(observation_time(stop), "TIME OF LAST OBS"),
        header_line(
            f"G  {len(obs):3d} " + "".join(f"{item:>3} " for item in obs),
            "SYS / # / OBS TYPES",
        ),
        header_line(phase_shift("L1C"), "SYS / PHASE SHIFT"),
        header_line(phase_shift("L2W"), "SYS / PHASE SHIFT"),
        header_line("", "END OF HEADER"),
    ]
    for index in range(139):
        epoch = start + timedelta(seconds=30 * index)
        tracks = SATELLITES + (("G01",) if include_extra else ())
        lines.append(
            f"> {epoch.year:04d} {epoch.month:02d} {epoch.day:02d} "
            f"{epoch.hour:02d} {epoch.minute:02d} {epoch.second:02d}.0000000  0 "
            f"{len(tracks):2d}\n"
        )
        for satellite in tracks:
            values = []
            for observable in obs:
                token = None if blank == (index, satellite, observable) else SECRET
                lli = "1" if nonzero_lli == (index, satellite, observable) else " "
                values.append(field(token, lli=lli))
            lines.append(satellite + "".join(values) + "\n")
    return bytearray("".join(lines).encode("ascii"))


def test_manifest_is_specific_value_blind_and_orbit_blind() -> None:
    value = runner.manifest()
    surface = value["inspection_surface"]

    assert value["new_gate"] is False
    assert surface["observation_scalar_conversion"] is False
    assert surface["observation_value_serialization"] is False
    assert surface["orbital_model_available"] is False
    assert surface["orbital_scores"] == 0
    assert value["artifact"]["name"] == runner.ARTIFACT_NAME


def test_complete_fixture_is_structurally_ready_without_exposing_values() -> None:
    result = runner.scan_decoded(fixture(include_extra=True))
    encoded = runner.strict_json(result)

    assert result["state"] == "DRAO_LABELLED_FORWARD_STRUCTURE_READY_FOR_INTEGRATED_PROOF"
    assert result["epoch_grid"]["observed"] == 139
    assert result["required_satellite_epoch_pairs"] == 834
    assert result["extra_gps_track_records_descriptive_only"] == 139
    assert result["typed_refusal_reasons"] == []
    assert SECRET not in encoded
    assert result["observation_scalar_conversions"] == 0
    assert result["observation_values_persisted"] == 0
    assert set(result["physical_clauses"].values()) == {"NOT_EVALUATED"}
    for observable in runner.REQUIRED_FIELDS:
        assert result["field_state_counts"][observable] == {"PRESENT": 834}
    for satellite in SATELLITES:
        assert result["segments"][satellite] == {
            "maximal_segment": {
                "first_index": 0,
                "last_index": 138,
                "epoch_count": 139,
            },
            "full_window": True,
        }


def test_blank_field_rejects_after_complete_window_scan() -> None:
    result = runner.scan_decoded(fixture(blank=(17, "G20", "C2W")))

    assert result["state"] == "DRAO_STRUCTURE_TOPOLOGY_REJECTED"
    assert result["field_state_counts"]["C2W"] == {"BLANK": 1, "PRESENT": 833}
    assert result["field_state_counts"]["L2W"] == {"PRESENT": 834}
    assert "FIELD_NOT_PRESENT:C2W:1" in result["typed_refusal_reasons"]
    segment = result["segments"]["G20"]["maximal_segment"]
    assert segment["epoch_count"] == 121
    assert segment["first_index"] == 18
    assert segment["last_index"] == 138


def test_nonzero_lli_breaks_only_the_affected_structural_segment() -> None:
    result = runner.scan_decoded(
        fixture(nonzero_lli=(70, "G15", "L1C"))
    )

    assert result["state"] == "DRAO_STRUCTURE_TOPOLOGY_REJECTED"
    assert result["lli_state_counts"]["L1C"] == {
        "NONZERO": 1,
        "ZERO_OR_BLANK": 833,
    }
    assert "LLI_NOT_ZERO_OR_BLANK:L1C:1" in result["typed_refusal_reasons"]
    assert result["segments"]["G15"]["maximal_segment"] == {
        "first_index": 0,
        "last_index": 69,
        "epoch_count": 70,
    }
    assert result["segments"]["G14"]["full_window"] is True


def test_strict_json_rejects_nonfinite() -> None:
    try:
        runner.strict_json({"bad": float("nan")})
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("non-finite JSON was accepted")
