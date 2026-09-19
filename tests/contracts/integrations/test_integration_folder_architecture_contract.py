from __future__ import annotations

import ast
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
        'app/integrations/observability/metrics_source/application',
        'app/integrations/observability/alert_source/providers/alertmanager/application',
        'app/integrations/storage/object_storage/providers/minio/application',
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


def _absolute_imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    targets: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            targets.append(node.module)
    return tuple(targets)


def test_product_directories_and_imports_stay_below_canonical_provider_boundaries() -> None:
    integration_root = ROOT / 'app/integrations'
    product_names = {
        'alertmanager',
        'aws_s3',
        'azure_blob',
        'garage',
        'hpe_alletra',
        'kubernetes',
        'minio',
        'netapp_ontap',
        'netapp_ontap_nfs',
        'prometheus',
        'rancher',
        'sangfor_kubernetes_engine',
        'thanos',
    }
    forbidden_imports = (
        'app.integrations.kubernetes',
        'app.integrations.metrics',
        'app.integrations.alertmanager',
        'app.integrations.minio',
        'app.metrics',
        'app.alertmanager',
        'app.minio',
    )

    for path in integration_root.rglob('*'):
        if path.is_dir() and path.name in product_names:
            assert 'providers' in path.relative_to(integration_root).parts, path

    for path in (ROOT / 'app').rglob('*.py'):
        for target in _absolute_imports(path):
            assert not any(target == prefix or target.startswith(f'{prefix}.') for prefix in forbidden_imports), (
                path,
                target,
            )

    for retired in (
        'app/templates/integrations/kubernetes',
        'app/templates/integrations/metrics',
        'app/templates/integrations/alertmanager',
        'app/templates/metrics',
        'app/templates/alertmanager',
        'app/templates/minio',
        'app/integrations/observability/metrics_source/prometheus_http_client.py',
        'app/integrations/observability/metrics_source/prometheus_http_runtime.py',
        'app/integrations/observability/metrics_source/prometheus_http_validation.py',
    ):
        assert not (ROOT / retired).exists(), retired
