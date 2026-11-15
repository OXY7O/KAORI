"""Concise Recommendations table copy retains complete evidence in Review."""

import runpy
from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]


def _presentation() -> dict:
    return runpy.run_path(str(ROOT / 'app/intelligence/finding_presentation.py'))


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding='utf-8')


def test_tenant_quota_summary_prefers_semantic_state_over_technical_identity() -> None:
    presentation = _presentation()
    title = presentation['recommendation_table_title']
    scope = presentation['recommendation_table_scope_title']
    finding = {
        'rule_key': 'kubernetes.tenant.capacity.overcommitted',
        'title': (
            'Tenant allocation posture for '
            '@tenant:kaori-capsule-uat-01:resource-quotas: Overcommitted'
        ),
        'evidence': {
            'namespace': '@tenant:kaori-capsule-uat-01:resource-quotas',
            'capacity_state': 'overcommitted',
            'affected_count': 1,
        },
    }

    assert title(finding, limit=64) == 'Tenant allocation: Overcommitted'
    assert scope(finding['evidence']['namespace']) == 'Tenant resource quotas'
    assert '@tenant:kaori-capsule-uat-01:resource-quotas' in finding['title']
    assert finding['evidence']['namespace'].startswith('@tenant:')


def test_missing_tenant_state_does_not_invent_governance_conclusions() -> None:
    title = _presentation()['recommendation_table_title']
    finding = {
        'rule_key': 'kubernetes.tenant.capacity.overcommitted',
        'title': 'Tenant allocation posture for @tenant:a-long-name:resource-quotas',
        'evidence': {'namespace': '@tenant:a-long-name:resource-quotas'},
    }
    projected = title(finding, limit=64)
    assert projected != 'Tenant allocation: Overcommitted'
    assert len(projected) <= 65


def test_other_titles_and_scope_keys_are_bounded_without_mutating_source() -> None:
    presentation = _presentation()
    title = presentation['recommendation_table_title']
    scope = presentation['recommendation_table_scope_title']
    original = 'Artifact registry observations with extended evidence and approval qualifiers'
    finding = {'rule_key': 'registry.artifact.scan', 'title': original}
    projected = title(finding, limit=64)
    assert len(projected) <= 65
    assert projected.endswith('…')
    assert finding['title'] == original
    assert scope('capsule-system') == 'capsule-system'
    assert scope('x' * 60) == ('x' * 43) + '…'


def test_table_and_mobile_use_display_projection_with_original_full_tooltips() -> None:
    service = _read('app/intelligence/service.py')
    records = _read('app/templates/intelligence/partials/_recommendation_records.html')
    detail = _read('app/templates/intelligence/partials/_recommendation_detail_content.html')
    Environment().parse(records)

    assert "item['list_scope_title'] = recommendation_table_scope_title(scope_title)" in service
    assert "item['scope_title'] = scope_title" in service
    assert "item['list_title'] = recommendation_table_title(item, limit=64)" in service
    assert "item['list_summary'] = recommendation_table_summary(item, limit=64)" in service
    assert records.count('title="{{ item.title }}"') == 2
    assert records.count('item.list_scope_title|default(item.scope_title|') == 2
    assert records.count('title="{{ item.scope_title|default(\'Asset Scope\', true) }}"') == 2
    assert 'item.list_summary|default(item.summary, true)' in records
    assert 'item.signal_source_label' in records
    assert "resource_detail_modal.detail_button(item.rule_key" in records
    assert "data-kaori-recommendation-header-summary" in detail
    assert '{{ item.title }}' in detail
