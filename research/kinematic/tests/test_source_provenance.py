"""Byte-exact checkout regression for current scientific source manifests."""
import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT/'research/kinematic/results'
# This superseded report intentionally binds its diagnosed historical runner,
# not the corrected current source. Its original checkpoint remains preserved.
REPORTS = [p for p in sorted(RESULTS.glob('*study*.json')) if p.name != 'receiver_time_study_v1.json']


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
