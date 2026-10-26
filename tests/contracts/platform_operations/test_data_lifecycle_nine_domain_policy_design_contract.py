"""Nine-domain Retention Policies design-system and ownership contract (#2961).

This is a structural regression layer. Full browser Visual QA, source RBAC,
PostgreSQL/Celery/Archive Storage execution and human acceptance are separate.
"""

from pathlib import Path

import pytest
from jinja2 import Environment

from app.platform_operations.data_lifecycle.retention.domains import DOMAIN_FACTORIES
from app.platform_operations.data_lifecycle.retention.presentation import (
    _domain_coverage,
    _domain_description,
    _domain_label,
)

ROOT = Path(__file__).resolve().parents[3]
INDEX = ROOT / 'app/templates/platform_operations/data_lifecycle/index.html'
WORKSPACE = ROOT / 'app/templates/platform_operations/data_lifecycle/partials/_domain_workspace.html'

EXPECTED_COVERAGE_COUNTS = {
    'operational_activity': 3,
    'job_execution': 1,
    'runtime_observation': 4,
    'analytics_snapshot': 3,
    'generated_report': 3,
    'alert_incident': 4,
    'tenant_audit_evidence': 2,
    'notification_delivery': 2,
    'audit_event': 2,
}


@pytest.mark.parametrize('domain_name', sorted(EXPECTED_COVERAGE_COUNTS))
def test_all_registered_policies_reuse_normalized_source_owned_coverage(domain_name: str) -> None:
    assert set(DOMAIN_FACTORIES) == set(EXPECTED_COVERAGE_COUNTS)
    coverage = _domain_coverage(domain_name)
    assert len(coverage) == EXPECTED_COVERAGE_COUNTS[domain_name]
    assert len({item['label'] for item in coverage}) == len(coverage)
    for item in coverage:
        assert item['icon'].strip()
        assert item['label'].strip()
        assert item['description'].strip()
    assert _domain_label(domain_name).strip()
    assert _domain_description(domain_name).strip()


def test_execution_boundary_is_canonical_title_adjacent_guide_not_question_mark() -> None:
    index = INDEX.read_text(encoding='utf-8')
    Environment().parse(index)
    footer = index.split('<footer class="flex flex-wrap items-center', 1)[1].split('</footer>', 1)[0]
    guide = footer.split("info_tip.render('data-lifecycle-execution-boundary',", 1)[1].split('}}', 1)[0]
    assert "'Execution Boundary'" in guide
    assert "variant='guide'" in guide
    assert "placement='right'" in guide
    assert footer.index('>Execution Boundary</span>') < footer.index('data-lifecycle-execution-boundary')
    assert "{% if current_user.has_permission('jobs.view') %}" in footer
    assert "url_for('jobs.executions')" in footer
    canonical = (ROOT / 'app/templates/components/info_tip.html').read_text(encoding='utf-8')
    assert "guide_variant = variant == 'guide' and not button_text" in canonical
    assert 'data-kaori-info-tip-variant' in canonical
    assert 'aria-expanded="false"' in canonical


def test_single_shared_policy_surface_has_no_new_domain_specific_card_designs() -> None:
    index = INDEX.read_text(encoding='utf-8')
    ui = WORKSPACE.read_text(encoding='utf-8')
    Environment().parse(index)
    Environment().parse(ui)
    assert index.count('platform_operations/data_lifecycle/partials/_domain_workspace.html') == 1
    assert '{% for domain in lifecycle.domains %}' in index
    assert 'x-ref="domainList"' in index
    assert 'xl:grid-cols-12 xl:items-stretch' in index
    assert 'xl:col-span-4' in index
    assert 'xl:col-span-8' in index

    assert 'class="{{ table_ui.block_classes() }} !border-outline-subtle !shadow-none"' in ui
    assert 'components/table_label.html' in ui
    assert 'components/loading_bar.html' in ui
    for section in (
        'Hot Retention',
        'Archive Retention',
        'Batch Size',
        'Lifecycle Coverage',
        'Storage Boundary',
        'Retention Boundary',
        'Execution Worker',
    ):
        assert section in ui
    assert '{% for item in lifecycle.coverage %}' in ui
    assert 'class="h-full rounded-lg border border-outline-subtle bg-surface-subtle p-3.5"' in ui
    assert '{% if lifecycle.coverage|length > 1 %}sm:grid-cols-2{% endif %}' in ui
    assert '{% if lifecycle.coverage|length == 3 %}xl:grid-cols-3{% endif %}' in ui
    assert "selected.name not in ('alert_incident', 'runtime_observation')" not in ui
    assert "selected.name in ('notification_delivery', 'audit_event')" in ui
    assert 'Source-owned records covered by manual, non-destructive archival.' in ui
    assert 'Records covered by this retention, archive, and cleanup policy.' in ui
    assert 'hx-indicator="#data-lifecycle-policy-loading"' in ui
    assert 'components/operation_feedback_oob.html' in ui


def test_buttons_share_permission_csrf_while_manual_domains_keep_correct_capability() -> None:
    ui = WORKSPACE.read_text(encoding='utf-8')
    assert "current_user.has_permission('platform_operations.manage_data_lifecycle')" in ui
    assert ui.count('name="csrf_token" value="{{ csrf_token() }}"') == 3
    assert "url_for('platform_operations.data_lifecycle.save_policy')" in ui
    assert "url_for('platform_operations.data_lifecycle.preview'" in ui
    assert 'name="mode" value="archive_only"' in ui
    assert 'name="mode" value="archive_and_cleanup"' in ui
    assert "{% if selected.name not in ('notification_delivery', 'audit_event') %}" in ui
    assert 'Manual Archive Only · No schedule' in ui
    assert "{% if selected.name not in ('notification_delivery', 'audit_event') %}" in ui
    assert '{% if execution_blocked %}disabled{% endif %}' in ui
    assert 'hx-disabled-elt="find button[type=\'submit\']"' in ui
    assert 'hx-target="#data-lifecycle-domain-workspace"' in ui
    assert 'hx-target="#data-lifecycle-page"' in ui
    assert "url_for('platform_operations.data_lifecycle.index', tab='storage')" in ui


def test_all_nine_policies_have_correct_card_count_driven_responsive_grid() -> None:
    ui = WORKSPACE.read_text(encoding='utf-8')
    start = ui.index('<div class="grid gap-3 p-4 ')
    end = ui.index('">', start)
    grid = Environment().from_string(ui[start : end + 2])
    for domain, count in EXPECTED_COVERAGE_COUNTS.items():
        rendered = grid.render(lifecycle={'coverage': [{}] * count})
        assert ('sm:grid-cols-2' in rendered) is (count > 1), domain
        assert ('xl:grid-cols-3' in rendered) is (count == 3), domain
    # One item takes full width; two remain side-by-side; all four-item
    # domains reuse the same 2 x 2 grid without a domain-name exception.
    assert "selected.name != 'alert_incident'" not in ui
    assert "selected.name not in ('alert_incident', 'runtime_observation')" not in ui
