from io import BytesIO

import numpy as np
import pytest
from scipy.io import savemat

from research.exploratory import pnt_texbat_noaa as study


def header(value, label):
    return f'{value:<60}{label:<20}'


def rinex2(*, duplicate_time=False, changed_header=False):
    first = '  2012     9    14    12    45    0.0000000     GPS'
    assert first[48:51] == 'GPS'
    lines = [header('     2.11           OBSERVATION DATA    G (GPS)', 'RINEX VERSION / TYPE'),
             header('TXAU', 'MARKER NAME'),
             header('     0', 'RCV CLOCK OFFS APPL'),
             header('     6    L1    L2    P1    P2    S1    C1', '# / TYPES OF OBSERV'),
             header(first, 'TIME OF FIRST OBS')]
    if duplicate_time:
        lines.append(header(first[:-3] + 'UTC', 'TIME OF FIRST OBS'))
    lines.append(header('', 'END OF HEADER'))
    lines.append(' ' * 28 + '4  1')
    lines.append(header('splice', 'MARKER NAME' if changed_header else 'COMMENT'))
    prns = [f'G{prn:02d}' for prn in range(1, 14)]
    lines.append(' 12  9 14 12 45  0.0000000  0 13' + ''.join(prns[:12]))
    lines.append(' ' * 32 + prns[12])
    for prn in range(1, 14):
        lines.append(' ' * 80)
        lines.append(f'{21000000 + prn:14.3f}  ')
    return '\n'.join(lines)


def test_rinex2_reads_c1_in_second_observation_line_and_comment_splice():
    values, counts = study.rinex2_c1_text(rinex2(), 'TXAU')
    assert len(values) == 13
    assert values[(477900, 13)] == 21000013
    assert counts['comment_only_events'] == 1
    assert counts['ordinary_epochs'] == 1


def test_rinex2_rejects_ambiguous_time_or_header_update():
    with pytest.raises(ValueError, match='uniquely GPST'):
        study.rinex2_c1_text(rinex2(duplicate_time=True), 'TXAU')
    with pytest.raises(ValueError, match='header update'):
        study.rinex2_c1_text(rinex2(changed_header=True), 'TXAU')


def test_matlab_layout_and_preattack_anchor_fail_closed():
    matrix = np.zeros((14, 4))
    matrix[1] = [20, 20, 50, 50]
    matrix[2] = study.GPS_WEEK
    matrix[3] = [477900, 477900, 477930, 477930]
    matrix[7] = [21e6, 22e6, 21e6, 22e6]
    matrix[9] = 1
    matrix[13] = [3, 6, 3, 6]
    stream = BytesIO()
    savemat(stream, {'channel': matrix})
    selected, counts = study.select_gps_code(study.channel_rows(stream.getvalue()))
    assert counts['selected_code_rows'] == 4
    anchor, count = study.preattack_anchor(selected, selected)
    assert (anchor, count) == (477880, 4)
    altered = dict(selected)
    altered[250, 6] = (50, 477930, 22e6 + 1)
    with pytest.raises(ValueError, match='preattack'):
        study.preattack_anchor(selected, altered)
    matrix[1, 1] = 20  # Duplicate RRT and PRN, even when the numeric code differs.
    matrix[13, 1] = 3
    stream = BytesIO()
    savemat(stream, {'channel': matrix})
    with pytest.raises(ValueError, match='duplicate'):
        study.select_gps_code(study.channel_rows(stream.getvalue()))


def test_common_mode_attack_is_visible_in_code_but_not_satellite_difference():
    clean = {(250, 3): (50, 477930, 20e6), (250, 6): (50, 477930, 22e6),
             (850, 3): (170, 478050, 20e6), (850, 6): (170, 478050, 22e6)}
    attack = dict(clean)
    attack[850, 3] = (170, 478050, 20e6 + 100)
    attack[850, 6] = (170, 478050, 22e6 + 101)
    refs = {'TXAU': {(477930, 3): 21e6, (477930, 6): 23e6,
                     (478050, 3): 21e6, (478050, 6): 23e6},
            'SAM2': {(477930, 3): 21.1e6, (477930, 6): 23.1e6,
                     (478050, 3): 21.1e6, (478050, 6): 23.1e6}}
    summary, counts, per_epoch = study.compare(clean, attack, refs, 477880)
    assert summary['time_push']['median_signed_local_code_change_m'] == 100.5
    assert summary['time_push']['median_absolute_satellite_difference_change_m'] == 1
    assert counts['matched_rows'] == 4
    assert per_epoch[-1]['reference_prn'] == 3
