#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Reviewed filter surfaces that must consume shared full-width geometry directly
# or through the canonical server-backed registry filter macro.
STANDARD_CONSUMERS = (
    'app/templates/access/activity_audit/partials/_activity_table_card.html',
    'app/templates/access/identity_providers/partials/_registry.html',
    'app/templates/access/permissions/partials/_coverage.html',
    'app/templates/access/permissions/partials/_registry.html',
    'app/templates/access/roles/partials/_registry.html',
    'app/templates/access/users/partials/_filters.html',
    'app/templates/components/integration_coverage.html',
    'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_capability_registry.html',
    'app/templates/integrations/observability/metrics_source/partials/_capability_registry.html',
    'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_inventory_card.html',
    'app/templates/integrations/observability/metrics_source/partials/_instance_inventory.html',
    (
        'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/'
        'partials/_capability_registry.html'
    ),
    (
        'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/'
        'partials/_integration_coverage.html'
    ),
    'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_registry.html',
    'app/templates/integrations/partials/_domain_workspace.html',
    'app/templates/integrations/partials/_runtime_history.html',
    'app/templates/integrations/partials/_runtime_overview.html',
    'app/templates/integrations/storage/object_storage/providers/minio/partials/_capability_registry.html',
    'app/templates/integrations/storage/object_storage/providers/minio/partials/_coverage.html',
    'app/templates/integrations/storage/object_storage/providers/minio/partials/_registry.html',
    'app/templates/intelligence/partials/_alert_intelligence_alerts.html',
    'app/templates/intelligence/partials/_alert_intelligence_workspace.html',
    'app/templates/intelligence/partials/_filters.html',
    'app/templates/kubernetes/analytics/components/_record_filter_bar.html',
    'app/templates/kubernetes/analytics/alerts/partials/_table_filters.html',
    'app/templates/kubernetes/governance/tls_certificates/partials/_filters.html',
    'app/templates/kubernetes/inventory/configuration/partials/_table_card.html',
    'app/templates/kubernetes/inventory/ingresses/partials/_table_card.html',
    'app/templates/kubernetes/inventory/namespaces/partials/_table_card.html',
    'app/templates/kubernetes/inventory/nodes/partials/_table_card.html',
    'app/templates/kubernetes/inventory/pods/partials/_table_card.html',
    'app/templates/kubernetes/inventory/services/partials/_table_card.html',
    'app/templates/kubernetes/inventory/storage/partials/_table_card.html',
    'app/templates/kubernetes/inventory/topology/partials/_workspace.html',
    'app/templates/kubernetes/inventory/workloads/partials/_table_card.html',
    'app/templates/kubernetes/operations/secrets/_bulk_filters.html',
    'app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_section.html',
    'app/templates/platform_operations/data_lifecycle/partials/_history.html',
    'app/templates/platform_operations/notifications/partials/_center_page_content.html',
    'app/templates/platform_operations/jobs/executions/partials/_registry.html',
    'app/templates/reports/generated/index.html',
    'app/templates/reports/report_templates/index.html',
    'app/templates/reports/schedules/index.html',
    'app/templates/storage/object_storage/analytics/partials/_controls.html',
    'app/templates/storage/object_storage/inventory/buckets/partials/_table_card.html',
    'app/templates/storage/object_storage/inventory/systems/partials/_table_card.html',
)


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    primitives = read('app/templates/components/table_primitives.html')
    table = read('app/templates/components/table.html')
    registry = read('app/templates/components/table_registry.html')
    standard = read('docs/design/components/TABLE_AND_LABEL.md')
    engineering = read('docs/standards/KAORI_ENGINEERING_STANDARD_V1.md')
    quality_gate = read('scripts/quality_gate.sh')

    for token in (
        'macro filter_layout_classes',
        'flex w-full flex-wrap items-end gap-3',
        '[&>label]:flex-1',
        '[&>label]:basis-full',
        '[&>div]:flex-1',
        '[&>div]:basis-full',
        'sm:[&>label]:basis-56',
        'sm:[&>div]:basis-56',
    ):
        require(token in primitives, f'filter primitive missing canonical token: {token}', errors)

    require(
        'table_primitives.filter_layout_classes()' in table,
        'components/table.html must expose the shared filter layout primitive.',
        errors,
    )
    require(
        'class="{{ table_primitives.filter_layout_classes() }} {{ classes }}"' in registry,
        'registry_ui.filter_form() must own canonical full-width filter geometry.',
        errors,
    )

    for relative in STANDARD_CONSUMERS:
        source = read(relative)
        require(
            'filter_layout_classes()' in source
            or 'registry_ui.filter_form(' in source
            or 'table_registry.filter_form(' in source
            or 'filter_bar_classes()' in source,
            f'{relative} must use canonical full-width filter geometry.',
            errors,
        )

    # The Provider Registry screenshot that initiated this standard had two
    # visible fields inside a three-column desktop grid. Fixed-grid ownership
    # must not return here even when optional filters are hidden.
    domain_workspace = read('app/templates/integrations/partials/_domain_workspace.html')
    require(
        'xl:grid-cols-3' not in domain_workspace,
        'Integration domain registry must not reserve an orphan third filter column.',
        errors,
    )

    integration_workspace = read('app/templates/integrations/components/_workspace.html')
    require(
        'macro filter_grid_classes' not in integration_workspace,
        'Integration workspace must not expose the retired fixed-grid filter helper.',
        errors,
    )

    integration_coverage = read('app/templates/components/integration_coverage.html')
    require(
        'xl:grid-cols-12' not in integration_coverage and 'xl:col-span-' not in integration_coverage,
        'Integration Coverage filters must not retain fixed desktop grid spans.',
        errors,
    )

    namespace_policy = read('app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_section.html')
    require(
        'md:grid-cols-[minmax(0,1fr)_18rem]' not in namespace_policy,
        'Namespace Policy filters must share remaining row width instead of fixing the select to 18rem.',
        errors,
    )

    alerts_filters = read('app/templates/kubernetes/analytics/alerts/partials/_table_filters.html')
    require(
        'lg:grid-cols-4' not in alerts_filters and 'lg:grid-cols-3' not in alerts_filters,
        'Kubernetes Alerts table filters must not use fixed desktop column counts.',
        errors,
    )

    intelligence_filters = ''.join(
        read(relative)
        for relative in (
            'app/templates/intelligence/partials/_filters.html',
            'app/templates/intelligence/partials/_alert_intelligence_alerts.html',
            'app/templates/intelligence/partials/_alert_intelligence_workspace.html',
        )
    )
    require(
        'lg:col-span-' not in intelligence_filters,
        'Intelligence filter fields must not retain grid-only column-span residue.',
        errors,
    )

    notification_center = read('app/templates/platform_operations/notifications/partials/_center_page_content.html')
    require(
        'lg:w-48' not in notification_center and 'lg:min-w-[20rem]' not in notification_center,
        'Notification Center filters must share the full row instead of reserving fixed desktop widths.',
        errors,
    )

    # Action-aware exception: fields fill the remaining space while actions
    # retain content width. This is allowed by the standard and avoids giant
    # Apply/Clear buttons.
    bucket_filter = read('app/templates/storage/object_storage/analytics/partials/_bucket_table.html')
    for token in (
        'class="block min-w-0 flex-1" for="object-storage-bucket-search"',
        'class="flex flex-none flex-wrap items-center gap-2"',
    ):
        require(
            token in bucket_filter,
            f'Object Storage bucket filter missing action-aware fill token: {token}',
            errors,
        )
    require(
        'sm:max-w-md' not in bucket_filter,
        'Object Storage bucket search must not float at a capped desktop width.',
        errors,
    )

    for token in (
        'full-width and content-aware',
        'orphan empty column',
        'explicit action groups may remain content-width',
        'filters never use `max-w-*`',
    ):
        require(token in standard, f'Table/filter design standard missing rule: {token}', errors)

    require(
        'canonical filter rows use the shared full-width wrapping geometry' in engineering,
        'Engineering Standard must register the full-width filter-layout rule.',
        errors,
    )
    require(
        'python scripts/verify_filter_layout_standard.py' in quality_gate,
        'quality_gate.sh must run the canonical filter-layout verifier.',
        errors,
    )

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    print(
        f'KAORI Filter Layout standard passed: {len(STANDARD_CONSUMERS)} reviewed filter surfaces '
        'use full-width wrapping ownership and action-aware exceptions remain bounded.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
