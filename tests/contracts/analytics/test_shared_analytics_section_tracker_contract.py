from pathlib import Path

from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / 'app/templates'


def test_analytics_section_tracker_macro_is_shared_by_kubernetes_and_registry() -> None:
    shared = (TEMPLATES / 'analytics/components/_section_load_tracker.html').read_text()
    kubernetes = (TEMPLATES / 'kubernetes/analytics/overview/index.html').read_text()
    k8s_tracker = (TEMPLATES / 'kubernetes/analytics/overview/partials/_load_tracker.html').read_text()
    registry = (TEMPLATES / 'artifact_registry/analytics.html').read_text()
    runtime = (ROOT / 'app/static/js/analytics/section_load_tracker.js').read_text()

    assert 'data-analytics-section-load-tracker="true"' in shared
    assert 'data-overview-load-tracker="true"' in shared
    assert 'data-analytics-load-counter' in shared
    assert 'aria-live="polite"' in shared
    assert 'kaori-loading-bar-segment' in shared
    assert 'section_tracker.render' in k8s_tracker
    assert 'section_tracker.render' in registry
    for page in (kubernetes, registry):
        assert 'data-analytics-section-tracker-root' in page
        assert "filename='js/analytics/section_load_tracker.js'" in page

    assert 'window.kaoriInitializeOverviewLoadTracker = initialize' in runtime
    assert "document.body.addEventListener('htmx:beforeRequest'" in runtime
    assert "document.body.addEventListener('htmx:afterSettle'" in runtime
    for error in ('htmx:responseError', 'htmx:sendError', 'htmx:timeout'):
        assert error in runtime
    assert 'Requested Sections' in runtime
    assert 'JobExecution progress' in runtime
    assert 'const REQUESTED = new Set' in runtime


def test_registry_tracker_counts_actual_committed_fragment_requests_only() -> None:
    shell = (TEMPLATES / 'artifact_registry/analytics.html').read_text()
    summary = (TEMPLATES / 'artifact_registry/partials/_analytics_summary.html').read_text()
    section = (TEMPLATES / 'artifact_registry/partials/_analytics_section.html').read_text()
    filters = (TEMPLATES / 'artifact_registry/partials/_analytics_controls_readiness.html').read_text()
    k8s = (TEMPLATES / 'kubernetes/analytics/overview/index.html').read_text()
    shared_runtime = (ROOT / 'app/static/js/analytics/section_load_tracker.js').read_text()

    assert shell.count('data-analytics-lazy-section="true"') == 2
    assert 'data-analytics-lazy-section="true"' in summary
    assert 'data-analytics-lazy-section="true"' in section
    assert 'data-analytics-load-state="loaded"' in summary
    assert 'data-analytics-load-state="loaded"' in section
    assert 'analytics_materialization_resolve' in shell
    assert 'data-analytics-lazy-section="true"' not in filters
    assert 'data-analytics-refresh-request="true"' in filters
    assert 'data-overview-lazy-section="true"' in k8s
    assert 'data-overview-refresh-request="true"' not in shell
    assert 'data-overview-lazy-section="true"' in shared_runtime
    assert 'data-analytics-lazy-section="true"' in shared_runtime
    assert 'currentSection(section)' in shared_runtime
    assert "setState(section, 'failed')" in shared_runtime
    assert "setState(section, 'loading')" in shared_runtime


def test_shared_analytics_tracker_is_parseable_and_retains_approved_geometry() -> None:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)))
    rendered = env.from_string(
        '{% import "analytics/components/_section_load_tracker.html" as tracker %}'
        '{{ tracker.render("example-analytics-load") }}'
    ).render()
    assert 'id="example-analytics-load"' in rendered
    assert '0/0 Sections' in rendered
    assert 'data-analytics-section-load-tracker="true"' in rendered
    assert 'data-overview-load-tracker="true"' in rendered
    assert 'role="status"' in rendered
    assert 'aria-live="polite"' in rendered


def test_overview_section_tracker_has_single_shared_runtime_owner() -> None:
    # This is the Overview *section* tracker, not the generic page-level
    # tracker retained in analytics/controls.js by merged issue #391.
    overview = (TEMPLATES / 'kubernetes/analytics/overview/index.html').read_text()
    registry = (TEMPLATES / 'artifact_registry/analytics.html').read_text()
    layout = (TEMPLATES / 'layouts/app.html').read_text()
    shared = (ROOT / 'app/static/js/analytics/section_load_tracker.js').read_text()
    readme = (ROOT / 'app/kubernetes/analytics/README.md').read_text()

    legacy = ROOT / 'app/static/js/kubernetes/analytics/overview.js'
    assert not legacy.exists(), 'Retired Overview-specific tracker must not regain event ownership.'
    assert overview.count("filename='js/analytics/section_load_tracker.js'") == 1
    assert registry.count("filename='js/analytics/section_load_tracker.js'") == 1
    for page in (overview, registry, layout):
        assert 'js/kubernetes/analytics/overview.js' not in page

    assert "filename='js/analytics/controls.js'" in layout
    assert 'app/static/js/analytics/section_load_tracker.js' in readme
    assert 'app/static/js/kubernetes/analytics/overview.js' not in readme
    assert shared.count('window.kaoriInitializeOverviewLoadTracker = initialize') == 1
    assert shared.count("document.body.addEventListener('htmx:beforeRequest'") == 1
    assert shared.count("document.body.addEventListener('htmx:afterSettle'") == 1
    assert 'currentSection(trackedSection(event))' in shared
    assert "setState(section, 'failed')" in shared
    for event in ('htmx:responseError', 'htmx:sendError', 'htmx:timeout'):
        assert event in shared
    assert 'Requested Sections' in shared
    assert 'JobExecution progress' in shared
