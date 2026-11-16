from pathlib import Path

from jinja2 import Environment


def read(path: str) -> str:
    return Path(path).read_text(encoding='utf-8')


def test_recommendation_header_markup_is_valid_jinja_and_reuses_shared_components() -> None:
    page = read('app/templates/intelligence/recommendations.html')
    summary = read('app/templates/intelligence/partials/_recommendation_workspace_info.html')
    actions = read('app/templates/intelligence/partials/_recommendation_workspace_header_actions.html')
    results = read('app/templates/intelligence/partials/_recommendations_results.html')
    workspace = read('app/templates/intelligence/components/_workspace.html')

    for template in (page, summary, actions, results, workspace):
        Environment().parse(template)

    assert 'components/section_intro.html' in page
    assert 'components/info_tip.html' in page
    assert 'components/table_label.html' in summary
    assert "table_label.metadata_label(indicator_count ~ ' Indicators', icon='layout-dashboard')" in summary
    assert 'indicator_count = domain_metrics|length + 2' in summary
    assert 'title_extra=summary_title_label' in summary
    assert 'title_extra=workspace_title_extra' in page
    assert "table_label.metadata_label('Filtered Review', 'list-filter')" in page
    assert 'header_actions=workspace_header_actions' in page
    assert 'header_actions=None' in workspace
    assert '{% if header_actions %}{{ header_actions }}{% endif %}' in workspace


def test_recommendations_review_intro_metadata_label_and_single_guide() -> None:
    page = read('app/templates/intelligence/recommendations.html')
    summary_index = page.index('_recommendation_workspace_info.html')
    intro_index = page.index('section_intro.render(')
    workspace_index = page.index('intelligence_ui.section(')
    assert summary_index < intro_index < workspace_index
    assert "'Recommendation Review'" in page
    assert 'Review committed findings by scope, evidence, and priority' in page
    assert page.count("variant='guide'") == 1
    assert "metadata_label('Filtered Review', 'list-filter')" in page
    assert "'recommendation-workspace-guide'" in page
    assert "'recommendation-filters-guide'" not in page
    assert "'Recommendations Guide'" in page
    assert 'committed findings' in page
    assert 'updates the browser URL' in page


def test_recommendation_filter_reset_and_status_share_header_oob_owner() -> None:
    page = read('app/templates/intelligence/recommendations.html')
    actions = read('app/templates/intelligence/partials/_recommendation_workspace_header_actions.html')
    results = read('app/templates/intelligence/partials/_recommendations_results.html')
    route = read('app/intelligence/routes.py')

    assert '_recommendation_workspace_header_actions.html' in page
    assert 'payload.active_filter_count|default(0) > 0' in actions
    assert 'registry_ui.clear_filters_action(' in actions
    assert "table_ui.action_classes(size='header')" in actions
    assert "target='#recommendations-workspace-content'" in actions
    assert "sync='#recommendations-workspace-content:replace'" in actions
    assert "swap='outerHTML show:none focus-scroll:false'" in actions
    assert "push_url='true'" in actions
    assert 'hx-swap-oob="outerHTML"' in actions
    assert 'id="recommendation-workspace-header-actions"' in actions
    assert actions.index('clear_filters_action(') < actions.index('table_label.status_label(')
    assert 'payload.posture.label' in actions
    assert 'payload.posture.tone' in actions
    assert '_recommendation_workspace_header_actions.html' in results
    assert results.index('_recommendation_workspace_header_actions.html') < results.index(
        '_recommendation_records.html'
    )
    assert 'recommendation_summary_oob=True' in route


def test_recommendation_results_remove_redundant_strip_but_keep_records_and_pagination() -> None:
    results = read('app/templates/intelligence/partials/_recommendations_results.html')
    summary = read('app/templates/intelligence/partials/_recommendation_workspace_info.html')
    assert '<span class="text-xs font-semibold text-content-secondary">Recommendations</span>' not in results
    assert 'table_label.result_count(' not in results
    assert 'clear_filters_action' not in results
    assert "include 'intelligence/partials/_recommendation_records.html'" in results
    assert 'intelligence_pagination.render(' in results
    assert 'payload.result_context.matching_items' in summary
    assert "'Matching Findings'" in summary
    assert 'payload.pagination.total_items' in summary
