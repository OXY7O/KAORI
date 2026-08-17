#!/usr/bin/env python3
"""Lock KAORI's domain → integration type → provider/adapter folder architecture."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'app'

REQUIRED_PATHS = (
    'app/integrations/orchestration/container_orchestrator/adapters/kubernetes_api',
    'app/integrations/observability/metrics_source/adapters/prometheus_http',
    'app/integrations/observability/alert_source/providers/alertmanager',
    'app/integrations/storage/object_storage/adapters/s3',
    'app/integrations/storage/object_storage/providers/minio',
    'app/integrations/storage/file_storage',
    'app/integrations/storage/block_storage',
    'app/integrations/delivery/notification_channels',
    'app/integrations/observability/metrics_source/application',
    'app/integrations/observability/alert_source/providers/alertmanager/application',
    'app/integrations/storage/object_storage/providers/minio/application',
    'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes',
    'app/templates/integrations/observability/metrics_source',
    'app/templates/integrations/observability/alert_source/providers/alertmanager',
    'app/templates/integrations/storage/object_storage/providers/minio',
    'app/templates/integrations/delivery/notification_channels',
    'app/definitions/catalogs/integrations/orchestration/container_orchestrator/providers/kubernetes.yaml',
    'app/definitions/catalogs/integrations/observability/metrics_source/contract.yaml',
    'app/definitions/catalogs/integrations/observability/alert_source/providers/alertmanager.yaml',
    'app/definitions/catalogs/integrations/storage/object_storage/contract.yaml',
)

FORBIDDEN_PATHS = (
    'app/integrations/kubernetes',
    'app/integrations/metrics',
    'app/integrations/alertmanager',
    'app/integrations/minio',
    'app/notification_channels',
    'app/metrics',
    'app/alertmanager',
    'app/minio',
    'app/templates/integrations/kubernetes',
    'app/templates/integrations/metrics',
    'app/templates/integrations/alertmanager',
    'app/templates/metrics',
    'app/templates/alertmanager',
    'app/templates/minio',
    'app/definitions/catalogs/integrations/kubernetes.yaml',
    'app/definitions/catalogs/integrations/metrics_source.yaml',
    'app/definitions/catalogs/integrations/alertmanager.yaml',
    'app/definitions/catalogs/integrations/object_storage.yaml',
    'app/integrations/observability/metrics_source/prometheus_http_client.py',
    'app/integrations/observability/metrics_source/prometheus_http_runtime.py',
    'app/integrations/observability/metrics_source/prometheus_http_validation.py',
)

FORBIDDEN_IMPORT_PREFIXES = (
    'app.integrations.kubernetes',
    'app.integrations.metrics',
    'app.integrations.alertmanager',
    'app.integrations.minio',
    'app.metrics',
    'app.alertmanager',
    'app.minio',
)

ALLOWED_INTEGRATION_ROOT_DIRS = {
    '__pycache__',
    'consumer',
    'contracts',
    'observability',
    'orchestration',
    'runtime',
    'storage',
    'delivery',
    'validation',
}

PRODUCT_DIR_NAMES = {
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


def _absolute_imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    targets: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            targets.append(node.module)
    return tuple(targets)


def main() -> int:
    errors: list[str] = []

    for relative in REQUIRED_PATHS:
        if not (ROOT / relative).exists():
            errors.append(f'canonical integration path is missing: {relative}')

    for relative in FORBIDDEN_PATHS:
        if (ROOT / relative).exists():
            errors.append(f'legacy/product-first integration path still exists: {relative}')

    integration_root = APP / 'integrations'
    for child in sorted(integration_root.iterdir()):
        if child.is_dir() and child.name not in ALLOWED_INTEGRATION_ROOT_DIRS:
            errors.append(f'non-canonical directory exists directly under app/integrations: {child.name}')

    for path in integration_root.rglob('*'):
        if not path.is_dir() or path.name not in PRODUCT_DIR_NAMES:
            continue
        relative_parts = path.relative_to(integration_root).parts
        if 'providers' not in relative_parts:
            errors.append('product directory must live below providers/: ' + path.relative_to(ROOT).as_posix())

    for path in APP.rglob('*.py'):
        for target in _absolute_imports(path):
            if any(target == prefix or target.startswith(f'{prefix}.') for prefix in FORBIDDEN_IMPORT_PREFIXES):
                errors.append(f'{path.relative_to(ROOT)} imports retired product-first namespace {target}')

    metrics_adapter = ROOT / 'app/integrations/observability/metrics_source/adapters/prometheus_http'
    for filename in ('client.py', 'runtime.py', 'validation.py'):
        if not (metrics_adapter / filename).exists():
            errors.append(f'Prometheus HTTP adapter is incomplete: missing {filename}')

    s3_client = ROOT / 'app/integrations/storage/object_storage/adapters/s3/client.py'
    if s3_client.exists():
        source = s3_client.read_text(encoding='utf-8')
        for marker in ('def build_s3_client(', 'def list_buckets(', 'class S3TransportFailure'):
            if marker not in source:
                errors.append(f'S3 shared adapter is incomplete: missing {marker}')

    minio_client = ROOT / 'app/integrations/storage/object_storage/providers/minio/client.py'
    if minio_client.exists():
        source = minio_client.read_text(encoding='utf-8')
        if 'from app.integrations.storage.object_storage.adapters.s3 import (' not in source:
            errors.append('MinIO provider must reuse the shared S3 adapter.')
        if 'def build_s3_client(' in source:
            errors.append('MinIO provider must not duplicate the shared S3 client builder.')

    if errors:
        print('FAIL — KAORI Integration Folder Architecture')
        for error in errors:
            print(f'- {error}')
        return 1

    print('PASS — KAORI Integration Folder Architecture')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
