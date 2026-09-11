"""Audited GPS RINEX record primitives extracted from the historical parser."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Sequence

@dataclass(frozen=True, slots=True)
class GpsEphemeris:
    satellite: str
    toc_gps: datetime
    af0_s: float
    af1_s_s: float
    af2_s_s2: float
    iode: float
    crs_m: float
    delta_n_rad_s: float
    m0_rad: float
    cuc_rad: float
    eccentricity: float
    cus_rad: float
    sqrt_a_m_sqrt: float
    toe_sow: float
    cic_rad: float
    omega0_rad: float
    cis_rad: float
    i0_rad: float
    crc_m: float
    argument_perigee_rad: float
    omega_dot_rad_s: float
    idot_rad_s: float
    gps_week: int
    sv_accuracy_m: float
    sv_health: int
    tgd_s: float
    transmission_sow: float
    fit_interval_h: float | None


def parse_gps_record(lines: Sequence[str]) -> GpsEphemeris:
    if len(lines) != 8 or not lines[0].startswith("G"):
        raise ValueError("not one RINEX-3 GPS record")
    epoch_fields = lines[0][3:23].split()
    if len(epoch_fields) != 6:
        raise ValueError("invalid GPS toc")
    year, month, day, hour, minute = (int(value) for value in epoch_fields[:5])
    second = float(epoch_fields[5])
    toc = datetime(year, month, day, hour, minute, tzinfo=timezone.utc) + timedelta(seconds=second)
    first = fixed_fields(lines[0], 23)
    rows = [fixed_fields(line, 4) for line in lines[1:]]
    return GpsEphemeris(
        lines[0][:3], toc, first[0], first[1], first[2],
        rows[0][0], rows[0][1], rows[0][2], rows[0][3],
        rows[1][0], rows[1][1], rows[1][2], rows[1][3],
        rows[2][0], rows[2][1], rows[2][2], rows[2][3],
        rows[3][0], rows[3][1], rows[3][2], rows[3][3],
        rows[4][0], int(round(rows[4][2])), rows[5][0], int(round(rows[5][1])),
        rows[5][2],
        rows[6][0],
        None if len(rows[6]) < 2 or rows[6][1] == 0.0 else rows[6][1],
    )


def fixed_fields(line: str, start: int) -> tuple[float, ...]:
    fields = []
    for offset in range(start, len(line), 19):
        text = line[offset : offset + 19].strip().replace("D", "E")
        if text:
            fields.append(float(text))
    return tuple(fields)
