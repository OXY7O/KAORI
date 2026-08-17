from pathlib import Path

ROOT = Path('.')


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_recommendation_and_catalog_filters_use_shared_two_desktop_rows() -> None:
    workspace = read('app/templates/intelligence/partials/_recommendations_workspace.html')
    filters = read('app/templates/intelligence/partials/_filters.html')
    catalog = read('app/templates/intelligence/partials/_catalog_workspace.html')

    assert '{% set filter_compact_two_rows = true %}' in workspace
    assert "'lg:grid-cols-12' if filter_compact_two_rows" in filters
    assert "'lg:col-span-4' if filter_compact_two_rows" in filters
    assert "'lg:col-span-2' if filter_compact_two_rows" in filters
    assert "'lg:col-span-3' if filter_compact_two_rows" in filters
    assert filters.index('>Signal Source</span>') < filters.index('>Severity</span>')
    assert '{% set filter_compact_two_rows = true %}' in catalog


def test_recommendation_summary_is_a_standalone_filter_aware_section_above_workspace() -> None:
    page = read('app/templates/intelligence/recommendations.html')
    results = read('app/templates/intelligence/partials/_recommendations_results.html')
    info = read('app/templates/intelligence/partials/_recommendation_workspace_info.html')
    routes = read('app/intelligence/routes.py')
    service = read('app/intelligence/service.py')

    assert page.index('_recommendation_workspace_info.html') < page.index("'Recommendation Workspace'")
    assert 'Recommendation Summary' in info
    assert 'intelligence_ui.section' in info
    assert 'id="recommendation-summary-section"' in info
    assert 'hx-swap-oob="outerHTML"' in info
    assert 'operational_callout.render' not in info
    assert 'Matching Findings' in info
    assert 'Kubernetes' in info
    assert 'Object Storage' in info
    assert 'Critical' in info
    assert 'Committed Evidence' in info
    assert 'recommendation_summary_oob|default(false)' in results
    assert results.index('_recommendation_workspace_info.html') < results.index('_recommendation_records.html')
    assert 'recommendation_summary_oob=True' in routes
    assert "'result_context':" in service
    assert "'matching_items': total_items" in service
    assert "'source_items': len(source_items)" in service
    assert "'active_filters': active_filter_count" in service
    assert "'kubernetes_items': sum(1 for item in filtered if item.get('domain') == 'kubernetes')" in service
    assert "'object_storage_items': sum(1 for item in filtered if item.get('domain') == 'object_storage')" in service
    assert "'critical_items': sum(1 for item in filtered if item.get('severity') == 'critical')" in service
    assert "'warning_items': sum(1 for item in filtered if item.get('severity') == 'warning')" in service


def test_recommendations_remain_committed_evidence_read_side_and_governed_action_boundary() -> None:
    service = read('app/intelligence/service.py')
    object_storage = read('app/intelligence/object_storage_recommendations.py')
    records = read('app/templates/intelligence/partials/_recommendation_records.html')
    detail = read('app/templates/intelligence/partials/_recommendation_detail_content.html')

    forbidden = (
        'MetricsConsumer(',
        'MinioClient(',
        'requests.get(',
        'requests.post(',
        'httpx.',
        'kubernetes.client',
    )
    for token in forbidden:
        assert token not in service
        assert token not in object_storage

    assert 'resource_detail_modal.detail_button' in records
    assert 'automation_control.' not in records
    assert 'automation_control.' not in detail
    assert 'Validate Live State' in detail
    assert 'Apply Remediation' in detail
    assert 'Verify & Close' in detail


def test_recommendation_workspace_keeps_htmx_filter_and_pagination_ownership() -> None:
    filters = read('app/templates/intelligence/partials/_filters.html')
    results = read('app/templates/intelligence/partials/_recommendations_results.html')
    routes = read('app/intelligence/routes.py')

    assert 'hx-target="{{ resolved_results_target }}"' in filters
    assert 'hx-push-url="true"' in filters
    assert 'hx-sync="{{ resolved_results_target }}:replace"' in filters
    assert "target='#recommendations-results-content'" in results
    assert "target == 'recommendations-results-content'" in routes
    assert "@permission_required('intelligence.view')" in routes


def test_recommendation_filters_disable_browser_autofill_state_restoration() -> None:
    filters = read('app/templates/intelligence/partials/_filters.html')

    assert 'autocomplete="off"' in filters
    assert filters.count('autocomplete="off"') >= 8
