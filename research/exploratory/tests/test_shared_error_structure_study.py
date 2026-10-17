"""The structure study never opens candidate scoring or scores an unfrozen fold."""
from research.exploratory import reference_network_clocks as study


def test_every_structure_predictor_precedes_scoring_and_unsupported_candidates_remain(monkeypatch):
    events = []
    monkeypatch.setattr(study.baseline, 'read_inputs', lambda: ({'plan': b'input'}, {'plan': {'references': ['G05', 'G11', 'G19']}}))
    monkeypatch.setattr(study.baseline.interval.shared.meteo, 'WeatherGrid', lambda *a: None)
    monkeypatch.setattr(study.baseline.interval.shared.meteo, 'read_inputs', lambda: ({}, {}))
    monkeypatch.setattr(study.baseline, 'build_arcs', lambda d,q,w: (
        [] if q == 'G19' else [{'endpoint_gpst_s': 30.}, {'endpoint_gpst_s': 60.}], [{'status': 'RF_MASK_UNSUPPORTED'}]))
    monkeypatch.setattr(study, 'reference_rows', lambda *a, **k: ([{'station': 'A', 'reference': 'G20',
        'time_s': 30., 'segment': 'A/G20', 'code_m': 100., 'phase_m': 2., 'mw_m': 3.}], {}))
    def prepare(rows, candidate):
        assert rows[0]['code_m'] == 98. and rows[0]['phase_m'] == 0.
        events.append('fit '+candidate)
        return {'comparisons': {'case': {'candidate': candidate}}}
    def evaluate(record):
        assert events[:2] == ['fit G05', 'fit G11']
        events.append('score '+record['candidate'])
        return {'status': 'POSITIVE_SHARED_STRUCTURE_UNQUALIFIED'}
    def forbidden(*args, **kwargs):
        raise AssertionError('dedicated candidate scoring entered')
    monkeypatch.setattr(study.shared_error_structure, 'prepare', prepare)
    monkeypatch.setattr(study.shared_error_structure, 'evaluate', evaluate)
    for name in ('oracle', 'score_rf', 'state_errors'):
        monkeypatch.setattr(study.baseline, name, forbidden)
    monkeypatch.setattr(study, 'score_mw', forbidden)
    result = study.run(structure=True)
    assert events == ['fit G05', 'fit G11', 'score G05', 'score G11']
    assert result['candidate_status_counts'] == {'REFERENCE_CONTRASTS_AVAILABLE': 2, 'INSUFFICIENT_PREPARED_ARCS': 1}
    assert result['candidates']['G19']['windows'] == [{'status': 'RF_MASK_UNSUPPORTED'}]
    assert not result['dedicated_candidate_rf_or_code_scoring']
    assert not result['new_candidate_trajectory_fit']
