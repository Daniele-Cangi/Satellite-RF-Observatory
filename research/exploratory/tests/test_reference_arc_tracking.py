"""Raw stream admission and regression for the exposed BRAZ/G05 witness."""
import json

from research.exploratory import reference_arc_tracking as tracking


def test_reference_replay_preserves_causal_alert_and_quarantine():
    data = json.loads(tracking.base.REFERENCE.read_bytes())
    result = tracking.replay(data)
    assert sum(result['statuses'].values()) == result['observation_count']
    cohort = data['cohorts']['day']
    assert result['observation_count'] == sum(
        len(item['rows']) for item in cohort['stations'].values()
        if tracking.base.header_status(item) == 'SUPPORTED_RAW_SIGNALS'
    )

    link = {r['time_s']: r for r in result['decisions']
            if r['station'] == 'BRAZ00BRA' and r['reference'] == 'G05'}
    before, alert, after = (link[t] for t in (39540., 39570., 39600.))
    assert alert['lli'] == ['0','0']
    assert alert['status'] == 'ARC_BREAK' and alert['arc'] is None
    assert alert['gf']['break'] and alert['mw']['break']
    assert alert['closed_arc'] == before['arc']
    assert after['status'] == 'ARC_START' and after['arc'] != before['arc']

    # Replaying a prefix gives exactly the same decisions through the alert.
    # Forbidden identities and rejected samples cannot read their RF payload.
    class Forbidden:
        def __float__(self):
            raise AssertionError('inadmissible payload accessed')

    for item in cohort['stations'].values():
        if 'rows' not in item:
            continue
        item['rows'] = [r for r in item['rows'] if r['time_s'] <= 39570.]
        for row in item['rows']:
            if row['status'] != 'AVAILABLE':
                row['fields'] = Forbidden()
        item['rows'].insert(0, {'reference':'G12', 'time_s':Forbidden()})
    prefix = tracking.replay(data)
    assert prefix['decisions'] == [r for r in result['decisions'] if r['time_s'] <= 39570.]
