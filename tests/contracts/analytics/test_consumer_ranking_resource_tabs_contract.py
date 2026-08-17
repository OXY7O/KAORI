from pathlib import Path


def test_consumer_rankings_are_separated_by_resource_tabs():
    template = Path('app/templates/kubernetes/analytics/top_consumers/partials/_top_consumers_section.html').read_text()
    for label in ["('cpu', 'CPU'", "('memory', 'Memory'", "('pvc', 'PVC'", "('pods', 'Pods'"]:
        assert label in template
    assert 'xl:grid-cols-2' not in template
    assert 'data-analytics-update-query="false"' in template


def test_nested_analytics_tabs_only_control_their_owner():
    script = Path('app/static/js/analytics/controls.js').read_text()
    assert "button.closest('[data-analytics-tabset]') === tabset" in script
    assert "panel.closest('[data-analytics-tabset]') === tabset" in script
    assert "tabset.dataset.analyticsUpdateQuery !== 'false'" in script
