from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
MATRIX_PATH = ROOT / 'docs' / 'architecture' / 'functional-capability-audit-matrix.json'
PROVIDER_MATRIX_PATH = ROOT / 'app' / 'definitions' / 'catalogs' / 'integrations' / 'provider_matrix.yaml'
VALIDATION_EVIDENCE_PATH = 'tests/integrations/test_minio_compatibility_profiles.py'


def test_object_storage_validation_behavior_binds_available_minio_evidence() -> None:
    provider_matrix = yaml.safe_load(PROVIDER_MATRIX_PATH.read_text(encoding='utf-8'))
    object_storage_types = [item for item in provider_matrix['integration_types'] if item['key'] == 'object_storage']
    assert len(object_storage_types) == 1
    assert object_storage_types[0]['domain_key'] == 'storage'

    available_providers = [item for item in object_storage_types[0]['providers'] if item['lifecycle'] == 'available']
    assert available_providers == [
        {
            'key': 'minio',
            'label': 'MinIO',
            'adapter_key': 's3',
            'lifecycle': 'available',
            'protocol': 's3',
        }
    ]

    evidence_path = ROOT / VALIDATION_EVIDENCE_PATH
    assert evidence_path.exists()

    payload = json.loads(MATRIX_PATH.read_text(encoding='utf-8'))
    behaviors = payload['surfaces']['integrations']['capabilities']['object_storage_provider']['behaviors']
    behavior = behaviors['validation_dependency']
    assert behavior['state'] == 'covered'
    assert behavior['evidence'] == [VALIDATION_EVIDENCE_PATH]
