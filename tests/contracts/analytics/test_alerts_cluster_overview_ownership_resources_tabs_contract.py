from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
ALERTS_ROOT = ROOT / 'app/templates/analytics/alerts'
INDEX = ALERTS_ROOT / 'index.html'
OVERVIEW = ALERTS_ROOT / 'partials/_cluster_signal_overview.html'
OWNERSHIP = ALERTS_ROOT / 'partials/_ownership_summary.html'
RECOMMENDATIONS = ALERTS_ROOT / 'partials/_recommendations.html'
RESOURCES = ALERTS_ROOT / 'partials/_operational_resources.html'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_alert_workspace_has_dedicated_ownership_readiness_and_resources_tabs() -> None:
    content = read(INDEX)

    assert "('ownership', 'Ownership & Runbook Coverage', 'book-open-check')" in content
    assert "('readiness', 'Incident Readiness', 'siren')" in content
    assert "('resources', 'Operational Resources', 'external-link')" in content
    assert 'alerts-content-panel-ownership' in content
    assert 'alerts-content-panel-readiness' in content
    assert 'alerts-content-panel-resources' in content
    assert 'partials/_ownership_summary.html' in content
    assert 'partials/_incident_readiness.html' in content
    assert 'partials/_operational_resources.html' in content


def test_cluster_signal_overview_is_compact_and_does_not_use_segment_grid() -> None:
    content = read(OVERVIEW)

    assert 'Cluster Signal Overview' in content
    assert 'Signal Distribution' in content
    assert 'Operational Insight' in content
    assert 'progress_bar.bar' in content
    assert 'range(12)' not in content
    assert 'text-2xl font-semibold text-content-primary">{{ overview.cluster_name }}' not in content
    assert 'truncate whitespace-nowrap' not in content


def test_ownership_workspace_is_not_nested_with_incident_readiness() -> None:
    index_content = read(INDEX)
    ownership_content = read(OWNERSHIP)

    ownership_panel = index_content.split('id="alerts-content-panel-ownership"', 1)[1].split(
        'id="alerts-content-panel-readiness"', 1
    )[0]

    assert '_ownership_summary.html' in ownership_panel
    assert '_incident_readiness.html' not in ownership_panel
    assert 'Coverage Score' in ownership_content
    assert 'Owner Groups' in ownership_content
    assert 'Runbook Links' in ownership_content
    assert 'Metadata Gaps' in ownership_content


def test_operational_resources_are_removed_from_recommendations() -> None:
    recommendations_content = read(RECOMMENDATIONS)
    resources_content = read(RESOURCES)

    assert 'Operational Resources' not in recommendations_content
    assert 'Alertmanager Console' in resources_content
    assert 'Runbook Portal' in resources_content
    assert 'Contact Point' in resources_content
    assert 'External Resource Boundary' in resources_content
