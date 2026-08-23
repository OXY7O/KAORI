import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_inventory_table_grammar_owns_primary_data_surface_hierarchy() -> None:
    primitives = read('app/templates/components/table_primitives.html')
    assert 'text-base font-semibold text-content-primary' in primitives
    assert 'mt-1 text-sm leading-6 text-content-secondary' in primitives
    assert 'mb-1.5 block text-xs font-semibold text-content-secondary' in primitives
    assert 'truncate text-sm font-semibold text-content-primary' in primitives
    assert 'mt-0.5 truncate text-xs text-content-muted' in primitives


def test_intelligence_primary_sections_match_inventory_hierarchy() -> None:
    workspace = read('app/templates/intelligence/components/_workspace.html')
    assert 'Primary section titles use text-base / semibold / leading-6.' in workspace
    assert '<h2 class="text-base font-semibold leading-6 text-content-primary">{{ title }}</h2>' in workspace
    assert 'max-w-4xl text-sm leading-6 text-content-secondary' in workspace
    assert 'text-2xl font-semibold leading-7 tracking-tight text-content-primary' in workspace
    # Nested record hierarchy intentionally remains one level smaller.
    assert '<h3 class="break-words text-sm font-semibold leading-5 text-content-primary' in workspace
    assert 'break-words text-xs leading-5 text-content-muted' in workspace


def test_shared_context_and_operation_surfaces_use_same_primary_scale() -> None:
    summary = read('app/templates/components/workspace_summary_card.html')
    context = read('app/templates/components/page_context_card.html')
    operations = read('app/templates/components/kubernetes_operation_ui.html')
    integrations = read('app/templates/integrations/components/_workspace.html')

    assert 'text-base font-semibold leading-6 text-content-primary' in summary
    assert 'text-sm leading-6 text-content-secondary' in summary
    assert 'text-base font-semibold leading-6 text-content-primary' in context
    assert 'text-sm leading-6 text-content-secondary' in context
    assert 'text-base font-semibold leading-6 text-content-primary' in operations
    assert 'text-sm leading-6 text-content-secondary' in operations
    assert 'mb-1.5 block text-xs font-semibold text-content-secondary' in integrations


def test_analytics_primary_workspace_titles_do_not_exceed_inventory_section_scale() -> None:
    analysis = read('app/templates/analytics/components/_analysis_surfaces.html')
    workspace = read('app/templates/kubernetes/analytics/components/_analysis_workspace.html')
    assert 'text-base font-semibold leading-6 text-content-primary' in analysis
    assert 'mt-1 text-sm leading-6 text-content-secondary' in analysis
    assert 'table_ui.block_title_classes()' in workspace

    for directory in (
        ROOT / 'app/templates/kubernetes/analytics',
        ROOT / 'app/templates/storage/object_storage/analytics',
    ):
        for template in directory.rglob('*.html'):
            if template.name == '_record_detail_modal.html':
                continue
            source = template.read_text(encoding='utf-8')
            assert not re.search(r'<h2\b[^>]*class="[^"]*\btext-lg\b', source), template.relative_to(ROOT)


def test_intelligence_operational_context_and_queue_share_primary_heading_scale() -> None:
    workspace = read('app/templates/intelligence/partials/_alert_intelligence_workspace.html')
    active = read('app/templates/intelligence/partials/_alert_ops_active.html')
    automation = read('app/templates/intelligence/automation_control.html')

    assert '<h3 class="{{ table_ui.block_title_classes() }}">Operational Context</h3>' in workspace
    assert '<h3 class="{{ table_ui.block_title_classes() }}">Active Alert Triage</h3>' in active
    assert '<h3 class="{{ table_ui.block_title_classes() }}">Active Alert Queue</h3>' in active
    assert '<h2 class="{{ table_ui.block_title_classes() }}">Automation Control Workspace</h2>' in automation
    assert '<h3 class="{{ table_ui.block_title_classes() }}">{{ payload.active_workspace.label }}</h3>' in automation


def test_all_intelligence_primary_surfaces_keep_canonical_title_and_description_scale() -> None:
    table_primitives = read('app/templates/components/table_primitives.html')
    assert 'text-base font-semibold text-content-primary' in table_primitives
    assert 'mt-1 text-sm leading-6 text-content-secondary' in table_primitives

    catalog_summary = read('app/templates/intelligence/partials/_catalog_summary.html')
    assert "'Rule Catalog Summary'" in catalog_summary
    assert 'intelligence_ui.section(' in catalog_summary
    assert (
        'Review the current catalog scope before scanning definitions, evaluator readiness, and imported-signal coverage.'
        in catalog_summary
    )

    recommendation_summary = read('app/templates/intelligence/partials/_recommendation_workspace_info.html')
    alert_summary = read('app/templates/intelligence/partials/_alert_intelligence_summary.html')
    automation = read('app/templates/intelligence/automation_control.html')
    overview = read('app/templates/intelligence/overview.html')
    rule_catalog = read('app/templates/intelligence/rule_catalog.html')

    assert "'Recommendation Summary'" in recommendation_summary
    assert "'Alert Operations Summary'" in alert_summary
    assert '<h2 class="{{ table_ui.block_title_classes() }}">Automation Control Workspace</h2>' in automation
    assert "'Intelligence Posture'" in overview
    assert "'Intelligence Workspaces'" in overview
    assert "'Rule Definitions'" in rule_catalog
