"""Global Runtime detail resolves canonical and provider-specific IDs separately."""

from pathlib import Path
from types import SimpleNamespace

from app.integrations import service
from app.integrations.storage.object_storage.providers.minio.presentation import (
    _runtime_row,
)


def test_minio_runtime_row_uses_canonical_detail_identity_even_if_ids_differ():
    provider = SimpleNamespace(key='minio', label='MinIO')
    from app.integrations.storage.object_storage.providers.minio import presentation
    from unittest.mock import patch
    canonical = SimpleNamespace(id=77, provider_key='minio', adapter_key='s3', bindings=[], lifecycle_status='active', enabled=True)
    instance = SimpleNamespace(
        id=4, integration_instance=canonical, name='One', object_storage_system=SimpleNamespace(name='Store'),
        capabilities=['buckets'], last_checked_at=None, last_validated_at=None,
        detected_product='minio', last_status='connected', readiness_status='ready',
        capability_profile='minio', validation_message=None, last_error=None,
    )
    with patch.object(presentation, 'provider_kind', return_value=provider):
        row = _runtime_row(instance, None)
    assert row['instance_id'] == '4'
    assert row['detail_key'] == 'object_storage:77'


def test_generic_runtime_detail_resolves_provider_id_before_observation_lookup(monkeypatch):
    canonical_id, provider_id = 77, 4
    record = SimpleNamespace(id=provider_id)
    captured = {}
    class Module:
        def get_record_for_canonical(self, supplied):
            assert supplied == canonical_id
            return record
        def build_runtime_overview_rows(self, latest, supplied):
            assert supplied == canonical_id
            assert latest == {('object_storage', str(provider_id)): captured['observation']}
            return [{'instance_id': str(provider_id), 'detail_key': f'object_storage:{canonical_id}'}]
    monkeypatch.setattr(service, 'get_integration', lambda name: Module())
    def load_observation(integration_type, instance_id):
        assert (integration_type, instance_id) == ('object_storage', str(provider_id))
        captured['observation'] = SimpleNamespace(id=9)
        return captured['observation']
    monkeypatch.setattr(service, '_latest_runtime_observation', load_observation)
    row = service.build_integration_runtime_detail('object_storage', str(canonical_id))
    assert row['instance_id'] == '4'


def test_missing_generic_canonical_record_is_a_safe_not_found(monkeypatch):
    monkeypatch.setattr(service, 'get_integration', lambda _name: SimpleNamespace(get_record_for_canonical=lambda _id: None))
    assert service.build_integration_runtime_detail('object_storage', '77') is None


def test_runtime_source_uses_canonical_scope_not_provider_id():
    root = Path(__file__).resolve().parents[2]
    source = (root / 'app/integrations/storage/object_storage/providers/minio/presentation.py').read_text()
    assert 'MinioInstance.integration_instance_id == int(canonical_id)' in source
    assert 'MinioInstance.id == int(instance_id)' not in source
