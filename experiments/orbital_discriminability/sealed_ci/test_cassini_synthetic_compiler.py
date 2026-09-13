"""Synthetic one-way compiler checks; these do not read or validate real SPK kernels."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass

import pytest

import experiments.orbital_discriminability.cassini_dss26_one_way as one_way
from experiments.orbital_discriminability.cassini_dss26_one_way import (
    SPEED_OF_LIGHT_M_S,
    USOCarrierModel,
    compile_dss26_one_way,
)


@dataclass(frozen=True, slots=True)
class FrozenEpoch:
    receive_utc: str
    receive_et_tdb_s: float
    geometric_light_time_s: float
    kinematic_frequency_factor: float


FROZEN_EPOCHS = (
    FrozenEpoch("2005-06-06T17:50:01Z", 10_000.0, 4_907.510879427195, 0.9999299036421737),
    FrozenEpoch("2005-06-06T19:10:26Z", 30_000.0, 4_907.850356847048, 0.9999293648478778),
    FrozenEpoch("2005-06-06T20:30:51Z", 50_000.0, 4_908.192765682936, 0.9999286935663851),
)

EXPECTED_KERNELS = (
    ("naif0012.tls", 5_257, "678e32bdb5a744117a467cd9601cd6b373f0e9bc9bbde1371d5eee39600a039b"),
    (
        "earth_720101_070426.bpc",
        8_603_648,
        "1fa3670679bcd3d1978bea7653a34e68d1518f832124412c766faf454d77205e",
    ),
    (
        "earthstns_itrf93_050714.bsp",
        38_912,
        "371fb58d19dd757de7b31cac80b5e61d5eaa26dc3437a009eece1c47792cee5c",
    ),
    (
        "050426AP_SCPSE_05116_05216.bsp",
        3_832_832,
        "065258e6982b10488604d97f02f9b5110d6b1e4760ff340211b50973ab8228f5",
    ),
)


class FrozenCassiniSpice:
    def __init__(self) -> None:
        self._receive_lookup = {epoch.receive_utc: epoch for epoch in FROZEN_EPOCHS}

    def furnsh(self, path: str) -> None:  # pragma: no cover - sealed CI bypasses CSPICE I/O
        return None

    def kclear(self) -> None:  # pragma: no cover - sealed CI bypasses CSPICE I/O
        return None

    def utc2et(self, utc: str) -> float:
        return self._receive_lookup[utc].receive_et_tdb_s

    def et2utc(self, et: float, format: str, precision: int) -> str:
        assert (format, precision) == ("ISOC", 6)
        return f"ET{et:.6f}"

    def spkezr(
        self,
        target: str,
        et: float,
        frame: str,
        aberration_correction: str,
        observer: str,
    ) -> tuple[tuple[float, float, float, float, float, float], float]:
        assert (frame, aberration_correction, observer) == (
            one_way.INERTIAL_FRAME,
            "NONE",
            one_way.STATE_OBSERVER,
        )
        if target == one_way.DEVELOPMENT_STATION:
            return ((0.0, 0.0, 0.0, 0.0, 0.0, 0.0), 0.0)
        if target != one_way.SPACECRAFT:
            raise AssertionError(target)
        epoch = self._epoch_for_et(et)
        beta = self._beta(epoch.kinematic_frequency_factor)
        velocity_m_s = beta * SPEED_OF_LIGHT_M_S
        transmit_et = epoch.receive_et_tdb_s - epoch.geometric_light_time_s
        position_m = (
            SPEED_OF_LIGHT_M_S * epoch.geometric_light_time_s
            + velocity_m_s * (et - transmit_et)
        )
        return (
            (
                position_m / 1_000.0,
                0.0,
                0.0,
                velocity_m_s / 1_000.0,
                0.0,
                0.0,
            ),
            0.0,
        )

    def _epoch_for_et(self, et: float) -> FrozenEpoch:
        if et < 20_000.0:
            return FROZEN_EPOCHS[0]
        if et < 40_000.0:
            return FROZEN_EPOCHS[1]
        return FROZEN_EPOCHS[2]

    @staticmethod
    def _beta(frequency_factor: float) -> float:
        factor_squared = frequency_factor * frequency_factor
        return (1.0 - factor_squared) / (1.0 + factor_squared)


@contextmanager
def _sealed_kernel_lineage():
    yield tuple(
        {
            "name": spec.name,
            "bytes": spec.bytes,
            "sha256": spec.sha256,
            "role": spec.role,
            "independence": spec.independence,
        }
        for spec in one_way.CASSINI_DSS26_KERNELS
    )


def test_synthetic_three_epoch_compiler_consistency(monkeypatch) -> None:
    monkeypatch.setattr(one_way, "_loaded_frozen_kernels", lambda _spice, _paths: _sealed_kernel_lineage())
    carrier = USOCarrierModel(
        nominal_rest_frequency_hz=1.0,
        calibration_reference_utc="2005-06-06T17:50:01Z",
        constant_offset_hz=0.0,
        aging_rate_hz_s=0.0,
    )
    kernel_paths = {spec.name: object() for spec in one_way.CASSINI_DSS26_KERNELS}
    frozen_spice = FrozenCassiniSpice()
    for epoch in FROZEN_EPOCHS:
        prediction = compile_dss26_one_way(
            epoch.receive_utc,
            carrier,
            kernel_paths,
            spice=frozen_spice,
        )
        assert prediction.geometric_light_time_s == pytest.approx(
            epoch.geometric_light_time_s,
            abs=1e-6,
        )
        assert prediction.kinematic_frequency_factor == pytest.approx(
            epoch.kinematic_frequency_factor,
            abs=1e-13,
        )
        assert tuple(prediction.kernel_lineage) == tuple(
            {
                "name": spec.name,
                "bytes": spec.bytes,
                "sha256": spec.sha256,
                "role": spec.role,
                "independence": spec.independence,
            }
            for spec in one_way.CASSINI_DSS26_KERNELS
        )
        assert not prediction.primary_prediction_authorized


def test_frozen_kernel_contract_remains_the_exact_public_set() -> None:
    assert tuple((spec.name, spec.bytes, spec.sha256) for spec in one_way.CASSINI_DSS26_KERNELS) == (
        EXPECTED_KERNELS
    )
    manifest = one_way.compiler_manifest()
    assert tuple(
        (item["name"], item["bytes"], item["sha256"])
        for item in manifest["kernels"]
    ) == EXPECTED_KERNELS
    assert [asdict(spec) for spec in one_way.CASSINI_DSS26_KERNELS] == manifest["kernels"]
