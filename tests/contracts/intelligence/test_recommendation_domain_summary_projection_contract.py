"""Source-qualified, filter-scoped Recommendations domain summary metrics."""

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def domain_metrics(findings: list[dict[str, str]]) -> list[dict[str, str | int]]:
    presentation = runpy.run_path(str(ROOT / 'app/intelligence/finding_presentation.py'))
    options = runpy.run_path(str(ROOT / 'app/intelligence/rule_presentation.py'))['DOMAIN_OPTIONS']
    labels = {option['value']: option['label'] for option in options if option['value']}
    return presentation['recommendation_summary_domain_metrics'](findings, labels)


def test_baseline_remains_five_indicators_without_additional_domain_findings() -> None:
    metrics = domain_metrics(
        [
            {'domain': 'kubernetes'},
            {'domain': 'kubernetes'},
            {'domain': 'registry'},
            {'domain': 'object_storage'},
        ]
    )
    assert [metric['key'] for metric in metrics] == ['kubernetes', 'object_storage', 'registry']
    assert [metric['count'] for metric in metrics] == [2, 1, 1]
    assert len(metrics) + 2 == 5

    empty = domain_metrics([])
    assert [metric['count'] for metric in empty] == [0, 0, 0]
    assert 'secrets_pki' not in [metric['key'] for metric in empty]
    assert 'server' not in [metric['key'] for metric in empty]
    assert 'hci' not in [metric['key'] for metric in empty]


def test_authorized_extra_domain_finding_adds_one_indicator_without_invented_counts() -> None:
    metrics = domain_metrics(
        [
            {'domain': 'kubernetes'},
            {'domain': 'secrets_pki'},
            {'domain': 'secrets_pki'},
            {'domain': 'registry'},
        ]
    )
    assert len(metrics) + 2 == 6
    assert [metric['key'] for metric in metrics] == [
        'kubernetes',
        'object_storage',
        'registry',
        'secrets_pki',
    ]
    assert [metric['count'] for metric in metrics] == [1, 0, 1, 2]
    assert metrics[-1]['label'] == 'Secrets & PKI'
    assert metrics[-1]['icon'] == 'shield-check'
    assert 'Committed Secrets & PKI finding(s)' == metrics[-1]['description']


def test_filter_and_authority_boundaries_hide_unmatched_or_unregistered_domains() -> None:
    # The helper receives only filtered, server-authorized matching findings.
    all_findings = [
        {'domain': 'secrets_pki'},
        {'domain': 'kubernetes'},
        {'domain': 'not_an_approved_domain'},
    ]
    filtered = [item for item in all_findings if item['domain'] == 'kubernetes']
    assert [metric['key'] for metric in domain_metrics(filtered)] == [
        'kubernetes',
        'object_storage',
        'registry',
    ]
    assert 'not_an_approved_domain' not in [metric['key'] for metric in domain_metrics(all_findings)]


def test_future_admitted_domains_expand_without_integrations_inventory_projection() -> None:
    metrics = domain_metrics([{'domain': 'server'}, {'domain': 'hci'}, {'domain': 'hci'}])
    assert [metric['key'] for metric in metrics] == [
        'kubernetes',
        'object_storage',
        'registry',
        'server',
        'hci',
    ]
    assert [metric['count'] for metric in metrics][-2:] == [1, 2]
    assert [metric['label'] for metric in metrics][-2:] == ['Server', 'HCI']


def test_summary_binding_stays_filtered_and_permission_constrained() -> None:
    service = source('app/intelligence/service.py')
    partial = source('app/templates/intelligence/partials/_recommendation_workspace_info.html')
    page = source('app/templates/intelligence/recommendations.html')
    assert 'recommendation_summary_domain_metrics(' in service
    assert '            filtered,' in service
    assert "if page_mode != 'catalog'" in service
    assert 'and _can_view_secrets_pki_intelligence()' in service
    assert "current_user.has_permission('secrets_pki.view')" in service
    assert "current_user.has_permission('intelligence.view')" in service
    assert "'domain_metrics': domain_metrics" in service
    assert 'indicator_count = domain_metrics|length + 2' in partial
    assert "metadata_label(indicator_count ~ ' Indicators'" in partial
    assert 'for domain_metric in domain_metrics' in partial
    assert 'data-recommendation-summary-metrics' in partial
    assert "'xl:grid-cols-5' if indicator_count == 5" in partial
    assert "'xl:grid-cols-6' if indicator_count == 6" in partial
    assert 'Committed Evidence only.' in partial
    assert 'Review committed operational guidance across supported domains.' in page
    assert 'hx-swap-oob="outerHTML"' in partial
