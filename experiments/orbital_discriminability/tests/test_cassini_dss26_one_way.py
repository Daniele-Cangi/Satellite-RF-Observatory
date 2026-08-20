"""Offline tests for the Cassini/DSS-26 one-way SpiceyPy compiler."""

from dataclasses import replace
from hashlib import sha256
from math import ulp
from pathlib import Path

import pytest

import experiments.orbital_discriminability.cassini_dss26_one_way as one_way
from experiments.orbital_discriminability.cassini_dss26_one_way import (
    CassiniPredictionError,
    FrequencyCorrectionTerm,
    KernelSpec,
    SPEED_OF_LIGHT_M_S,
    StateVector,
    USOCarrierModel,
    compile_dss26_one_way,
    compiler_manifest,
    compiler_manifest_sha256,
    initial_open_terms,
    solve_one_way_event,
)


RECEIVE_UTC = "2005-06-06T17:50:01Z"
REFERENCE_UTC = "2005-06-06T17:49:41Z"


class FakeSpice:
    def __init__(self, spacecraft_velocity_km_s: float = 0.0) -> None:
        self.spacecraft_velocity_km_s = spacecraft_velocity_km_s
        self.loaded: list[str] = []
        self.state_calls: list[tuple[str, float, str, str, str]] = []
        self.clear_count = 0

    def furnsh(self, path: str) -> None:
        self.loaded.append(path)

    def kclear(self) -> None:
        self.clear_count += 1

    def utc2et(self, utc: str) -> float:
        return {RECEIVE_UTC: 20.0, REFERENCE_UTC: 0.0}[utc]

    def et2utc(self, et: float, format: str, precision: int) -> str:
        assert (format, precision) == ("ISOC", 6)
        return f"ET{et:.6f}"

    def spkezr(self, target, et, frame, aberration_correction, observer):
        self.state_calls.append((target, et, frame, aberration_correction, observer))
        if target == "DSS-26":
            return ([0.0, 0.0, 0.0, 0.0, 0.0, 0.0], 0.0)
        if target == "CASSINI":
            distance_km = 10.0 * SPEED_OF_LIGHT_M_S / 1_000.0
            return (
                [
                    distance_km + self.spacecraft_velocity_km_s * et,
                    0.0,
                    0.0,
                    self.spacecraft_velocity_km_s,
                    0.0,
                    0.0,
                ],
                0.0,
            )
        raise AssertionError(target)


def _synthetic_kernel_set(tmp_path: Path, monkeypatch) -> dict[str, Path]:
    specs = []
    paths = {}
    for index, role in enumerate(
        (
            "UTC_TO_ET_TDB",
            "HISTORICAL_EARTH_ORIENTATION",
            "DSS26_STATION_STATE",
            "CASSINI_TRAJECTORY",
        )
    ):
        name = f"synthetic-{index}.kernel"
        body = f"specification-only-{role}".encode("ascii")
        path = tmp_path / name
        path.write_bytes(body)
        specs.append(
            KernelSpec(
                name=name,
                bytes=len(body),
                sha256=sha256(body).hexdigest(),
                role=role,
                independence=(
                    "PREDICT_CREATED_BEFORE_DEVELOPMENT_PASS"
                    if role == "CASSINI_TRAJECTORY"
                    else "SYNTHETIC_TEST_CONTROL"
                ),
            )
        )
        paths[name] = path
    monkeypatch.setattr(one_way, "CASSINI_DSS26_KERNELS", tuple(specs))
    return paths


def _carrier(*, resolved: bool) -> USOCarrierModel:
    return USOCarrierModel(
        nominal_rest_frequency_hz=8_425_000_000.0,
        calibration_reference_utc=REFERENCE_UTC,
        constant_offset_hz=2.0 if resolved else None,
        aging_rate_hz_s=0.1 if resolved else None,
    )


def test_stationary_light_time_and_open_term_claim_scope(tmp_path, monkeypatch) -> None:
    paths = _synthetic_kernel_set(tmp_path, monkeypatch)
    spice = FakeSpice()
    prediction = compile_dss26_one_way(
        RECEIVE_UTC,
        _carrier(resolved=True),
        paths,
        spice=spice,
    )
    assert prediction.geometric_light_time_s == pytest.approx(10.0, abs=1e-12)
    assert prediction.transmit_et_tdb_s == pytest.approx(10.0, abs=1e-12)
    assert prediction.emitted_frequency_hz == pytest.approx(8_425_000_003.0)
    assert prediction.kinematic_frequency_factor == pytest.approx(1.0, abs=1e-15)
    # The offset and aging are already applied in the emitted rest-frame carrier.
    assert prediction.declared_correction_hz == 0.0
    assert prediction.received_sky_frequency_hz == pytest.approx(8_425_000_003.0)
    assert prediction.steering_only_received_sky_frequency_hz == pytest.approx(
        prediction.emitted_frequency_hz
    )
    assert prediction.orbital_minus_steering_only_hz == pytest.approx(0.0)
    assert not prediction.primary_prediction_authorized
    assert "OPEN_TERMS=" in prediction.claim_scope
    assert spice.clear_count == 2
    assert len(spice.loaded) == 4
    assert all(call[2:] == ("J2000", "NONE", "SOLAR SYSTEM BARYCENTER") for call in spice.state_calls)


def test_receding_spacecraft_redshifts_the_one_way_carrier() -> None:
    station = lambda _time: StateVector((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))

    def spacecraft(time):
        return StateVector(
            (10.0 * SPEED_OF_LIGHT_M_S + 1_000.0 * time, 0.0, 0.0),
            (1_000.0, 0.0, 0.0),
        )

    event = solve_one_way_event(20.0, station, spacecraft)
    assert event.transmit_et_tdb_s < 10.0
    assert event.kinematic_frequency_factor < 1.0


def test_light_time_convergence_is_not_limited_by_absolute_et_ulp() -> None:
    receive_et = 100_000_000.0
    base_light_time_s = 10.123456789
    radial_beta = 0.05
    station = lambda _time: StateVector((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))

    def spacecraft(epoch_et: float) -> StateVector:
        relative_s = epoch_et - receive_et
        return StateVector(
            (
                SPEED_OF_LIGHT_M_S * (base_light_time_s + radial_beta * relative_s),
                0.0,
                0.0,
            ),
            (SPEED_OF_LIGHT_M_S * radial_beta, 0.0, 0.0),
        )

    event = solve_one_way_event(receive_et, station, spacecraft, tolerance_s=1e-9)
    analytic_light_time = base_light_time_s / (1.0 + radial_beta)
    # An absolute-ET subtraction at this epoch is quantized at about 15 ns.
    assert ulp(receive_et) > 1e-9
    assert event.geometric_light_time_s == pytest.approx(analytic_light_time, abs=1e-9)


def test_all_bounded_terms_can_authorize_only_a_declared_envelope(tmp_path, monkeypatch) -> None:
    paths = _synthetic_kernel_set(tmp_path, monkeypatch)
    terms = tuple(
        replace(term, status="BOUNDED", central_correction_hz=0.0, absolute_bound_hz=1.0)
        for term in initial_open_terms()
    )
    prediction = compile_dss26_one_way(
        RECEIVE_UTC,
        _carrier(resolved=True),
        paths,
        correction_terms=terms,
        spice=FakeSpice(),
    )
    assert prediction.sky_prediction_terms_closed
    assert not prediction.primary_prediction_authorized
    assert prediction.declared_correction_bound_hz == 7.0
    assert prediction.claim_scope == (
        "ONE_WAY_SKY_FREQUENCY_WITH_DECLARED_ENVELOPE_"
        "AWAITING_CONCRETE_RSR_TRANSFORM"
    )


def test_missing_term_and_invented_open_term_number_are_refused(tmp_path, monkeypatch) -> None:
    paths = _synthetic_kernel_set(tmp_path, monkeypatch)
    with pytest.raises(CassiniPredictionError, match="omits or adds"):
        compile_dss26_one_way(
            RECEIVE_UTC,
            _carrier(resolved=False),
            paths,
            correction_terms=initial_open_terms()[:-1],
            spice=FakeSpice(),
        )
    bad = replace(initial_open_terms()[0], central_correction_hz=0.0)
    with pytest.raises(CassiniPredictionError, match="invented number"):
        bad.validate()


def test_kernel_hash_failure_occurs_before_cspice_load(tmp_path, monkeypatch) -> None:
    paths = _synthetic_kernel_set(tmp_path, monkeypatch)
    first = next(iter(paths.values()))
    first.write_bytes(first.read_bytes() + b"changed")
    spice = FakeSpice()
    with pytest.raises(CassiniPredictionError, match="identity failed|SHA-256 failed"):
        compile_dss26_one_way(RECEIVE_UTC, _carrier(resolved=False), paths, spice=spice)
    assert not spice.loaded


def test_runtime_has_no_ephemeris_fallback(monkeypatch) -> None:
    def missing(_name):
        raise ModuleNotFoundError("spiceypy")

    monkeypatch.setattr(one_way.importlib, "import_module", missing)
    with pytest.raises(CassiniPredictionError, match="no Horizons or Skyfield fallback"):
        one_way._import_spiceypy()


def test_manifest_freezes_predict_spk_and_forbids_outcome_conditioned_inputs() -> None:
    manifest = compiler_manifest()
    spacecraft = next(item for item in manifest["kernels"] if item["role"] == "CASSINI_TRAJECTORY")
    assert spacecraft["name"] == "050426AP_SCPSE_05116_05216.bsp"
    assert "PREDICT" in spacecraft["independence"]
    forbidden = " ".join(manifest["forbidden_inputs"]).lower()
    assert "reconstructed" in forbidden
    assert "horizons" in forbidden
    assert len(compiler_manifest_sha256()) == 64
