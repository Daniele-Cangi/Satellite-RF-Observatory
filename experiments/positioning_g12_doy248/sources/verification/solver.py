"""Multi-receiver emitted-event multilateration: no target-state input surface."""
from __future__ import annotations

from itertools import combinations, product
import numpy as np
from scipy.optimize import least_squares, brentq

from .calibration import C, OMEGA, rotate_z, troposphere

CHI95 = 7.814727903251179


def interpolate_event(codes, clocks, stations, u0=None, degree=3, time_offsets=None, times_s=None):
    codes, clocks, stations = map(np.asarray, (codes, clocks, stations))
    times = np.asarray(times_s if times_s is not None else np.arange(-150., 151., 30.), dtype=float)
    if codes.ndim != 2 or codes.shape != clocks.shape or codes.shape[1] != len(times) or len(times) % 2 != 1:
        raise ValueError("inconsistent code, clock and time arrays")
    if not np.isfinite(codes).all() or not np.isfinite(clocks).all() or not np.isfinite(times).all():
        raise ValueError("nonfinite event input")
    tagged_times = np.broadcast_to(times, codes.shape)
    if time_offsets is not None:
        tagged_times = tagged_times + np.asarray(time_offsets)
    tags = tagged_times - codes / C
    if u0 is None:
        u0 = float(np.median(tags[:, len(times)//2]))
    z, weights, positions = [], [], []
    for i, row in enumerate(tags):
        if np.any(np.diff(row) <= 0) or not row[0] <= u0 <= row[-1]:
            raise ValueError("emission tags do not bracket event monotonically")
        selected = np.sort(np.argsort(abs(row - u0), kind="stable")[:degree + 1])
        nodes = row[selected]
        if not nodes[0] <= u0 <= nodes[-1]:
            raise ValueError("interpolation stencil does not bracket event")
        w = np.ones(len(nodes))
        for j in range(len(nodes)):
            for k in range(len(nodes)):
                if j != k:
                    w[j] *= (u0 - nodes[k]) / (nodes[j] - nodes[k])
        full = np.zeros(len(times))
        full[selected] = w
        zi = float(full @ (codes[i] - clocks[i]))
        z.append(zi)
        weights.append(full)
        positions.append(rotate_z(stations[i], OMEGA * zi / C))
    return {"u0": u0, "z": np.array(z), "weights": np.array(weights), "positions": np.array(positions)}


def measurement_model(q, stations, atmosphere=True):
    q, stations = np.asarray(q), np.asarray(stations)
    ranges = np.linalg.norm(q[:3] - stations, axis=1)
    if atmosphere:
        delays = np.array([troposphere(s, q[:3])[0] for s in stations])
    else:
        delays = np.zeros(len(stations))
    return ranges + q[3] + delays


def model_jacobian(q, stations, atmosphere=True):
    delta = q[:3] - stations
    jac = np.column_stack((delta / np.linalg.norm(delta, axis=1)[:, None], np.ones(len(stations))))
    if atmosphere:
        for k in range(3):
            dq = np.zeros(4)
            dq[k] = 1.0
            plus = np.array([troposphere(s, q[:3] + dq[:3])[0] for s in stations])
            minus = np.array([troposphere(s, q[:3] - dq[:3])[0] for s in stations])
            jac[:, k] += (plus - minus) / 2
    return jac


def algebraic_seeds(z, stations):
    scale = 1e7
    y, s = np.asarray(z) / scale, np.asarray(stations) / scale
    def matrix(indices):
        yy, ss = y[indices], s[indices]
        a = np.column_stack((2 * (ss[1:] - ss[0]), -2 * (yy[1:] - yy[0])))
        rhs = (ss[1:]**2).sum(axis=1) - (ss[0]**2).sum() - (yy[1:]**2 - yy[0]**2)
        return a, rhs, yy, ss
    a, rhs, _, _ = matrix(list(range(len(y))))
    if np.linalg.matrix_rank(a) != 4:
        raise ValueError("multi-root algebraic matrix is rank deficient")
    seeds = [np.linalg.lstsq(a, rhs, rcond=None)[0] * scale]
    for indices in combinations(range(len(y)), 4):
        a, rhs, yy, ss = matrix(list(indices))
        if np.linalg.matrix_rank(a) != 3:
            continue
        q = np.linalg.lstsq(a, rhs, rcond=None)[0]
        _, _, vh = np.linalg.svd(a)
        n = vh[-1]
        dx, b = q[:3] - ss[0], yy[0] - q[3]
        coefficients = [n[3]**2 - n[:3] @ n[:3], -2 * (b * n[3] + dx @ n[:3]), b*b - dx @ dx]
        for root in np.roots(coefficients):
            if abs(root.imag) < 1e-8:
                candidate = q + root.real * n
                if np.all(yy - candidate[3] > 0):
                    seeds.append(candidate * scale)
    return seeds


def refine(z, stations, covariance, seed, atmosphere=True):
    chol = np.linalg.cholesky(covariance)
    def residual(q):
        return np.linalg.solve(chol, measurement_model(q, stations, atmosphere) - z)
    def jac(q):
        return np.linalg.solve(chol, model_jacobian(q, stations, atmosphere))
    fit = least_squares(residual, seed, jac=jac, x_scale=np.full(4, 1e7), max_nfev=300, ftol=1e-12, xtol=1e-12, gtol=1e-10)
    singular = np.linalg.svd(jac(fit.x), compute_uv=False)
    return {"q": fit.x, "cost": float(residual(fit.x) @ residual(fit.x)), "success": bool(fit.success), "singular_values": singular, "residuals": measurement_model(fit.x, stations, atmosphere) - z}


def solve(z, stations, covariance, atmosphere=True):
    fits = []
    for seed in algebraic_seeds(z, stations):
        result = refine(z, stations, covariance, seed, atmosphere)
        if not result["success"] or not np.isfinite(result["q"]).all():
            continue
        q = result["q"]
        if atmosphere and min(troposphere(s, q[:3])[1] for s in stations) < 5:
            continue
        if np.any(z - q[3] <= 0):
            continue
        if all(np.linalg.norm(q - previous["q"]) > 0.1 for previous in fits):
            fits.append(result)
    if not fits:
        raise ValueError("no admissible finite emitted-event solution")
    fits.sort(key=lambda v: v["cost"])
    best = fits[0]
    best["branches"] = [{"q": f["q"].tolist(), "cost": f["cost"]} for f in fits]
    best["ambiguous"] = any(f["cost"] - best["cost"] <= CHI95 for f in fits[1:])
    best["elevations_deg"] = [troposphere(s, best["q"][:3])[1] for s in stations] if atmosphere else []
    h = model_jacobian(best["q"], stations, atmosphere)
    _, sv, vh = np.linalg.svd(np.linalg.solve(np.linalg.cholesky(covariance), h), full_matrices=False)
    if sv[-1] <= sv[0] * 1e-12:
        raise ValueError("position-clock Jacobian rank deficient")
    best["covariance"] = (vh.T / sv**2) @ vh
    return best


def profile_axes(z, stations, covariance, best):
    values, vectors = np.linalg.eigh(best["covariance"][:3, :3])
    chol = np.linalg.cholesky(covariance)
    radii = []
    for k in range(3):
        orth = vectors[:, [j for j in range(3) if j != k]]
        for sign in (-1, 1):
            direction = vectors[:, k] * sign
            def profile(distance):
                def residual(v):
                    q = best["q"].copy()
                    q[:3] += direction * distance + orth @ v[:2]
                    q[3] += v[2]
                    return np.linalg.solve(chol, measurement_model(q, stations) - z)
                def jac(v):
                    return np.column_stack([(residual(v + np.eye(3)[j]) - residual(v - np.eye(3)[j])) / 2 for j in range(3)])
                fit = least_squares(residual, np.zeros(3), jac=jac, x_scale=1000., max_nfev=100, ftol=1e-10, xtol=1e-10)
                return float(fit.fun @ fit.fun - best["cost"] - CHI95)
            upper = float(np.sqrt(CHI95 * values[k]) * 1.5)
            while profile(upper) < 0 and upper < 1e9:
                upper *= 2
            if upper >= 1e9:
                raise ValueError("nonlinear confidence profile not bounded")
            radius = brentq(profile, 0.0, upper, xtol=0.01)
            radii.append({"axis": k, "sign": sign, "radius_m": float(radius)})
    return radii


def uncertainty_box(z, stations, covariance, best, bias_m=20., interior_samples=0, seed=2026250, margin=1.):
    displacements = []
    max_semiaxis = float(np.sqrt(CHI95 * np.linalg.eigvalsh(best["covariance"][:3, :3])[-1]))
    bias_probes = list(product((-1., 1.), repeat=len(z)))
    if interior_samples:
        bias_probes += np.random.default_rng(seed).uniform(-1, 1, (interior_samples, len(z))).tolist()
    for signs in bias_probes:
        shifted = z + bias_m * np.array(signs)
        corner = refine(shifted, stations, covariance, best["q"])
        if not corner["success"]:
            raise ValueError("bias-box sensitivity fit did not converge")
        h = model_jacobian(corner["q"], stations)
        cw = np.linalg.solve(np.linalg.cholesky(covariance), h)
        _, singular, vh = np.linalg.svd(cw, full_matrices=False)
        cov = (vh.T / singular**2) @ vh
        max_semiaxis = max(max_semiaxis, float(np.sqrt(CHI95 * np.linalg.eigvalsh(cov[:3, :3])[-1])))
        displacements.append({"signs": list(signs), "delta_q": (corner["q"] - best["q"]).tolist()})
    profiles = profile_axes(z, stations, covariance, best)
    max_semiaxis = max(max_semiaxis, max(p["radius_m"] for p in profiles))
    bias_radius = max(np.linalg.norm(np.array(c["delta_q"])[:3]) for c in displacements)
    return {"bias_probes": displacements, "interior_samples": interior_samples, "margin": margin, "profile_axes": profiles, "statistical_95_radius_m": max_semiaxis, "bias_displacement_max_m": float(bias_radius), "total_95_outer_radius_m": float(margin * (max_semiaxis + bias_radius))}


def heldout_prediction(q, station, covariance_q):
    z = float(np.linalg.norm(q[:3] - station) + q[3])
    for _ in range(6):
        rotated = rotate_z(station, OMEGA * z / C)
        z = float(measurement_model(q, rotated[None, :])[0])
    h = model_jacobian(q, rotated[None, :])[0]
    variance = float(h @ covariance_q @ h)
    return z, variance


def far_field_cost(z, stations, covariance, q):
    """Cost at infinite range with free common clock: unit plane-wave direction."""
    direction = q[:3] / np.linalg.norm(q[:3])
    az = np.arctan2(direction[1], direction[0])
    el = np.arcsin(direction[2])
    chol = np.linalg.cholesky(covariance)
    def residual(v):
        n = np.array([np.cos(v[1]) * np.cos(v[0]), np.cos(v[1]) * np.sin(v[0]), np.sin(v[1])])
        from .calibration import geodetic
        delays = []
        for s in stations:
            _, _, height, up = geodetic(s)
            delays.append((2.3 * np.exp(-0.000116 * height) + 0.1) * 1.001 / np.sqrt(0.002001 + (up @ n)**2))
        return np.linalg.solve(chol, v[2] - stations @ n + np.array(delays) - z)
    initial_d = float(np.mean(z + stations @ direction))
    fit = least_squares(residual, [az, el, initial_d], x_scale=[1.,1.,1e7], max_nfev=300, ftol=1e-12, xtol=1e-12)
    return float(fit.fun @ fit.fun)
