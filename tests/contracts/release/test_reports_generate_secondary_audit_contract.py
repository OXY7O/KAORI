from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MATRIX_PATH = ROOT / 'docs' / 'architecture' / 'functional-capability-audit-matrix.json'
EXECUTION_EVIDENCE_PATH = 'tests/reports/test_generate_execution_characterization.py'


def test_reports_generate_authorization_binds_execution_evidence() -> None:
    payload = json.loads(MATRIX_PATH.read_text(encoding='utf-8'))
    behaviors = payload['surfaces']['reports']['capabilities']['generate']['behaviors']

    assert behaviors['authorization'] == {
        'state': 'covered',
        'evidence': [EXECUTION_EVIDENCE_PATH],
    }


def test_reports_generate_persistence_binds_execution_evidence() -> None:
    payload = json.loads(MATRIX_PATH.read_text(encoding='utf-8'))
    behaviors = payload['surfaces']['reports']['capabilities']['generate']['behaviors']

    assert behaviors['persistence'] == {
        'state': 'covered',
        'evidence': [EXECUTION_EVIDENCE_PATH],
    }
