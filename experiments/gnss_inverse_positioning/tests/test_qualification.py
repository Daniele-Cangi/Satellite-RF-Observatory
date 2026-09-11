import pytest
from experiments.gnss_inverse_positioning.qualification import QualificationError, scan_structure, select_window


def rinex(target_value="12345678.125", missing=False):
    header = [
        f"{'     3.04           OBSERVATION DATA    M':60}RINEX VERSION / TYPE",
        f"{'G    6 L1C L2W S1C S2W C1C C2W':60}SYS / # / OBS TYPES",
        f"{'':60}END OF HEADER",
    ]
    rows = ["> 2026 09 06 00 00  0.0000000  0  5"]
    for sv in ("G01", "G02", "G03", "G04", "G08"):
        value = target_value if sv == "G08" else "20000000.125"
        # Code fields beyond column 80; omit trailing code in one case.
        row = sv + " " * 64 + f"{value:>14}  "
        if not (missing and sv == "G08"):
            row += f"{value:>14}  "
        rows.append(row)
    return "\n".join(header + rows)


def test_numeric_target_values_do_not_affect_structural_result():
    first = scan_structure(rinex())
    changed = scan_structure(rinex("99999999.999"))
    assert first == changed
    assert first["epochs"][0]["eligible"]


def test_missing_trailing_code_not_mistaken_for_presence():
    assert not scan_structure(rinex(missing=True))["epochs"][0]["eligible"]


def test_phase_update_at_same_epoch_does_not_remove_code_observation():
    event = "> 2026 09 06 00 00  0.0000000  4  1\n"
    phase = f"{'E L6C  0.00000':60}SYS / PHASE SHIFT\n"
    data = rinex().replace("> 2026", event + phase + "> 2026", 1)
    result = scan_structure(data)
    assert result["epoch_count"] == 1
    assert result["eligible_epoch_count"] == 1
    assert len(result["events"]) == 1


def test_clock_header_update_fails_explicitly():
    event = "> 2026 09 06 00 00  0.0000000  4  1\n"
    clock = f"{'     1':60}RCV CLOCK OFFS APPL\n"
    data = rinex().replace("> 2026", event + clock + "> 2026", 1)
    with pytest.raises(QualificationError, match="header update"):
        scan_structure(data)


def test_first_complete_window_and_no_gap_bridging():
    def structure(times):
        return {"epochs": [{"seconds_gpst": str(t), "eligible": True} for t in times]}
    early = list(range(0, 300, 30))  # ten samples are insufficient
    later = list(range(600, 930, 30))
    result = select_window({"a": structure(early + later), "b": structure(early + later)})
    assert result["selected_seconds_gpst"] == [str(t) for t in later]
    assert select_window({"a": structure(early)})["selected_seconds_gpst"] is None
