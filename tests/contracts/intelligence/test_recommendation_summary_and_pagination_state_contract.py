from pathlib import Path


def test_recommendation_list_uses_service_owned_compact_summary():
    service = Path('app/intelligence/service.py').read_text()
    records = Path('app/templates/intelligence/partials/_recommendation_records.html').read_text()
    assert 'def _compact_recommendation_summary' in service
    assert "for marker in (' Examples:', ' Example:', ' Examples include:')" in service
    assert "item['list_summary'] = _compact_recommendation_summary" in service
    assert 'item.list_summary|default(item.summary, true)' in records
    assert 'line-clamp-2' in records


def test_pagination_and_filters_have_separate_htmx_ownership():
    filters = Path('app/templates/intelligence/partials/_filters.html').read_text()
    pagination = Path('app/templates/intelligence/components/_pagination.html').read_text()
    route = Path('app/intelligence/routes.py').read_text()
    assert "filter_results_target|default('#recommendations-results-content')" in filters
    assert 'hx-target="{{ resolved_results_target }}"' in filters
    assert "filter_workspace_target|default('#recommendations-workspace-content')" in filters
    assert 'hx-target="{{ resolved_workspace_target }}"' in filters
    assert "target == 'recommendations-results-content'" in route
    assert "hx-sync=\"{{ target }}:replace\"" in pagination
    assert "hx_swap='innerHTML show:none focus-scroll:false'" in pagination
