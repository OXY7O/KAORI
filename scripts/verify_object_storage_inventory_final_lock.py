#!/usr/bin/env python3
"""Fail closed on Object Storage Inventory release-surface drift."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = (
    'app/inventory/object_storage/routes.py',
    'app/inventory/object_storage/presentation.py',
    'app/templates/components/navigation/object_storage_menu.html',
    'app/templates/inventory/object_storage/overview/index.html',
    'app/templates/inventory/object_storage/components/_hero_blocked_context.html',
    'app/templates/inventory/object_storage/components/_onboarding_banner.html',
    'app/templates/inventory/object_storage/components/_snapshot_context.html',
    'migrations/versions/20260814_object_storage_rbac_split.py',
    'app/templates/inventory/object_storage/systems/partials/_snapshot_boundary.html',
    'app/templates/inventory/object_storage/buckets/partials/_snapshot_boundary.html',
    'app/templates/inventory/object_storage/systems/partials/_table_content.html',
    'app/templates/inventory/object_storage/buckets/partials/_table_content.html',
    'tests/contracts/inventory/object_storage',
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

    routes = read('app/inventory/object_storage/routes.py')
    menu = read('app/templates/components/navigation/object_storage_menu.html')
    overview = read('app/templates/inventory/object_storage/overview/index.html')
    systems_workspace = read('app/templates/inventory/object_storage/systems/partials/_page_workspace.html')
    buckets_workspace = read('app/templates/inventory/object_storage/buckets/partials/_page_workspace.html')
    systems_snapshot = read('app/templates/inventory/object_storage/systems/partials/_snapshot_boundary.html')
    buckets_snapshot = read('app/templates/inventory/object_storage/buckets/partials/_snapshot_boundary.html')
    blocker = read('app/templates/inventory/object_storage/components/_hero_blocked_context.html')
    onboarding = read('app/templates/inventory/object_storage/components/_onboarding_banner.html')
    systems = read('app/templates/inventory/object_storage/systems/partials/_table_content.html')
    buckets = read('app/templates/inventory/object_storage/buckets/partials/_table_content.html')
    presentation = read('app/inventory/object_storage/presentation.py')

    for endpoint in (
        "url_for('object_storage_inventory.overview')",
        "url_for('object_storage_inventory.systems')",
        "url_for('object_storage_inventory.buckets')",
    ):
        if endpoint not in menu:
            errors.append(f'Object Storage navigation endpoint missing: {endpoint}')

    for token in (
        "url_prefix='/storage/object-storage'",
        "@permission_required('object_storage_inventory.view')",
        'build_overview(',
        'build_systems(',
        'build_buckets(',
    ):
        if token not in routes:
            errors.append(f'Object Storage route boundary missing: {token}')

    if 'app.integrations.minio' in routes or 'MinioClient' in routes or 'MinIOClient' in routes:
        errors.append('Object Storage inventory routes must not query the live MinIO provider')

    for include in (
        'inventory/object_storage/overview/partials/_snapshot_boundary.html',
        'inventory/object_storage/overview/partials/_fleet_posture.html',
        'inventory/object_storage/overview/partials/_summary_cards.html',
        'inventory/object_storage/overview/partials/_systems_snapshot.html',
    ):
        if include not in overview:
            errors.append(f'Object Storage Overview composition missing: {include}')

    for token in (
        'overview.setup.is_blocked',
        'inventory/object_storage/components/_onboarding_banner.html',
    ):
        if token not in overview:
            errors.append(f'Object Storage setup-blocked Overview contract missing: {token}')

    for source, label in ((systems_workspace, 'Systems'), (buckets_workspace, 'Buckets & Containers')):
        for token in ('inventory.setup.is_blocked', '_snapshot_boundary.html', '_onboarding_banner.html'):
            if token not in source:
                errors.append(f'{label} setup/snapshot composition missing: {token}')

    for source, label in ((systems_snapshot, 'Systems'), (buckets_snapshot, 'Buckets & Containers')):
        if 'object_storage_snapshot.render(inventory.snapshot)' not in source:
            errors.append(f'{label} Inventory Data Snapshot contract missing')

    for token in ('Object Storage Setup Required', 'Registered Systems', 'Workspace State', 'Blocked'):
        if token not in blocker:
            errors.append(f'Object Storage blocked Hero contract missing: {token}')

    for relative in (
        'app/templates/inventory/object_storage/overview/partials/_hero.html',
        'app/templates/inventory/object_storage/systems/partials/_hero.html',
        'app/templates/inventory/object_storage/buckets/partials/_hero.html',
    ):
        hero_source = read(relative)
        if 'page_hero.aside_classes()' not in hero_source:
            errors.append(f'Object Storage blocked Hero must retain canonical aside geometry: {relative}')

    for token in ("url_for('integrations.storage')", 'settings.manage_integrations', 'Register Your First Object Storage System'):
        if token not in onboarding:
            errors.append(f'Object Storage onboarding ownership contract missing: {token}')

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
        "'is_blocked': total_systems == 0",
        "'snapshot': _overview_snapshot(all_rows)",
        "'snapshot': _overview_snapshot(system_rows)",
    ):
        if token not in presentation:
            errors.append(f'Committed-snapshot presentation boundary missing: {token}')

    if errors:
        print('KAORI Object Storage Inventory Final Lock FAILED')
        for error in errors:
            print(f'- {error}')
        return 1

    print('PASS — KAORI Object Storage Inventory Final Lock v1.2')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
