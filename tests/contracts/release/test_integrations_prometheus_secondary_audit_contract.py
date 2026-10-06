from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
MATRIX_PATH = ROOT / 'docs' / 'architecture' / 'functional-capability-audit-matrix.json'
PROVIDER_MATRIX_PATH = ROOT / 'app' / 'definitions' / 'catalogs' / 'integrations' / 'provider_matrix.yaml'
VALIDATION_EVIDENCE_PATH = 'tests/integrations/test_metrics_source_kubernetes_identity.py'


def test_prometheus_validation_behavior_binds_canonical_metrics_source_evidence() -> None:
    provider_matrix = yaml.safe_load(PROVIDER_MATRIX_PATH.read_text(encoding='utf-8'))
    metrics_sources = [item for item in provider_matrix['integration_types'] if item['key'] == 'metrics_source']
    assert len(metrics_sources) == 1
    assert metrics_sources[0]['domain_key'] == 'observability'

    prometheus = [item for item in metrics_sources[0]['providers'] if item['key'] == 'prometheus']
    assert prometheus == [
        {
            'key': 'prometheus',
            'label': 'Prometheus',
            'adapter_key': 'prometheus_http',
            'lifecycle': 'available',
            'protocol': 'prometheus_http',
        }
    ]

    evidence_path = ROOT / VALIDATION_EVIDENCE_PATH
    assert evidence_path.exists()

    payload = json.loads(MATRIX_PATH.read_text(encoding='utf-8'))
    behaviors = payload['surfaces']['integrations']['capabilities']['prometheus_provider']['behaviors']
    behavior = behaviors['validation_dependency']
    assert behavior['state'] == 'covered'
    assert behavior['evidence'] == [VALIDATION_EVIDENCE_PATH]
