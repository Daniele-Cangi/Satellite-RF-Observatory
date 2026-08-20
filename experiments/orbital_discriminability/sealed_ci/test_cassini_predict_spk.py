"""Non-optional real type-1 PREDICT-SPK regression for the sealed CI job."""

import os
from pathlib import Path

import pytest

import experiments.orbital_discriminability.cassini_dss26_one_way as one_way
from experiments.orbital_discriminability.cassini_dss26_one_way import (
    USOCarrierModel,
    compile_dss26_one_way,
)


def test_frozen_predict_kernel_three_epoch_numerical_regression() -> None:
    kernel_root_value = os.environ["SATELLITE_RF_CASSINI_KERNEL_ROOT"]
    kernel_root = Path(kernel_root_value)
    kernel_paths = {spec.name: kernel_root / spec.name for spec in one_way.CASSINI_DSS26_KERNELS}
    carrier = USOCarrierModel(
        nominal_rest_frequency_hz=1.0,
        calibration_reference_utc="2005-06-06T17:50:01Z",
        constant_offset_hz=0.0,
        aging_rate_hz_s=0.0,
    )
    expected = (
        ("2005-06-06T17:50:01Z", 4_907.510879427195, 0.9999299036421737),
        ("2005-06-06T19:10:26Z", 4_907.850356847048, 0.9999293648478778),
        ("2005-06-06T20:30:51Z", 4_908.192765682936, 0.9999286935663851),
    )
    for receive_utc, light_time_s, frequency_factor in expected:
        prediction = compile_dss26_one_way(receive_utc, carrier, kernel_paths)
        assert prediction.geometric_light_time_s == pytest.approx(light_time_s, abs=1e-6)
        assert prediction.kinematic_frequency_factor == pytest.approx(frequency_factor, abs=1e-13)
        assert not prediction.primary_prediction_authorized
