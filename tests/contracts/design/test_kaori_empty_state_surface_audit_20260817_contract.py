from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_reviewed_product_surfaces_use_the_canonical_state_components() -> None:
    reviewed_empty_state_owners = (
        'app/templates/welcome/index.html',
        'app/templates/dashboards/kubernetes/partials/_alerts_summary.html',
        'app/templates/inventory/object_storage/systems/partials/_table_content.html',
        'app/templates/components/kubernetes_operation_ui.html',
        'app/templates/analytics/kubernetes/components/_evidence_record_list.html',
        'app/templates/analytics/object_storage/partials/_bucket_table.html',
        'app/templates/intelligence/components/_workspace.html',
        'app/templates/reports/generated/index.html',
        'app/templates/reports/report_templates/index.html',
        'app/templates/reports/schedules/index.html',
        'app/templates/integrations/partials/_runtime_history.html',
    )
    for relative in reviewed_empty_state_owners:
        assert 'components/states/_empty_state.html' in read(relative), relative

    overview = read('app/templates/platform_operations/overview/index.html')
    assert 'data-kaori-empty-state' not in overview
    assert 'No Data Available' not in overview

    reviewed_blocked_state_owners = (
        'app/templates/dashboards/kubernetes/partials/_forecast_risk.html',
        'app/templates/analytics/object_storage/partials/_alert_records.html',
        'app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_table_content.html',
    )
    for relative in reviewed_blocked_state_owners:
        assert 'components/states/_blocked_state.html' in read(relative), relative


def test_reviewed_registry_empty_rows_do_not_keep_page_local_visual_shells() -> None:
    templates = {
        'app/templates/integrations/storage/object_storage/providers/minio/partials/_capability_registry.html': 'No Capability Records Match the Current Filters',
        'app/templates/analytics/object_storage/partials/_alert_records.html': 'No Alert Records Match the Current Filters',
        'app/templates/analytics/object_storage/partials/_bucket_table.html': 'No Bucket Records Match the Current Filters',
        'app/templates/intelligence/partials/_alert_intelligence_records.html': 'No Alert Records Match the Current Filters',
        'app/templates/reports/generated/index.html': 'No Generated Reports Match the Current Filters',
        'app/templates/reports/report_templates/index.html': 'No Templates Match the Current Filters',
        'app/templates/reports/schedules/index.html': 'No Schedules Match the Current Filters',
        'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_capability_registry.html': 'No Capability Records Match the Current Filters',
        'app/templates/integrations/notification_channels/index.html': 'No Notification Channels Configured',
    }
    for relative, title in templates.items():
        source = read(relative)
        assert title in source, relative
        assert 'components/states/_empty_state.html' in source, relative

    intelligence = read('app/templates/intelligence/partials/_recommendation_records.html')
    assert "empty_state_label = 'No Results'" in intelligence
    assert 'rounded-xl border border-dashed border-outline-strong bg-surface-hover px-4 py-10' not in intelligence


def test_adapter_macros_delegate_visual_ownership_to_shared_empty_state() -> None:
    intelligence = read('app/templates/intelligence/components/_workspace.html')
    analytics = read('app/templates/analytics/kubernetes/components/_evidence_record_list.html')
    operations = read('app/templates/components/kubernetes_operation_ui.html')

    for source in (intelligence, analytics, operations):
        assert "include 'components/states/_empty_state.html'" in source

    assert (
        'rounded-lg border border-dashed border-outline-strong bg-surface-hover px-4 py-9 text-center'
        not in intelligence
    )
    assert 'flex min-h-[190px] flex-col items-center justify-center bg-surface-card' not in analytics
    assert "label='Selection Required'" in operations


def test_web_empty_state_standard_does_not_claim_report_pdf_layout_ownership() -> None:
    guide = read('docs/design/components/empty-state.md')
    assert 'web application surfaces' in guide
    assert 'PDF and exported artifacts keep their report-publication layout contract' in guide
    assert 'Topology canvas selection placeholders remain canvas-owned interaction states' in guide


def test_reviewed_web_tables_do_not_reintroduce_plain_text_empty_rows() -> None:
    roots = (
        'app/templates/dashboards/kubernetes',
        'app/templates/inventory/kubernetes',
        'app/templates/kubernetes_operations',
        'app/templates/inventory/object_storage',
        'app/templates/integrations/storage/object_storage/providers/minio',
        'app/templates/analytics/kubernetes',
        'app/templates/analytics/object_storage',
        'app/templates/intelligence',
        'app/templates/reports',
        'app/templates/platform_operations',
        'app/templates/integrations',
    )
    approved_adapters = {
        'app/templates/intelligence/partials/_catalog_records.html',
    }
    violations: list[str] = []
    for root in roots:
        for path in (ROOT / root).rglob('*.html'):
            relative = path.relative_to(ROOT).as_posix()
            if '/pdf/' in relative or relative in approved_adapters:
                continue
            source = path.read_text(encoding='utf-8')
            if '<td' not in source or 'colspan' not in source:
                continue
            has_plain_zero_copy = any(
                token in source
                for token in (
                    'text-center text-sm text-content-muted">No ',
                    'py-10 text-center">\n                            <p class="text-sm font-semibold',
                    'py-12 text-center text-sm text-content-muted">No ',
                )
            )
            if (
                has_plain_zero_copy
                and 'components/states/_empty_state.html' not in source
                and 'components/states/_blocked_state.html' not in source
            ):
                violations.append(relative)

    assert violations == []
