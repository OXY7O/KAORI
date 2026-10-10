from pathlib import Path

from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / 'app/templates'
STORAGE = TEMPLATES / 'storage/object_storage/analytics'


def _source(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_object_storage_reuses_shared_analytics_tracker_across_six_pages() -> None:
    page = _source(STORAGE / 'index.html')
    tracker = _source(TEMPLATES / 'analytics/components/_section_load_tracker.html')
    javascript = _source(ROOT / 'app/static/js/analytics/section_load_tracker.js')
    routes = _source(ROOT / 'app/storage/object_storage/analytics/routes.py')

    assert 'data-analytics-section-tracker-root' in page
    assert 'data-analytics-load-title="Loading Analytics Section"' in page
    assert "section_tracker.render('object-storage-analytics-load-tracker'" in page
    assert "filename='js/analytics/section_load_tracker.js'" in page
    assert page.count("filename='js/analytics/section_load_tracker.js'") == 1
    assert 'data-analytics-section-load-tracker="true"' in tracker
    assert 'data-analytics-load-progress' in tracker
    assert 'data-analytics-load-counter' in tracker
    assert 'Requested Sections' in javascript
    assert 'const REQUESTED = new Set' in javascript
    assert "setText(view, '[data-analytics-load-counter]', 'Applying Filter')" in javascript

    for route in (
        'object_storage_overview',
        'object_storage_capacity',
        'object_storage_performance',
        'object_storage_forecast',
        'object_storage_top_consumers',
        'object_storage_alerts',
    ):
        assert f'def {route}()' in routes

    # Server-rendered summary/panels are not fabricated as HTMX section requests.
    assert 'data-analytics-lazy-section="true"' not in page
    assert "partials/_overview_analysis.html" in page
    assert "partials/_overview_workspace.html" in page
    assert 'data-analytics-lazy-section="true"' not in _source(
        STORAGE / 'partials/_overview_workspace.html'
    )


def test_object_storage_three_real_htmx_record_fragments_are_counted() -> None:
    filenames = {
        '_bucket_table.html': 'object-storage-bucket-table-panel',
        '_bucket_forecast_table.html': 'object-storage-bucket-forecast-table-panel',
        '_alert_records.html': 'object-storage-alert-records',
    }
    for filename, target_id in filenames.items():
        template = _source(STORAGE / 'partials' / filename)
        assert f'id="{target_id}"' in template
        assert 'data-analytics-lazy-section="true"' in template
        assert 'data-analytics-load-state="idle"' in template
        assert 'hx-get=' in template
        assert f'hx-target="#{target_id}"' in template
        assert 'hx-indicator=' in template

    javascript = _source(ROOT / 'app/static/js/analytics/section_load_tracker.js')
    assert 'currentSection(trackedSection(event))' in javascript
    assert 'setState(section, \'loading\')' in javascript
    assert 'setState(section, \'loaded\')' in javascript
    assert 'setState(section, \'failed\')' in javascript
    for error in ('htmx:responseError', 'htmx:sendError', 'htmx:timeout'):
        assert error in javascript


def test_object_storage_controls_use_shared_shell_with_preserved_domain_evidence() -> None:
    controls = _source(STORAGE / 'partials/_controls.html')
    shared = _source(TEMPLATES / 'analytics/components/_controls_readiness.html')

    assert 'shared_readiness.frame(' in controls
    assert "'Analytics Controls & Data Readiness'" in controls
    assert "eyebrow='Analytics Overview' if page_key == 'overview'" in controls
    assert "'object-storage-analytics-refresh-indicator'" in controls
    assert "loading_bar.render(indicator_id" in shared
    assert 'data-analytics-refresh-request="true"' in controls
    assert 'hx-get="{{ url_for(\'analytics.object_storage_\' ~ page_key) }}"' in controls
    assert 'hx-target="#object-storage-analytics-page"' in controls
    assert 'hx-push-url="true"' in controls
    assert 'name="system_id"' in controls
    assert 'name="time_range"' in controls
    assert 'name="history_window"' in controls
    assert 'name="source"' in controls
    for evidence in (
        'Committed Inventory',
        'Analytics Worker Snapshot',
        'Metrics Contract At Collection',
        'Forecast Worker Snapshot',
        'Selected Alert Stream',
        'Alertmanager Lifecycle',
        'Metrics Snapshot Source',
        'Operational Metrics Degraded',
    ):
        assert evidence in controls

    assert '{% endcall %}' in controls
    assert '<section class="{{ analysis_surface.snapshot_shell_classes() }}">' not in controls


def test_shared_object_storage_templates_parse_and_worker_remains_domain_owned() -> None:
    environment = Environment(loader=FileSystemLoader(str(TEMPLATES)))
    for name in (
        'storage/object_storage/analytics/index.html',
        'storage/object_storage/analytics/partials/_controls.html',
        'storage/object_storage/analytics/partials/_bucket_table.html',
        'storage/object_storage/analytics/partials/_bucket_forecast_table.html',
        'storage/object_storage/analytics/partials/_alert_records.html',
        'analytics/components/_controls_readiness.html',
        'analytics/components/_section_load_tracker.html',
    ):
        environment.parse(_source(TEMPLATES / name))

    # Render the actual shared shell rather than testing its text alone.
    example = environment.from_string(
        '{% import "analytics/components/_controls_readiness.html" as controls %}'
        '{% call controls.frame("Analytics Controls & Data Readiness", '
        '"Committed data only", "sliders-horizontal", "example-loading", '
        'eyebrow="Analytics Overview") %}'
        '<span id="example-body">Source data</span>'
        '{% endcall %}'
    ).render()
    assert 'Analytics Controls & Data Readiness' in example
    assert 'id="example-loading"' in example
    assert 'id="example-body"' in example
    assert 'data-analytics-controls-readiness' in example

    service = _source(ROOT / 'app/storage/object_storage/analytics/service.py')
    job_adapter = _source(ROOT / 'app/storage/object_storage/analytics/job_adapter.py')
    assert 'read_analytics_snapshot(' in service
    assert 'enqueue_canonical_job(' in job_adapter
    assert 'analytics-batch' in job_adapter
    assert 'MetricsConsumer' not in _source(STORAGE / 'index.html')
