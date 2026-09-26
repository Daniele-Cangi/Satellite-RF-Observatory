"""Reference-only clock admission and retained real-data failures."""
import json

import pytest

from research.exploratory import reference_phase_clock as study


class Poison:
    def __float__(self):
        raise AssertionError('excluded reference was decoded')


def test_excluded_value_is_never_read_and_failure_is_closed():
    rows = [{'reference': f'G{i:02}', 'phase_minus_model_rate_m_s': float(i)}
            for i in range(1, 6)]
    rows.append({'reference': 'G12', 'phase_minus_model_rate_m_s': Poison()})
    for method in ('mean', 'median'):
        estimate = study.clock_rate(rows, excluded='G12', estimator=method)
        assert estimate['status'] == 'ESTIMATED'
        assert estimate['rate_m_s'] == 3.
    assert study.clock_rate(rows[:3], excluded='G12')['status'] == 'INSUFFICIENT_REFERENCES'
    assert study.clock_rate(rows+[rows[0]], excluded='G12')['status'] == 'DUPLICATE_REFERENCE'
    rows[0]['phase_minus_model_rate_m_s'] = float('nan')
    assert study.clock_rate(rows, excluded='G12')['status'] == 'INVALID_REFERENCE_RATE'


def test_median_resists_one_unflagged_jump_without_hiding_it():
    rows = [{'reference': f'G{i:02}', 'phase_minus_model_rate_m_s': value}
            for i, value in enumerate((.001, .0011, .0009, .0012, .029), start=1)]
    assert study.clock_rate(rows, excluded='G12', estimator='median')['rate_m_s'] == .0011
    assert study.clock_rate(rows, excluded='G12', estimator='mean')['rate_m_s'] > .006
    held = study.clock_rate(rows, excluded='G05', estimator='median')
    assert rows[-1]['phase_minus_model_rate_m_s']-held['rate_m_s'] > .027


def test_retained_exposed_report_does_not_claim_absolute_clock_bound():
    path = study.BASE/'results/reference_phase_clock_v1.json'
    result = json.loads(path.read_bytes())
    assert not result['target_values_accessed'] and result['target_excluded'] == 'G12'
    assert result['summary']['held_out_count'] == len(result['held_out_reference_diagnostics'])
    assert result['stations']['BOGT00COL']['status'] != 'EVALUATED'
    assert result['stations']['YELL00CAN']['status'] != 'EVALUATED'
    assert result['summary']['held_out']['median']['max_abs'] > .02
    assert any(row['station'] == 'BRAZ00BRA' and row['reference'] == 'G13'
               and row['time_s'] == 38040 and row['error_m_s_median'] > .02
               for row in result['held_out_reference_diagnostics'])
    assert 'No absolute clock' in result['scope']
