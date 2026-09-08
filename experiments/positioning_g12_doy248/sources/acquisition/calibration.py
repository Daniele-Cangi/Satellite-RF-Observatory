"""Non-target GPS clock calibration for a single frozen inverse event."""
from __future__ import annotations

from datetime import datetime, timezone
from math import atan2, cos, sin, sqrt

import numpy as np
from scipy.optimize import least_squares

# Pure numeric record parsing; no dependency on historical executors.
from .navigation import parse_gps_record
from .context import Context

C = 299792458.0
OMEGA = 7.2921151467e-5
MU = 3.986005e14
ALPHA = 1575.42**2 / (1575.42**2 - 1227.60**2)
BETA = 1.0 - ALPHA


def strip_target_navigation(content: str, target: str) -> str:
    """Ignore target blocks as text; no target numbers are parsed or returned."""
    lines = content.splitlines()
    start = next(i for i, row in enumerate(lines) if row[60:80].strip() == "END OF HEADER") + 1
    kept = [f"{'     3.04           NAVIGATION DATA     G':60}RINEX VERSION / TYPE", f"{'':60}END OF HEADER"]
    i = start
    while i < len(lines):
        row = lines[i]
        if row.startswith("G"):
            block = lines[i:i + 8]
            if len(block) != 8 or any(not r.startswith("    ") for r in block[1:]):
                raise ValueError("invalid GPS navigation block")
            if row[:3] != target:
                kept.extend(block)
            i += 8
        else:
            i += 1
    return "\n".join(kept) + "\n"


def parse_reference_navigation(content: str, target: str) -> dict:
    lines = content.splitlines()
    records = {}
    for i, row in enumerate(lines):
        if row.startswith(target):
            raise ValueError("target navigation is forbidden")
        if row.startswith("G"):
            record = parse_gps_record(lines[i:i + 8])
            if record.sv_health == 0 and 0 <= record.eccentricity < 1:
                records.setdefault(record.satellite, []).append(record)
    if not records:
        raise ValueError("no non-target navigation records")
    return records


def rotate_z(x, angle):
    x = np.asarray(x)
    ca, sa = np.cos(angle), np.sin(angle)
    return np.array([ca * x[0] - sa * x[1], sa * x[0] + ca * x[1], x[2]])


def state_and_clock(record, t, context: Context):
    if record.satellite == context.target:
        raise ValueError("target propagation is forbidden")
    # t is local seconds relative to the declared GPST calendar day.
    elapsed = (context.gps_week - record.gps_week) * 604800 + context.sow_midnight + t - record.toe_sow
    tk = ((elapsed + 302400) % 604800) - 302400
    a = record.sqrt_a_m_sqrt**2
    mean = record.m0_rad + (sqrt(MU / a**3) + record.delta_n_rad_s) * tk
    eccentric = mean
    for _ in range(15):
        update = eccentric - (eccentric - record.eccentricity * sin(eccentric) - mean) / (1 - record.eccentricity * cos(eccentric))
        if abs(update - eccentric) < 1e-14:
            eccentric = update
            break
        eccentric = update
    phi = atan2(sqrt(1 - record.eccentricity**2) * sin(eccentric), cos(eccentric) - record.eccentricity) + record.argument_perigee_rad
    s2, c2 = sin(2 * phi), cos(2 * phi)
    u = phi + record.cus_rad * s2 + record.cuc_rad * c2
    radius = a * (1 - record.eccentricity * cos(eccentric)) + record.crs_m * s2 + record.crc_m * c2
    inc = record.i0_rad + record.idot_rad_s * tk + record.cis_rad * s2 + record.cic_rad * c2
    node = record.omega0_rad + (record.omega_dot_rad_s - OMEGA) * tk - OMEGA * record.toe_sow
    ox, oy = radius * cos(u), radius * sin(u)
    x = np.array([ox * cos(node) - oy * cos(inc) * sin(node), ox * sin(node) + oy * cos(inc) * cos(node), oy * sin(inc)])
    dt = t - (record.toc_gps - context.day).total_seconds()
    clock = record.af0_s + record.af1_s_s * dt + record.af2_s_s2 * dt**2 - 4.442807633e-10 * record.eccentricity * record.sqrt_a_m_sqrt * sin(eccentric)
    return x, clock


def geodetic(x):
    x = np.asarray(x)
    lon = atan2(x[1], x[0])
    p = np.hypot(x[0], x[1])
    e2 = (1 / 298.257223563) * (2 - 1 / 298.257223563)
    lat = atan2(x[2], p * (1 - e2))
    for _ in range(10):
        n = 6378137.0 / sqrt(1 - e2 * sin(lat)**2)
        h = p / cos(lat) - n
        lat = atan2(x[2], p * (1 - e2 * n / (n + h)))
    up = np.array([cos(lat) * cos(lon), cos(lat) * sin(lon), sin(lat)])
    return lat, lon, h, up


def antenna_position(header):
    x = np.array([float(v) for v in header["APPROX POSITION XYZ"][0].split()])
    lat, lon, _, up = geodetic(x)
    dh, de, dn = map(float, header["ANTENNA: DELTA H/E/N"][0].split())
    east = np.array([-sin(lon), cos(lon), 0.0])
    north = np.array([-sin(lat) * cos(lon), -sin(lat) * sin(lon), cos(lat)])
    return x + dh * up + de * east + dn * north


def troposphere(station, satellite):
    _, _, height, up = geodetic(station)
    direction = satellite - station
    sine = np.dot(direction, up) / np.linalg.norm(direction)
    mapping = 1.001 / sqrt(0.002001 + sine**2)
    delay = (2.3 * np.exp(-0.000116 * height) + 0.1) * mapping
    return delay, np.degrees(np.arcsin(np.clip(sine, -1, 1)))


def observation_window(content: str, header, gps_types, include_target: bool, context: Context):
    for label in ("SYS / SCALE FACTOR", "SYS / DCBS APPLIED", "SYS / PCVS APPLIED"):
        if label in header:
            raise ValueError("unqualified applied correction: " + label)
    if int(header.get("RCV CLOCK OFFS APPL", ["0"])[0]) != 0:
        raise ValueError("receiver-applied clock correction not qualified")
    if header["TIME OF FIRST OBS"][0][48:51] != "GPS":
        raise ValueError("expected GPS time scale")
    indices = [gps_types.index(c) for c in ("C1C", "C2W")]
    lines = iter(content.splitlines())
    for row in lines:
        if row[60:80].strip() == "END OF HEADER":
            break
    observations = []
    for row in lines:
        if not row.startswith(">"):
            continue
        fields = row[1:].split()
        t = int(fields[3]) * 3600 + int(fields[4]) * 60 + float(fields[5])
        flag, n = int(fields[6]), int(fields[7])
        if t > context.times[-1]:
            break
        block = [next(lines) for _ in range(n)]
        if flag != 0 or t < context.start_s:
            continue
        values = {}
        for record in block:
            sv = record[:3]
            if not sv.startswith("G") or (sv == context.target and not include_target):
                continue
            # Exclude target before converting any of its measurement fields.
            codes = [record[3 + 16 * i:3 + 16 * i + 14].strip() for i in indices]
            if all(codes):
                p1, p2 = map(float, codes)
                if not np.isfinite([p1, p2]).all():
                    raise ValueError("nonfinite code")
                values[sv] = ALPHA * p1 + BETA * p2
        observations.append({"time_s": t, "if_code_m": values})
    if [o["time_s"] for o in observations] != list(context.times):
        raise ValueError("window differs from frozen selection")
    return observations


def reference_model(record, p, t_tag, station, receiver_clock_m, context: Context):
    emitted = t_tag - p / C
    t_tx = emitted
    for _ in range(4):
        _, clock = state_and_clock(record, t_tx, context)
        t_tx = emitted - clock
    sat, clock = state_and_clock(record, t_tx, context)
    t_rx = t_tag - receiver_clock_m / C
    rotated = rotate_z(sat, -OMEGA * (t_rx - t_tx))
    trop, elevation = troposphere(station, rotated)
    model = np.linalg.norm(rotated - station) - C * clock + trop
    return model, elevation


def calibrate_station(observations, station, navigation, context: Context):
    epochs = []
    failures = []
    for obs in observations:
        t = obs["time_s"]
        records = {}
        for sv, p in obs["if_code_m"].items():
            if sv == context.target:
                raise ValueError("target observation passed to calibration")
            candidates = navigation.get(sv, [])
            if not candidates:
                continue
            record = min(candidates, key=lambda r: abs(t - (r.toc_gps - context.day).total_seconds()))
            if abs(t - (record.toc_gps - context.day).total_seconds()) <= 7200:
                _, elev = reference_model(record, p, t, station, 0.0, context)
                if elev >= 10:
                    records[sv] = record
        svs = sorted(records)
        if len(svs) < 4:
            failures.append(f"epoch {t}: fewer than four references above 10 degrees")
            continue
        clock = 0.0
        for _ in range(4):
            estimates = np.array([obs["if_code_m"][sv] - reference_model(records[sv], obs["if_code_m"][sv], t, station, clock, context)[0] for sv in svs])
            clock = float(estimates.mean())
        residuals = estimates - clock
        rms = float(np.sqrt(np.mean(residuals**2)))
        split = float(abs(estimates[::2].mean() - estimates[1::2].mean()))
        if np.max(np.abs(residuals)) > 50 or rms > 20 or split > 30:
            failures.append(f"epoch {t}: reference residual or subset clock threshold")
        # An independent non-target SPP check of the fixed terrestrial coordinate.
        def residual(v):
            return np.array([reference_model(records[sv], obs["if_code_m"][sv], t, station + v[:3], v[3], context)[0] + v[3] - obs["if_code_m"][sv] for sv in svs])
        def jac(v):
            return np.column_stack([(residual(v + np.eye(4)[j]) - residual(v - np.eye(4)[j])) / 2 for j in range(4)])
        spp = least_squares(residual, np.array([0., 0., 0., clock]), jac=jac, xtol=1e-11, ftol=1e-11, gtol=1e-8)
        rank = np.linalg.matrix_rank(spp.jac)
        offset = float(np.linalg.norm(spp.x[:3]))
        if not spp.success or rank != 4 or offset > 30:
            failures.append(f"epoch {t}: non-target ground-coordinate check")
        epochs.append({"time_s": t, "clock_m": clock, "references": svs, "residuals_m": residuals.tolist(), "rms_m": rms, "split_clock_m": split, "ground_offset_m": offset, "ground_offset_xyz_m": spp.x[:3].tolist(), "ground_fit_rank": int(rank)})
    return {"epochs": epochs, "failures": failures, "status": "CALIBRATION_QUALIFIED" if not failures and len(epochs) == context.samples else "CALIBRATION_NOT_QUALIFIED"}
