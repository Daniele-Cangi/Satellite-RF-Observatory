"""Bounded, value-blind qualification of the frozen G08 inverse experiment.

No orbit inputs or numerical pseudorange parsing. RINEX 3 observation records
are not limited to 80 columns; missing trailing observation fields are blank.
"""
from __future__ import annotations

from decimal import Decimal


class QualificationError(ValueError):
    pass


def scan_structure(content: str, target: str = "G08") -> dict:
    lines = iter(content.splitlines())
    types: dict[str, list[str]] = {}
    counts: dict[str, int] = {}
    headers: dict[str, list[str]] = {}
    system = ""
    for line in lines:
        label = line[60:80].strip()
        headers.setdefault(label, []).append(line[:60].rstrip())
        if label == "SYS / # / OBS TYPES":
            if line[0:1].strip():
                system = line[0]
                if system in counts:
                    raise QualificationError("duplicate observation type declaration")
                counts[system] = int(line[3:6])
                types[system] = []
            if not system:
                raise QualificationError("orphan observation type continuation")
            types[system].extend(line[7:60].split())
        if label == "END OF HEADER":
            break
    else:
        raise QualificationError("incomplete RINEX header")
    version = float(headers["RINEX VERSION / TYPE"][0][:9])
    if not 3 <= version < 4:
        raise QualificationError("expected RINEX 3")
    for system, count in counts.items():
        if len(types[system]) != count:
            raise QualificationError("incomplete observation types")
    gps_types = types.get("G", [])
    if not {"C1C", "C2W"}.issubset(gps_types):
        raise QualificationError("missing GPS C1C/C2W declarations")
    indices = [gps_types.index(code) for code in ("C1C", "C2W")]
    epochs = []
    events = []
    previous = None
    for line in lines:
        if not line.strip():
            continue
        if not line.startswith(">"):
            raise QualificationError("expected RINEX epoch")
        fields = line[1:].split()
        if len(fields) not in (8, 9):
            raise QualificationError("invalid epoch header")
        year, month, day, hour, minute = map(int, fields[:5])
        if (year, month, day) != (2026, 9, 6):
            raise QualificationError("epoch outside frozen date")
        second = Decimal(fields[5])
        time_s = Decimal(hour * 3600 + minute * 60) + second
        flag, record_count = map(int, fields[6:8])
        if flag == 4:
            updates = [next(lines, "") for _ in range(record_count)]
            # Phase-only updates do not change pseudorange or epoch tags.
            # Never silently ignore clock, coordinates, or code-type changes.
            if not all(row[60:80].strip() in ("SYS / PHASE SHIFT", "COMMENT") for row in updates):
                raise QualificationError("unhandled header update affecting code qualification")
            events.append({"seconds_gpst": str(time_s), "flag": flag, "records": updates})
            continue
        if previous is not None and time_s <= previous:
            raise QualificationError("non-increasing epoch time")
        previous = time_s
        if flag not in (0, 1):
            raise QualificationError("special event requires explicit interpretation")
        present = []
        seen = set()
        for _ in range(record_count):
            record = next(lines, None)
            if record is None or len(record) < 3 or not record[0].isalpha() or not record[1:3].isdigit():
                raise QualificationError("truncated or invalid satellite record")
            satellite = record[:3]
            if satellite in seen:
                raise QualificationError("duplicate satellite in epoch")
            seen.add(satellite)
            if satellite[0] != "G":
                continue
            # Deliberately no float conversion or range-quality filtering.
            if all(record[3 + 16 * i: 3 + 16 * i + 14].strip() for i in indices):
                present.append(satellite)
        target_present = target in present
        reference_count = sum(sv != target for sv in present)
        epochs.append({
            "seconds_gpst": str(time_s), "flag": flag,
            "receiver_clock_field_present": len(fields) == 9,
            "target_codes_present": target_present,
            "reference_code_count": reference_count,
            "eligible": flag == 0 and target_present and reference_count >= 4,
        })
    return {
        "header": headers, "gps_observation_types": gps_types,
        "epochs": epochs, "events": events,
        "epoch_count": len(epochs),
        "target_code_epoch_count": sum(e["target_codes_present"] for e in epochs),
        "eligible_epoch_count": sum(e["eligible"] for e in epochs),
    }


def select_window(structures: dict[str, dict], samples: int = 11, step: int = 30) -> dict:
    if not structures or samples < 1:
        raise QualificationError("empty selection")
    sets = [
        {Decimal(e["seconds_gpst"]) for e in s["epochs"] if e["eligible"]}
        for s in structures.values()
    ]
    common = set.intersection(*sets)
    selected = None
    for start in sorted(common):
        candidate = [start + i * step for i in range(samples)]
        if all(time in common for time in candidate):
            selected = [str(time) for time in candidate]
            break
    return {
        "common_eligible_epoch_count": len(common),
        "common_eligible_seconds_gpst": [str(t) for t in sorted(common)],
        "selected_seconds_gpst": selected,
        "status": "STRUCTURAL_WINDOW_PRESENT" if selected else "NO_COMMON_STRUCTURAL_WINDOW",
    }
