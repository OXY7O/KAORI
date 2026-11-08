from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding='utf-8')


def test_both_intelligence_filter_forms_keep_rows_during_results_only_htmx_swap() -> None:
    filters = read('app/templates/intelligence/partials/_filters.html')
    catalog = read('app/templates/intelligence/partials/_catalog_results.html')
    recommendations = read('app/templates/intelligence/partials/_recommendations_results.html')
    assert 'id="{{ resolved_scope }}-filter-page-size"' in filters
    assert 'id="catalog-filter-page-size"' in catalog
    assert 'id="recommendation-filter-page-size"' in recommendations
    assert 'hx-swap-oob="outerHTML"' in catalog
    assert 'hx-swap-oob="outerHTML"' in recommendations
    assert 'value="{{ payload.pagination.per_page }}"' in catalog
    assert 'value="{{ payload.pagination.per_page }}"' in recommendations


def test_only_available_rule_offers_escalation_form() -> None:
    detail = read('app/templates/intelligence/partials/_catalog_detail_content.html')
    alerting = read('app/intelligence/recommendation_alerting.py')
    assert "{% if item.status != 'available' %}" in detail
    assert "{% elif current_user.has_permission('intelligence.decisions.create') %}" in detail
    assert 'role="status"' in detail
    assert "if str(rule.get('status') or '') != 'available':" in alerting
