"""Check the closed G14 record; never reacquire or refit a revealed event."""
from datetime import datetime
import json
from pathlib import Path

import pytest

from positioning.acquisition import digest
from positioning.jobs import status, dossier
from positioning.network import select_network

RUN = Path(__file__).resolve().parents[2] / 'experiments/positioning_g14_doy246_network'


def read(name):
    return json.loads((RUN/name).read_text())


def test_g14_terminal_and_byte_frozen_claim_survive_checkout():
    outcome=status(RUN)['outcome']
    assert outcome['status']=='INDEPENDENT_SATELLITE_POSITION_DEMONSTRATED'
    assert outcome['primary_pass']
    solution=read('solution.json');freeze=read('solution_freeze.json')
    assert digest(RUN/'solution.json')==freeze['solution_sha256']==outcome['solution_sha256']
    for name, expected in solution['input_hashes'].items():
        assert digest(RUN/name)==expected
    assert outcome['comparison']['error_3d_m']==pytest.approx(31.0169661315,abs=1e-8)
    assert outcome['prospective_uncertainty_radius_m']==pytest.approx(5755.157155537,abs=1e-8)
    assert outcome['heldout']['residual_m']==pytest.approx(-0.845590025,abs=1e-8)
    assert solution['uncertainty']['margin']==1.05
    assert dossier(RUN)['primary_pass']


def test_g14_selection_and_exclusion_follow_frozen_plan():
    plan=read('plan.json');structure=read('structure.json');admitted=read('estimation/admitted.json')
    selected=select_network(plan,structure['structures'])
    assert selected['fit_stations']==structure['selection']['fit_stations']==admitted['fit_stations']
    assert selected['selected_seconds_gpst']==structure['selection']['selected_seconds_gpst']
    assert admitted['stations']['GOLD00USA']['target_if_codes_m'] is None
    assert all('G14' not in obs['if_code_m'] for s in admitted['stations'].values() for obs in s['reference_observations'])
    assert not any(line.startswith('G14 ') for line in (RUN/'estimation/reference_only.rnx').read_text().splitlines())
    freeze=read('solution_freeze.json');heldout=read('heldout_reveal.json');oracle=read('oracle_access.json')
    assert datetime.fromisoformat(freeze['freeze_utc']) < datetime.fromisoformat(heldout['reveal_utc']) < datetime.fromisoformat(oracle['access_utc'])
