"""Byte-exact checkout regression for current scientific source manifests."""
import hashlib
import json
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT/'research/kinematic/results'
# This superseded report intentionally binds its diagnosed historical runner,
# not the corrected current source. Its original checkpoint remains preserved.
COMMIT_BOUND_REPORTS = {
    'real_reference_qualification_study_v1.json': ROOT/'research/kinematic/real_reference_qualification_plan.json',
    'real_reference_qualification_study_v2.json': ROOT/'research/kinematic/real_reference_qualification_plan_v2.json',
}
REPORTS = [p for p in sorted(RESULTS.glob('*study*.json'))
           if p.name != 'receiver_time_study_v1.json' and p.name not in COMMIT_BOUND_REPORTS]


@pytest.mark.parametrize('report', REPORTS, ids=lambda p: p.name)
def test_current_report_sources_survive_checkout_byte_exactly(report):
    manifest = json.loads(report.read_text(encoding='utf-8'))['sources_sha256']
    assert manifest
    for name, expected in manifest.items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == expected, name


def test_fixed_validation_plan_keeps_its_recorded_bytes():
    report = json.loads((RESULTS/'slow_validation_study_v1.json').read_text(encoding='utf-8'))
    plan = ROOT/'research/kinematic/slow_validation_plan.json'
    assert hashlib.sha256(plan.read_bytes()).hexdigest() == report['plan_sha256']


@pytest.mark.parametrize('name,plan', COMMIT_BOUND_REPORTS.items())
def test_commit_bound_real_receipts_keep_plan_and_implementation_identity(name, plan):
    """These execution receipts bind the code used, not later source bytes."""
    report = json.loads((RESULTS/name).read_text(encoding='utf-8'))
    freeze = report['freeze']
    assert re.fullmatch(r'[0-9a-f]{40}', freeze['source_commit'])
    assert re.fullmatch(r'[0-9a-f]{64}', freeze['implementation_sha256'])
    assert hashlib.sha256(plan.read_bytes()).hexdigest() == freeze['plan_sha256']
