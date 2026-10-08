"""Real exposed recording replay, matched comparison and visible unavailable cases."""

from pathlib import Path
import gzip
import json

import pytest

from research.exploratory import pnt_yunnan_network as study


@pytest.fixture(scope='module')
def report():
    return study.run()


def test_native_association_refuses_rounding_large_gaps_ties_and_duplicates():
    assert study.nearest_native([30.004], 30) == (0, 'ASSOCIATED')
    assert study.nearest_native([29.4, 30.6], 30)[0] is None
    assert study.nearest_native([29.8, 30.2], 30)[1] == 'AMBIGUOUS_NATIVE_EPOCH'
    assert study.nearest_native([30.004, 30.004], 30)[1] == 'AMBIGUOUS_NATIVE_EPOCH'
    assert study.nearest_native([], 30)[1] == 'MISSING_NATIVE_EPOCH'


def test_real_sources_and_nav_join_keep_gaps_and_different_host_labels(report):
    assert len(report['native_epoch_audit']) == 7124
    assert report['native_status_counts']['OUTSIDE_DECLARED_DAY'] == 248
    first = report['navigation_pairing']['12']['status_counts']
    later = report['navigation_pairing']['18']['status_counts']
    assert first == {'PAIRED': 3593, 'MISSING_CLOCK': 7}
    assert later == {'MISSING_PVT': 55, 'MISSING_CLOCK': 15, 'PAIRED': 3530}
    pairs = report['navigation_pairing']['18']['epochs']
    missing = next(row for row in pairs if row['iTOW'] == 381617000)
    assert missing['status'] == 'MISSING_CLOCK'
    pair = next(row for row in pairs if row['iTOW'] == 381619000)
    assert pair['pvt_sources'] == ['2023-12-21 18:00:02']
    assert pair['clock_sources'] == ['2023-12-21 18:00:03']
    assert all(report['sources'][name]['distance_to_paper_coordinate_m'] > 1e6
               for name in ('CUSV', 'JFNG'))


def test_native_model_time_and_comparison_denominators_remain_explicit(report):
    assert report['coverage']['requested_reference_epochs'] == 240
    assert report['coverage']['matched_status_counts'] == {'EVALUATED': 204, 'INSUFFICIENT_EVIDENCE': 36}
    assert sum(report['coverage']['association_status_counts'].values()) == 240
    assert report['comparison']['unassigned_metadata_window_epochs'] == 13
    first = report['epochs'][0]
    assert first['local_source_label'] == '2023-12-21 12:00:13'
    times = first['diagnostic']['receiver_measurement_gpst_s']
    assert times == {'local': 14430.007, 'JFNG': 14430., 'CUSV': 14430.}
    for epoch in report['epochs']:
        matched = epoch['diagnostic']['matched']
        assert all(fit['satellites'] == matched['satellites'] for fit in matched['receiver_fits'].values())
    assert report['assessments']['network_detection_gain'] == 'NOT_ASSESSED'


def test_worsening_and_post_disturbance_outliers_remain_in_comparison(report):
    summary = report['table13_windows']['after_logged_disturbance']
    assert summary['combined_residual_larger_epochs'] > 0
    assert summary['local_satellite_difference']['maximum_m'] > 1e6
    assert summary['combined_mean_double_difference']['maximum_m'] > 1e6
    assert report['table13_windows']['attack_1']['evaluated_matched_epochs'] == 0
    assert report['table13_windows']['attack_2']['evaluated_matched_epochs'] == 0


def test_replay_matches_retained_numerical_evidence(report):
    stored = json.loads(gzip.decompress(Path(study.__file__).with_name('results').joinpath(
        'pnt_yunnan_native_network.json.gz').read_bytes()))
    # Byte hashes, associations and counts are exact; float fits may differ
    # across BLAS/platforms, so compare physical diagnostics at sub-mm scale.
    for name, source in report['sources'].items():
        retained = stored['sources'][name]
        for key, value in source.items():
            if key == 'antenna_ecef_m':
                assert value == pytest.approx(retained[key], abs=1e-6, rel=0)
            elif key == 'distance_to_paper_coordinate_m':
                assert value == pytest.approx(retained[key], abs=1e-6, rel=0)
            else:
                assert value == retained[key]
    assert report['native_epoch_audit'] == stored['native_epoch_audit']
    assert report['navigation_pairing'] == stored['navigation_pairing']
    assert report['coverage'] == stored['coverage']
    for current, retained in zip(report['epochs'], stored['epochs'], strict=True):
        a, b = current['diagnostic']['matched'], retained['diagnostic']['matched']
        assert a['status'] == b['status'] and a['satellites'] == b['satellites']
        if a['status'] == 'EVALUATED':
            for name in a['receiver_fits']:
                first, second = a['receiver_fits'][name], b['receiver_fits'][name]
                assert first['clock_m'] == pytest.approx(second['clock_m'], abs=1e-4, rel=0)
                assert first['satellite_residuals_m'] == pytest.approx(
                    second['satellite_residuals_m'], abs=1e-4, rel=0)
