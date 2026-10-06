#!/usr/bin/env python3
"""Fail closed on Object Storage Inventory release-surface drift."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = (
    'app/storage/object_storage/inventory/routes.py',
    'app/storage/object_storage/inventory/presentation.py',
    'app/templates/components/navigation/object_storage_menu.html',
    'app/templates/storage/object_storage/inventory/overview/index.html',
    'app/templates/storage/object_storage/inventory/components/_hero_blocked_context.html',
    'app/templates/storage/object_storage/inventory/components/_onboarding_banner.html',
    'app/templates/storage/object_storage/inventory/components/_snapshot_context.html',
    'migrations/versions/20260814_object_storage_rbac_split.py',
    'app/templates/storage/object_storage/inventory/systems/partials/_snapshot_boundary.html',
    'app/templates/storage/object_storage/inventory/buckets/partials/_snapshot_boundary.html',
    'app/templates/storage/object_storage/inventory/systems/index.html',
    'app/templates/storage/object_storage/inventory/buckets/index.html',
    'app/templates/storage/object_storage/inventory/systems/partials/_table_content.html',
    'app/templates/storage/object_storage/inventory/buckets/partials/_table_content.html',
    'app/templates/storage/object_storage/inventory/systems/partials/_system_detail_content.html',
    'app/templates/storage/object_storage/inventory/buckets/partials/_bucket_detail_content.html',
    'tests/contracts/storage/object_storage/inventory',
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

    routes = read('app/storage/object_storage/inventory/routes.py')
    menu = read('app/templates/components/navigation/object_storage_menu.html')
    overview = read('app/templates/storage/object_storage/inventory/overview/index.html')
    systems_workspace = read('app/templates/storage/object_storage/inventory/systems/partials/_page_workspace.html')
    buckets_workspace = read('app/templates/storage/object_storage/inventory/buckets/partials/_page_workspace.html')
    systems_snapshot = read('app/templates/storage/object_storage/inventory/systems/partials/_snapshot_boundary.html')
    buckets_snapshot = read('app/templates/storage/object_storage/inventory/buckets/partials/_snapshot_boundary.html')
    blocker = read('app/templates/storage/object_storage/inventory/components/_hero_blocked_context.html')
    onboarding = read('app/templates/storage/object_storage/inventory/components/_onboarding_banner.html')
    systems_index = read('app/templates/storage/object_storage/inventory/systems/index.html')
    buckets_index = read('app/templates/storage/object_storage/inventory/buckets/index.html')
    systems = read('app/templates/storage/object_storage/inventory/systems/partials/_table_content.html')
    buckets = read('app/templates/storage/object_storage/inventory/buckets/partials/_table_content.html')
    presentation = read('app/storage/object_storage/inventory/presentation.py')
    system_detail = read('app/templates/storage/object_storage/inventory/systems/partials/_system_detail_content.html')
    bucket_detail = read('app/templates/storage/object_storage/inventory/buckets/partials/_bucket_detail_content.html')

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

    if (
        'app.integrations.storage.object_storage.providers.minio' in routes
        or 'MinioClient' in routes
        or 'MinIOClient' in routes
    ):
        errors.append('Object Storage inventory routes must not query the live MinIO provider')

    for include in (
        'storage/object_storage/inventory/overview/partials/_snapshot_boundary.html',
        'storage/object_storage/inventory/overview/partials/_fleet_posture.html',
        'storage/object_storage/inventory/overview/partials/_summary_cards.html',
    ):
        if include not in overview:
            errors.append(f'Object Storage Overview composition missing: {include}')

    for token in (
        'overview.setup.is_blocked',
        'storage/object_storage/inventory/components/_onboarding_banner.html',
    ):
        if token not in overview:
            errors.append(f'Object Storage setup-blocked Overview contract missing: {token}')

    for forbidden in (
        'resource_detail_modal.inventory_host(',
        '_systems_snapshot.html',
        'object-storage-inventory-summary-content',
    ):
        if forbidden in overview:
            errors.append(f'Object Storage Overview must remain fleet-summary only: {forbidden}')

    for retired in (
        'app/templates/storage/object_storage/inventory/overview/partials/_systems_snapshot.html',
        'app/templates/storage/object_storage/inventory/overview/partials/_systems_snapshot_content.html',
    ):
        if (ROOT / retired).exists():
            errors.append(f'Object Storage Overview retired duplicate system surface still exists: {retired}')

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
        'app/templates/storage/object_storage/inventory/overview/partials/_hero.html',
        'app/templates/storage/object_storage/inventory/systems/partials/_hero.html',
        'app/templates/storage/object_storage/inventory/buckets/partials/_hero.html',
    ):
        hero_source = read(relative)
        if 'page_hero.aside_classes()' not in hero_source:
            errors.append(f'Object Storage blocked Hero must retain canonical aside geometry: {relative}')

    for token in (
        "url_for('integrations.storage')",
        'integrations.manage',
        'Register Your First Object Storage System',
    ):
        if token not in onboarding:
            errors.append(f'Object Storage onboarding ownership contract missing: {token}')

    for index_source, label, endpoint in (
        (systems_index, 'Systems', 'object_storage_inventory.system_details'),
        (buckets_index, 'Buckets & Containers', 'object_storage_inventory.bucket_details'),
    ):
        for token in (
            'resource_detail_modal.inventory_host(',
            endpoint,
            'Committed Object Storage Inventory snapshot · No live provider API query.',
        ):
            if token not in index_source:
                errors.append(f'Object Storage {label} modal-host contract missing: {token}')

    for source, label, endpoint in (
        (systems, 'Systems', 'object_storage_inventory.system_details'),
        (buckets, 'Buckets & Containers', 'object_storage_inventory.bucket_details'),
    ):
        for token in ('resource_detail_modal.detail_button(', endpoint):
            if token not in source:
                errors.append(f'Object Storage {label} detail-button contract missing: {token}')
        for retired in ('side_drawer.render(', 'x-teleport="body"', 'openDrawer', 'openDetail'):
            if retired in source:
                errors.append(f'Object Storage {label} retains retired inline detail host: {retired}')

    for token in ('Inventory Assets', 'Snapshot', 'Status', 'Details'):
        if token not in systems:
            errors.append(f'Object Storage Systems table contract missing: {token}')

    for token in ('Quota', 'Protection', 'Committed object-storage bucket and container inventory.'):
        if token not in buckets:
            errors.append(f'Buckets & Containers table contract missing: {token}')

    for name, source in (('System', system_detail), ('Bucket', bucket_detail)):
        for token in (
            'data-kaori-detail-density="unified-resource-sheet"',
            'data-kaori-inventory-detail="v10"',
            'data-kaori-inventory-detail-layout="unified-resource-sheet"',
            'detail.workspace_header(',
            'detail.inventory_title(',
            'detail.inspector_summary_strip(',
            'detail.resource_sheet()',
        ):
            if token not in source:
                errors.append(f'Object Storage {name} detail V10 contract missing: {token}')
        if 'detail.detail_card(' in source:
            errors.append(f'Object Storage {name} detail must not use legacy detail-card gallery geometry')

    for token in ('System Identity', 'Provider Connection', 'Inventory Snapshot'):
        if token not in system_detail:
            errors.append(f'Object Storage System resource-sheet section missing: {token}')

    for token in (
        "url_for('integrations.storage')",
        "job_key='object_storage.inventory.sync'",
        'Open Inventory Job',
    ):
        if token not in system_detail:
            errors.append(f'Object Storage System operational navigation contract missing: {token}')

    for token in (
        'Identity & Location',
        'Snapshot Context',
        'Capacity & Usage',
        'Data Protection',
        'Lifecycle & Access',
        'Provider Context',
        'provider_detail_sections',
    ):
        if token not in bucket_detail:
            errors.append(f'Object Storage Bucket resource-sheet section missing: {token}')

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
