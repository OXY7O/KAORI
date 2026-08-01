from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text()


def test_recommendations_filters_refresh_only_results_without_apply_button():
    filters = read('app/templates/intelligence/partials/_filters.html')
    assert 'hx-get=' in filters
    assert 'hx-target="#recommendations-results-content"' in filters
    assert 'hx-swap="innerHTML show:none focus-scroll:false"' in filters
    assert 'hx-sync="#recommendations-results-content:replace"' in filters
    assert 'hx-indicator="#recommendations-loading-bar"' in filters
    assert 'input changed delay:350ms' in filters
    assert 'change from:select' in filters
    assert 'Apply Filters' not in filters
    assert 'Reset' in filters


def test_recommendations_use_modal_details_not_inline_expandables():
    records = read('app/templates/intelligence/partials/_recommendation_records.html')
    page = read('app/templates/intelligence/recommendations.html')
    routes = read('app/intelligence/routes.py')
    assert 'resource_detail_modal.detail_button' in records
    assert '<details' not in records
    assert 'resource_detail_modal.host(' in page
    assert "def recommendation_details(" in routes
    assert "_recommendation_detail_content.html" in routes


def test_recommendations_pagination_matches_kaori_contract():
    pagination = read('app/templates/intelligence/components/_pagination.html')
    service = read('app/intelligence/service.py')
    assert 'Showing <span' in pagination
    assert '>Rows</label>' in pagination
    assert pagination.index('Showing <span') < pagination.index('>Rows</label>')
    assert 'data-kaori-auto-submit' in pagination
    assert 'innerHTML show:none focus-scroll:false' in pagination
    assert '>Apply</button>' not in pagination
    assert "'start_item': start_item" in service
    assert "'end_item': end_item" in service


def test_recommendations_workspace_has_standard_header_loading_bar():
    page = read('app/templates/intelligence/recommendations.html')
    workspace = read('app/templates/intelligence/components/_workspace.html')
    assert "indicator_id='recommendations-loading-bar'" in page
    assert 'loading_bar.render(indicator_id' in workspace
    assert 'basis-full' not in workspace
    assert workspace.index('sm:items-start sm:justify-between') < workspace.index('loading_bar.render(indicator_id')


def test_recommendations_route_owns_results_only_htmx_response():
    routes = read('app/intelligence/routes.py')
    results = read('app/templates/intelligence/partials/_recommendations_results.html')
    workspace = read('app/templates/intelligence/partials/_recommendations_workspace.html')
    assert "request.headers.get('HX-Target')" in routes
    assert "target == 'recommendations-results-content'" in routes
    assert "_recommendations_results.html" in routes
    assert 'id="recommendations-results-content"' in workspace
    assert '_recommendation_records.html' in results
