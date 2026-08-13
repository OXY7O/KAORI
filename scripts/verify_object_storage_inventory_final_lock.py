#!/usr/bin/env python3
"""Fail closed on Object Storage Inventory release-surface drift."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = (
    'app/storage_inventory/routes.py',
    'app/storage_inventory/presentation.py',
    'app/templates/components/navigation/object_storage_menu.html',
    'app/templates/object_storage_inventory/overview/index.html',
    'app/templates/object_storage_inventory/systems/partials/_table_content.html',
    'app/templates/object_storage_inventory/buckets/partials/_table_content.html',
    'tests/contracts/storage_inventory',
)


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def main() -> int:
    errors: list[str] = []
    for relative in REQUIRED:
        if not (ROOT / relative).exists():
            errors.append(f'missing Object Storage Inventory final-lock artifact: {relative}')

    if errors:
        print('KAORI Object Storage Inventory Final Lock FAILED')
        for error in errors:
            print(f'- {error}')
        return 1

    routes = read('app/storage_inventory/routes.py')
    menu = read('app/templates/components/navigation/object_storage_menu.html')
    overview = read('app/templates/object_storage_inventory/overview/index.html')
    systems = read('app/templates/object_storage_inventory/systems/partials/_table_content.html')
    buckets = read('app/templates/object_storage_inventory/buckets/partials/_table_content.html')
    presentation = read('app/storage_inventory/presentation.py')

    for endpoint in (
        "url_for('object_storage_inventory.overview')",
        "url_for('object_storage_inventory.systems')",
        "url_for('object_storage_inventory.buckets')",
    ):
        if endpoint not in menu:
            errors.append(f'Object Storage navigation endpoint missing: {endpoint}')

    for token in (
        "url_prefix='/storage/object-storage'",
        "@permission_required('inventory.view')",
        'build_overview(',
        'build_systems(',
        'build_buckets(',
    ):
        if token not in routes:
            errors.append(f'Object Storage route boundary missing: {token}')

    if 'app.integrations.minio' in routes or 'MinioClient' in routes or 'MinIOClient' in routes:
        errors.append('Object Storage inventory routes must not query the live MinIO provider')

    for include in (
        'object_storage_inventory/overview/partials/_snapshot_boundary.html',
        'object_storage_inventory/overview/partials/_fleet_posture.html',
        'object_storage_inventory/overview/partials/_summary_cards.html',
        'object_storage_inventory/overview/partials/_systems_snapshot.html',
    ):
        if include not in overview:
            errors.append(f'Object Storage Overview composition missing: {include}')

    for token in (
        'Inventory Assets',
        'Open Provider Integration',
        "width='2xl'",
        'Authority Boundary',
        "job_key='object_storage.inventory.sync'",
    ):
        if token not in systems:
            errors.append(f'Object Storage Systems final-lock contract missing: {token}')

    for token in (
        'max-w-[88rem]',
        'Operational Reading',
        'Open Provider Integration',
        'Quota',
        'Protection',
        'Committed object-storage bucket and container inventory.',
    ):
        if token not in buckets:
            errors.append(f'Buckets & Containers final-lock contract missing: {token}')

    for token in (
        'ObjectStorageSystem.query',
        'ObjectStorageBucket.query',
        "'snapshot_source': 'Committed Snapshot'",
    ):
        if token not in presentation:
            errors.append(f'Committed-snapshot presentation boundary missing: {token}')

    if errors:
        print('KAORI Object Storage Inventory Final Lock FAILED')
        for error in errors:
            print(f'- {error}')
        return 1

    print('PASS — KAORI Object Storage Inventory Final Lock v1')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
