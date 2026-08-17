from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_integration_kernel_follows_domain_type_provider_adapter_hierarchy() -> None:
    required = (
        'app/integrations/orchestration/container_orchestrator/adapters/kubernetes_api',
        'app/integrations/observability/metrics_source/adapters/prometheus_http',
        'app/integrations/observability/alert_source/providers/alertmanager',
        'app/integrations/storage/object_storage/adapters/s3',
        'app/integrations/storage/object_storage/providers/minio',
        'app/integrations/storage/file_storage',
        'app/integrations/storage/block_storage',
    )
    for relative in required:
        assert (ROOT / relative).exists(), relative

    forbidden = (
        'app/integrations/kubernetes',
        'app/integrations/metrics',
        'app/integrations/alertmanager',
        'app/integrations/minio',
    )
    for relative in forbidden:
        assert not (ROOT / relative).exists(), relative


def test_application_templates_and_definitions_mirror_integration_hierarchy() -> None:
    required = (
        'app/metrics_sources',
        'app/alert_sources/providers/alertmanager',
        'app/object_storage/providers/minio',
        'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes',
        'app/templates/integrations/observability/metrics_source',
        'app/templates/integrations/observability/alert_source/providers/alertmanager',
        'app/templates/integrations/storage/object_storage/providers/minio',
        'app/definitions/catalogs/integrations/orchestration/container_orchestrator/providers/kubernetes.yaml',
        'app/definitions/catalogs/integrations/observability/metrics_source/contract.yaml',
        'app/definitions/catalogs/integrations/observability/alert_source/providers/alertmanager.yaml',
        'app/definitions/catalogs/integrations/storage/object_storage/contract.yaml',
    )
    for relative in required:
        assert (ROOT / relative).exists(), relative


def test_minio_reuses_shared_s3_transport_instead_of_owning_transport_copy() -> None:
    adapter = read('app/integrations/storage/object_storage/adapters/s3/client.py')
    provider = read('app/integrations/storage/object_storage/providers/minio/client.py')

    assert 'def build_s3_client(' in adapter
    assert 'def list_buckets(' in adapter
    assert 'class S3TransportFailure' in adapter
    assert 'from app.integrations.storage.object_storage.adapters.s3 import (' in provider
    assert 'def build_s3_client(' not in provider


def test_folder_architecture_verifier_is_part_of_the_lock() -> None:
    verifier = read('scripts/verify_integration_folder_architecture.py')
    assert 'PASS — KAORI Integration Folder Architecture' in verifier
    assert 'product directory must live below providers/' in verifier
    assert 'MinIO provider must reuse the shared S3 adapter.' in verifier
