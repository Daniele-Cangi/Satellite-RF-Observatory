"""Preserve the complete reference-only qualification and replay its predictions."""
import gzip
import hashlib
import json
import subprocess

import numpy as np

from research.exploratory import reference_network_clocks as study

PRODUCER = '5614bb7638aebb8aa8c513f2a307c0d5c2ed205e'
RESULT_SHA256 = '73f1a463e51fb3abe7c53153d2204b95319334728c521dca316f37a28650585b'


def test_shared_structure_receipt_preserves_admission_predictions_and_raw_nonuniqueness():
    payload = (study.baseline.BASE/'results/shared_error_structure_v1.json.gz').read_bytes()
    assert hashlib.sha256(payload).hexdigest() == RESULT_SHA256
    result = json.loads(gzip.decompress(payload))
    assert result['schema'] == 'exposed-shared-error-structure-v1'
    raw, data = study.baseline.read_inputs()
    assert result['input_sha256'] == {k:hashlib.sha256(v).hexdigest() for k,v in raw.items()}
    for path, wanted in result['source_sha256'].items():
        source = subprocess.check_output(['git', 'show', PRODUCER+':'+path], cwd=study.baseline.BASE.parents[1])
        assert hashlib.sha256(source).hexdigest() == wanted
    assert not any(result[k] for k in ('candidate_products_used_in_own_fit', 'candidate_rf_used_in_own_network',
        'dedicated_candidate_rf_or_code_scoring', 'g12_state_accessed', 'oracle_tuning', 'new_confirmation',
        'physical_covariance_qualified', 'production_floors_changed', 'new_candidate_trajectory_fit'))
    assert result['all_predictions_before_validation_scoring']
    candidates = result['candidates']
    assert set(candidates) == set(data['plan']['references'])
    assert sum(len(c['windows']) for c in candidates.values()) == 440
    assert sum(c['prepared_arc_count'] for c in candidates.values()) == 63
    assert sum(w['status'] == 'PREPARED' for c in candidates.values() for w in c['windows']) == 63
    assert result['candidate_status_counts'] == {'INSUFFICIENT_PREPARED_ARCS':17, 'REFERENCE_CONTRASTS_AVAILABLE':5}
    for candidate, c in candidates.items():
        if 'structure' not in c:
            assert c['status'] == 'INSUFFICIENT_PREPARED_ARCS'
            continue
        rows = c['reference_rows']
        assert all(r['reference'] != candidate and r['phase_m'] == 0. for r in rows)
        replay = study.shared_error_structure.prepare(rows, candidate)
        assert replay['training_stop_s'] == c['structure']['training_stop_s']
        assert len(c['structure']['comparisons']) == 8
        for name, fitted in replay['comparisons'].items():
            actual = study.shared_error_structure.evaluate(fitted)
            recorded = c['structure']['comparisons'][name]
            assert actual['status'] == recorded['status']
            assert not recorded['physical_covariance_qualified']
            for part in ('training', 'validation'):
                assert actual[part]['status_counts'] == recorded[part]['status_counts']
                assert candidate not in sum(recorded[part]['reference_groups'], [])
            if 'predictors' not in actual:
                continue
            for part in ('training_moments', 'validation_moments'):
                for key in ('cross_covariance_m2', 'cross_eigenvalues_m2', 'consensus_covariance_m2', 'disagreement_covariance_m2'):
                    np.testing.assert_allclose(actual[part][key], recorded[part][key], atol=1e-9, rtol=1e-8)
            assert actual['common_moment_admissible'] == recorded['common_moment_admissible']
            for direction, predictor in actual['predictors'].items():
                own = recorded['predictors'][direction]
                for key in ('positive_common_gain', 'signed_gain', 'validation_times_s'):
                    np.testing.assert_allclose(predictor[key], own[key], atol=1e-9, rtol=1e-8)
                for label, prediction in predictor['predictions_m'].items():
                    np.testing.assert_allclose(prediction, own['predictions_m'][label], atol=1e-9, rtol=1e-8)
                    a, b = actual['scores'][direction][label], recorded['scores'][direction][label]
                    assert a['epoch_count'] == b['epoch_count']
                    assert a['worse_epochs_than_independent'] == b['worse_epochs_than_independent']
                    np.testing.assert_allclose(a['mean_square_m2'], b['mean_square_m2'], atol=1e-9, rtol=1e-8)
                    np.testing.assert_allclose(a['training_scaled_loss'], b['training_scaled_loss'], atol=1e-9, rtol=1e-8)
    witness = result['raw_identifiability']
    assert witness['raw_covariance_nullity'] == 7
    assert witness['separate_code_phase_covariance_nullity'] == 3
    h = np.asarray(witness['contrast_transform'])
    for law in witness['indistinguishable_laws'].values():
        np.testing.assert_allclose(h @ law['raw_increment_covariance_m2'] @ h.T, np.eye(2), atol=1e-12, rtol=0)
