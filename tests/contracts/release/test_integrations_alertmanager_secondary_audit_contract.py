from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
MATRIX_PATH = ROOT / 'docs' / 'architecture' / 'functional-capability-audit-matrix.json'
PROVIDER_MATRIX_PATH = ROOT / 'app' / 'definitions' / 'catalogs' / 'integrations' / 'provider_matrix.yaml'
RUNTIME_EVIDENCE_PATH = 'tests/integrations/runtime/test_recovery.py'


def test_alertmanager_secondary_behaviors_bind_canonical_runtime_recovery_evidence() -> None:
    provider_matrix = yaml.safe_load(PROVIDER_MATRIX_PATH.read_text(encoding='utf-8'))
    alert_sources = [item for item in provider_matrix['integration_types'] if item['key'] == 'alert_source']
    assert len(alert_sources) == 1
    assert alert_sources[0]['domain_key'] == 'observability'
    assert alert_sources[0]['providers'] == [
        {
            'key': 'alertmanager',
            'label': 'Alertmanager',
            'adapter_key': 'alertmanager_api_v2',
            'lifecycle': 'available',
            'protocol': 'alertmanager_api_v2',
        }
    ]

    evidence_path = ROOT / RUNTIME_EVIDENCE_PATH
    assert evidence_path.exists()

    payload = json.loads(MATRIX_PATH.read_text(encoding='utf-8'))
    behaviors = payload['surfaces']['integrations']['capabilities']['alertmanager_provider']['behaviors']
    for behavior_key in ('async_job', 'failure_recovery'):
        behavior = behaviors[behavior_key]
        assert behavior['state'] == 'covered'
        assert behavior['evidence'] == [RUNTIME_EVIDENCE_PATH]
