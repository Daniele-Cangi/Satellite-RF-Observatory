"""Signed-error diagnosis without fitting/tuning another predictive model."""
import pytest

from research.exploratory.g20_prediction_diagnosis import correction_decomposition
from research.exploratory import g20_prediction_diagnosis as diagnosis


def test_anticorrelated_correction_is_not_confused_with_too_large_helpful_correction():
    keys = [('A','G01',300.),('B','G02',300.)]
    base = dict(zip(keys,[1.,-1.]))
    corrected = dict(zip(keys,[1.5,-1.5]))
    result = correction_decomposition(base,corrected,keys)
    assert result['error_correction_mean_product_m2'] == -.5
    assert result['correction_energy_m2'] == .25
    assert result['delta_mse_m2'] == pytest.approx(result['corrected_rms_m']**2-result['baseline_rms_m']**2)
    assert result['worse_absolute_error_count'] == 2


def test_missing_original_key_is_not_silently_removed_from_diagnosis():
    with pytest.raises(KeyError):
        correction_decomposition({('A','G01',300.):1.},{},[('A','G01',300.)])


def test_entrypoint_reaches_explicit_input_guard_before_any_numeric_fit(tmp_path, monkeypatch):
    archive = tmp_path/'wrong.gz'
    archive.write_bytes(b'not the admitted archive')
    monkeypatch.setattr(diagnosis,'ARCHIVE',archive)
    with pytest.raises(ValueError, match='stable input hash mismatch'):
        diagnosis.main()
