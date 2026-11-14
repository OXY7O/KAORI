from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_registry_analytics_is_worker_materialized_and_page_reads_snapshot() -> None:
    analytics = (ROOT / 'app/artifact_registry/analytics.py').read_text()
    presentation = (ROOT / 'app/artifact_registry/presentation_analytics.py').read_text()
    routes = (ROOT / 'app/artifact_registry/routes.py').read_text()
    jobs = (ROOT / 'app/definitions/catalogs/platform_operations/jobs/registered_jobs.yaml').read_text()

    assert 'RegistryAnalyticsSnapshot(' in analytics
    assert 'MetricsConsumer.for_asset' in analytics
    assert "scope_type='registry_instance'" in analytics
    assert 'RegistryAnalyticsSnapshot.query' in presentation
    assert 'MetricsConsumer' not in presentation
    assert 'requests.' not in routes
    assert 'artifact_registry.analytics.materialize' in jobs
    assert 'queue_name: analytics-batch' in jobs


def test_registry_recommendations_are_owned_by_central_intelligence() -> None:
    service = (ROOT / 'app/intelligence/service.py').read_text()
    evaluator = (ROOT / 'app/intelligence/registry_recommendations.py').read_text()
    rules = (ROOT / 'app/definitions/catalogs/intelligence/rules.yaml').read_text()

    assert 'build_registry_recommendation_findings' in service
    assert 'build_registry_recommendation_findings' in evaluator
    for rule_key in (
        'registry.security.critical_runtime_vulnerability',
        'registry.security.scan_evidence_missing',
        'registry.governance.public_project_without_immutability',
        'registry.runtime.tag_only_correlation',
        'registry.capacity.quota_exhaustion_review',
        'registry.capacity.quota_exhaustion_critical',
    ):
        assert f'rule_key: {rule_key}' in rules

    artifact_registry_files = list((ROOT / 'app/artifact_registry').glob('*.py'))
    assert not any('RegistryRecommendation' in path.read_text() for path in artifact_registry_files)
    assert not any('AcceptedRisk' in path.read_text() for path in artifact_registry_files)


def test_raw_vulnerability_evidence_does_not_auto_escalate() -> None:
    rules = (ROOT / 'app/definitions/catalogs/intelligence/rules.yaml').read_text()
    critical = rules.split(
        '- rule_key: registry.security.critical_runtime_vulnerability',
        1,
    )[1].split('- rule_key:', 1)[0]
    scan_gap = rules.split(
        '- rule_key: registry.security.scan_evidence_missing',
        1,
    )[1].split('- rule_key:', 1)[0]

    assert 'runtime' in critical.lower()
    assert 'mode: manual' in critical
    assert 'alert_escalation:' not in scan_gap


def test_domain_intelligence_ownership_standard_is_present() -> None:
    standard = (ROOT / 'docs/architecture/domain-intelligence-ownership-standard.md').read_text()
    assert 'Intelligence owns recommendation semantics' in standard
    assert 'Automation Control' in standard
    assert 'Direct Recommendation → provider mutation is not allowed.' in standard


def test_registry_scan_gap_recommendation_uses_usable_scan_evidence_semantics() -> None:
    evaluator = (ROOT / 'app/intelligence/registry_recommendations.py').read_text()
    rules = (ROOT / 'app/definitions/catalogs/intelligence/rules.yaml').read_text()

    assert 'from app.integrations.registry.security_contracts import registry_scan_evidence_ready' in evaluator
    assert 'if not registry_scan_evidence_ready(artifact.scan_status):' in evaluator
    assert 'Running Registry artifact has no usable scan evidence' in evaluator
    assert 'not a normalized ' in evaluator
    assert 'successful scan state.' in evaluator

    scan_gap = rules.split(
        '- rule_key: registry.security.scan_evidence_missing',
        1,
    )[1].split('- rule_key:', 1)[0]
    assert 'Running Registry Artifact Has No Usable Scan Evidence' in scan_gap
    assert 'success, finished, or completed' in scan_gap
    assert 'runtime binding' in scan_gap.lower()


def test_registry_analytics_materializes_operational_harbor_metric_profile() -> None:
    analytics = (ROOT / 'app/artifact_registry/analytics.py').read_text()
    profile = (ROOT / 'app/integrations/observability/metrics_source/query_profiles/registry_harbor_v1.py').read_text()

    for query_key in (
        'registry.health',
        'registry.component.up',
        'registry.projects.total',
        'registry.project.artifacts',
        'registry.project.quota.usage_bytes',
        'registry.project.quota.bytes',
        'registry.project.pull_count',
        'registry.core.request_rate',
        'registry.core.inflight',
        'registry.backend.request_rate',
        'registry.task.queue_size',
    ):
        assert query_key in profile
        assert query_key in analytics

    assert "'capability_gaps': gaps" in analytics
    assert "'metrics_source': consumer.config.name" in analytics
    assert "scope_type='registry_instance'" in analytics


def test_registry_historical_snapshots_use_measured_source_range_and_scope() -> None:
    history = (ROOT / 'app/artifact_registry/analytics_history.py').read_text()
    analytics = (ROOT / 'app/artifact_registry/analytics.py').read_text()
    adapter = (ROOT / 'app/artifact_registry/analytics_job_adapter.py').read_text()
    routes = (ROOT / 'app/artifact_registry/routes.py').read_text()
    presentation = (ROOT / 'app/artifact_registry/presentation_analytics.py').read_text()
    common = (ROOT / 'app/artifact_registry/presentation_common.py').read_text()

    assert 'consumer.query_range(' in history
    assert "'60d': timedelta(days=60)" in history
    assert 'MAX_HISTORY_POINTS = 240' in history
    assert 'MAX_HISTORY_SERIES = 250' in history
    assert 'snapshot.time_range = time_range' in analytics
    assert "'history': history" not in presentation
    assert 'time_range=normalize_registry_analytics_window(snapshot_window)' in presentation
    assert 'RegistryAnalyticsSnapshot.time_range == normalized_window' in adapter
    assert "RegistryAnalyticsSnapshot.time_range == 'current'" in common
    assert "parameters={'snapshot_window': window}" in routes
    assert "scope_key=f'all:{time_range}'" in adapter
    assert 'artifact_growth_per_day' in history
    assert 'size_growth_bytes_per_day' in history


def test_registry_growth_history_chart_points_are_bounded_measured_and_aligned() -> None:
    from datetime import UTC, datetime, timedelta

    from app.artifact_registry.analytics_history import (
        MAX_HISTORY_CHART_POINTS,
        _bounded_matrix,
    )
    from app.artifact_registry.presentation_analytics import _committed_growth_chart_points

    start = datetime(2026, 11, 13, tzinfo=UTC)
    end = start + timedelta(minutes=99)
    origin = start.timestamp()

    def samples(baseline: float, factor: float, offset: int = 0) -> list[list[str]]:
        return [[str(origin + i * 60 + offset), str(baseline + i * factor)] for i in range(100)]

    aligned = {
        'status': 'success',
        'data': {
            'resultType': 'matrix',
            'result': [
                {'metric': {'project_name': 'alpha'}, 'values': samples(10, 1)},
                {'metric': {'project_name': 'beta'}, 'values': samples(5, 2)},
            ],
        },
    }
    chart: list[dict[str, float]] = []
    summary = _bounded_matrix(
        aligned,
        project_scoped=True,
        start_at=start,
        end_at=end,
        step_seconds=60,
        chart_points=chart,
    )
    assert MAX_HISTORY_CHART_POINTS == 48
    assert len(chart) == MAX_HISTORY_CHART_POINTS
    assert chart[0] == {'timestamp': origin, 'value': 15.0}
    assert chart[-1] == {'timestamp': origin + 99 * 60, 'value': 312.0}
    assert summary['alpha']['samples'] == 100
    assert all(chart[i]['timestamp'] < chart[i + 1]['timestamp'] for i in range(len(chart) - 1))
    points, mode, count = _committed_growth_chart_points(
        {'chart_series': {'project_artifacts': chart}}, 'project_artifacts'
    )
    assert points == chart and mode == 'measured' and count == 48

    unaligned = {
        'status': 'success',
        'data': {
            'resultType': 'matrix',
            'result': [
                {'metric': {'project_name': 'alpha'}, 'values': samples(10, 1)},
                {'metric': {'project_name': 'beta'}, 'values': samples(5, 2, offset=60)},
            ],
        },
    }
    chart = []
    _bounded_matrix(
        unaligned,
        project_scoped=True,
        start_at=start,
        end_at=end,
        step_seconds=60,
        chart_points=chart,
    )
    assert chart == []  # No timestamp mixing or interpolated filler.


def test_registry_growth_chart_legacy_uses_only_committed_endpoints() -> None:
    from types import SimpleNamespace

    from app.artifact_registry.presentation_analytics import (
        _committed_growth_chart_points,
        _registry_growth_charts,
    )

    legacy = {
        'source': 'metrics_source_query_range',
        'status': 'ready',
        'time_range': '24h',
        'series': {
            'project_artifacts': {
                'demo': {'start_time': 10, 'end_time': 20, 'first': 3, 'last': 5, 'samples': 100},
            },
        },
    }
    points, mode, count = _committed_growth_chart_points(legacy, 'project_artifacts')
    assert mode == 'checkpoints' and count == 2
    assert points == [{'timestamp': 10.0, 'value': 3.0}, {'timestamp': 20.0, 'value': 5.0}]
    view = {
        'identity': SimpleNamespace(name='Harbor X300'),
        'snapshot': SimpleNamespace(payload_json={'history': legacy}),
    }
    result = _registry_growth_charts([view], snapshot_window='24h')
    assert len(result['artifacts']) == 1
    assert result['artifacts'][0]['mode'] == 'checkpoints'
    assert result['storage'] == []
    assert _registry_growth_charts([view], snapshot_window='current') == {
        'artifacts': [],
        'storage': [],
    }
    assert _registry_growth_charts([view], snapshot_window='7d')['artifacts'] == []
    legacy['series']['project_artifacts']['demo']['last'] = float('nan')
    assert _committed_growth_chart_points(legacy, 'project_artifacts')[0] == []


def test_registry_growth_overview_charts_and_summary_reuse_canonical_patterns() -> None:
    from jinja2 import Environment

    summary = (ROOT / 'app/templates/artifact_registry/partials/_analytics_summary.html').read_text()
    growth = (ROOT / 'app/templates/artifact_registry/partials/_analytics_growth_charts.html').read_text()
    panel = (ROOT / 'app/templates/artifact_registry/partials/_analytics_overview_panel.html').read_text()
    page = (ROOT / 'app/templates/artifact_registry/analytics.html').read_text()
    script = (ROOT / 'app/static/js/artifact_registry/analytics_growth_chart.js').read_text()
    worker = (ROOT / 'app/artifact_registry/analytics_history.py').read_text()
    presentation = (ROOT / 'app/artifact_registry/presentation_analytics.py').read_text()
    inventory = (ROOT / 'app/templates/artifact_registry/partials/_inventory_workspace.html').read_text()
    for template in (summary, growth, panel):
        Environment().parse(template)

    assert 'header_badge=posture_badge' in summary
    assert 'table_label.metadata_label(analytical_metrics|length' in summary
    assert 'header_badge=posture_badge' in inventory
    assert 'artifact_registry/partials/_analytics_growth_charts.html' in panel
    assert 'data-registry-growth-chart-panel' in growth
    assert 'data-registry-growth-chart-series' in growth
    assert 'data-registry-growth-chart' in growth
    assert 'Historical Chart Not Available' in growth
    assert 'Source Growth Trend Guide' in growth
    assert 'chart.umd.min.js' in page
    assert 'js/artifact_registry/analytics_growth_chart.js' in page
    assert 'new Chart(' in script
    assert "document.body.addEventListener('htmx:afterSwap'" in script
    assert 'data-registry-growth-chart-series' in growth
    assert 'MAX_HISTORY_CHART_POINTS = 48' in worker
    assert "'chart_series': chart_series" in worker
    assert "_registry_growth_charts(bundle['latest_rows'], snapshot_window=selected_window)" in presentation
    assert 'MetricsConsumer' not in presentation
    assert 'consumer.query_range(' in worker


def test_registry_analytics_workspace_is_reusable_and_intelligence_bounded() -> None:
    shell = (ROOT / 'app/templates/artifact_registry/analytics.html').read_text()
    section = (ROOT / 'app/templates/artifact_registry/partials/_analytics_section.html').read_text()
    overview_tabs = (ROOT / 'app/templates/artifact_registry/partials/_analytics_overview_workspace.html').read_text()
    overview_panel = (ROOT / 'app/templates/artifact_registry/partials/_analytics_overview_panel.html').read_text()
    presentation = (ROOT / 'app/artifact_registry/presentation_analytics.py').read_text()
    routes = (ROOT / 'app/artifact_registry/routes.py').read_text()

    assert 'components/framed_workspace_tabs.html' not in shell
    assert 'framed_workspace_tabs.render_navigation' not in shell
    assert 'artifact-registry-analytics-workspace' in shell
    assert 'Explore Analytics' in shell
    for title in (
        'Registry Growth',
        'Capacity Outlook',
        'Artifact Usage',
        'Risk Concentration',
        'Governance Gaps',
        'Operational Alerts',
        'Derived Insights',
        'Central Intelligence',
    ):
        assert title in section

    for tab in ('growth', 'capacity', 'usage', 'risk', 'governance', 'alerts', 'insights'):
        assert f"('{tab}'," in overview_tabs
        assert f"'{tab}'" in presentation
    assert "url_for('artifact_registry.analytics_' ~ overview_domain" in overview_panel

    assert "return _render_registry_analytics_page('overview')" in routes
    assert "legacy_tab = request.args.get('tab', '', type=str)" in routes
    assert 'never waits on live Harbor, Alertmanager, Prometheus, or Thanos requests' in shell
    assert 'never auto-cleaned' in section
    assert (
        'central Intelligence owns recommendation semantics, Accepted Risk, escalation, and automation control'
        in section
    )
    assert "url_for('intelligence.recommendations', domain='registry')" in shell

    assert "aggregate['inflight_requests'] > 100" not in presentation
    assert "aggregate['task_queue_size'] > 0" not in presentation


def test_registry_analytics_overview_uses_shared_tabs_and_bounded_committed_panels() -> None:
    from jinja2 import Environment, FileSystemLoader

    shell = (ROOT / 'app/templates/artifact_registry/analytics.html').read_text()
    tabs = (ROOT / 'app/templates/artifact_registry/partials/_analytics_overview_workspace.html').read_text()
    panel = (ROOT / 'app/templates/artifact_registry/partials/_analytics_overview_panel.html').read_text()
    routes = (ROOT / 'app/artifact_registry/routes.py').read_text()
    common = (ROOT / 'app/templates/components/content_tabs.html').read_text()
    js = (ROOT / 'app/static/js/analytics/controls.js').read_text()
    k8 = (ROOT / 'app/templates/kubernetes/analytics/overview/index.html').read_text()
    storage = (ROOT / 'app/templates/storage/object_storage/analytics/partials/_overview_workspace.html').read_text()

    for template in (shell, tabs, panel):
        Environment().parse(template)
    assert 'artifact_registry/partials/_analytics_overview_workspace.html' in shell
    assert "section='summary'" in shell
    assert (
        "'Analytical Evidence Summary'"
        in (ROOT / 'app/templates/artifact_registry/partials/_analytics_summary.html').read_text()
    )
    assert 'analytics_domains =' not in shell
    assert 'Analytics Domains' not in shell

    assert '{% import "components/content_tabs.html" as content_tabs %}' in tabs
    assert "content_tabs.render_buttons('artifact-registry-overview-content'," in tabs
    assert "content_tabs.render_buttons('overview-content'," in k8
    assert "content_tabs.render_buttons('object-storage-overview-content'," in storage
    assert 'data-analytics-tabset-id="artifact-registry-overview-content"' in tabs
    assert 'data-analytics-update-query="false"' in tabs
    assert 'data-default-tab="growth"' in tabs
    assert 'hx-trigger="kaori:analytics-tab-activated once"' in tabs
    assert 'data-overview-lazy-section="true"' in tabs
    assert 'hx_sync=' not in tabs
    assert 'hx-sync="this:replace"' in tabs
    assert "overview_panel='1'" in tabs
    assert 'provider_id=analytics.selected_provider_id' in tabs
    assert 'snapshot_window=analytics.snapshot_window' in tabs
    assert 'render_buttons(' in common
    assert "tabset.dataset.analyticsUpdateQuery !== 'false'" in js

    for key, label in (
        ('growth', 'Growth'),
        ('capacity', 'Capacity'),
        ('usage', 'Usage'),
        ('risk', 'Risk'),
        ('governance', 'Governance'),
        ('alerts', 'Alerts'),
        ('insights', 'Insights'),
        ('evidence', 'Data & Evidence'),
    ):
        assert f"('{key}', '{label}'," in tabs

    # Test the actual shared tab geometry and unique panel identity after Jinja rendering.
    env = Environment(loader=FileSystemLoader(str(ROOT / 'app/templates')))
    env.globals['url_for'] = lambda endpoint, **kwargs: f'/{endpoint.replace(".", "/")}'
    rendered = env.get_template('artifact_registry/partials/_analytics_overview_workspace.html').render(
        analytics={
            'snapshot_count': 1,
            'provider_count': 1,
            'snapshot_window': '24h',
            'selected_provider_id': 5,
        }
    )
    assert rendered.count('data-analytics-tab-button=') == 8
    assert rendered.count('data-analytics-tab-panel=') == 8
    assert rendered.count('data-overview-lazy-section="true"') == 8
    assert rendered.count('hx-trigger="kaori:analytics-tab-activated once"') == 8
    assert rendered.count('data-kaori-tab-variant="content-tabs"') == 1
    assert 'data-kaori-info-tip-variant="guide"' in rendered

    # The Overview-only variant cannot expose Data & Evidence as a detail route.
    assert "overview_panel = request.args.get('overview_panel', '', type=str) == '1'" in routes
    assert "overview_panel and section == 'evidence'" in routes
    assert "overview_panel and section == 'summary'" in routes
    assert "context['data_readiness'] = build_registry_analytics_readiness(" in routes
    assert "'artifact_registry/partials/_analytics_overview_panel.html'" in routes
    assert 'return render_template(template, analytics=context)' in routes
    assert "@permission_required('artifact_registry.view')" in routes
    assert (
        'dispatch_registered_job('
        not in routes.split('def analytics_section(', 1)[1].split('def analytics_alerts_table(', 1)[0]
    )
    assert 'MetricsConsumer' not in routes


def test_registry_analytics_overview_panels_preserve_missing_data_and_evidence_authority() -> None:
    from jinja2 import Environment

    panel = (ROOT / 'app/templates/artifact_registry/partials/_analytics_overview_panel.html').read_text()
    Environment().parse(panel)

    assert 'analytics.snapshot_count > 0' in panel
    assert 'if analytics.activity_rows else unknown' in panel
    assert 'if analytics.capacity_outlook.highest_utilization is not none else unknown' in panel
    assert "if analytics.capacity_outlook.nearest_quota_days is not none else 'No forecast'" in panel
    assert 'aggregate.governance_projects_assessed > 0' in panel
    assert 'if alerts_ready else unknown' in panel
    assert 'if has_snapshot else unknown' in panel
    assert 'Committed Source Coverage' in panel
    assert 'analytics.latest_rows[:5]' in panel
    assert 'readiness.current_count' in panel
    assert 'readiness.execution_label' in panel
    assert 'row.status_label, row.tone' in panel
    assert 'No committed snapshots for the selected Registry and Time Range.' in panel
    charts = (ROOT / 'app/templates/artifact_registry/partials/_analytics_growth_charts.html').read_text()
    assert 'artifact_registry/partials/_analytics_growth_charts.html' in panel
    assert 'data-registry-growth-chart-panel' in charts
    capacity_chart = (ROOT / 'app/templates/artifact_registry/partials/_analytics_capacity_chart.html').read_text()
    assert 'artifact_registry/partials/_analytics_capacity_chart.html' in panel
    assert 'analytics.capacity_chart_rows' in capacity_chart
    assert 'data-registry-capacity-quota-series' in capacity_chart
    assert 'analytics.activity_rows[:3]' in panel
    assert 'analytics.insights[:3]' in panel
    assert 'analytics.alert_source_rows[:3]' in panel
    assert 'no automatic cleanup' in panel
    assert 'Missing pull metrics do not imply zero demand.' in panel
    assert 'not interchangeable' in panel
    assert 'Not Configured differs from Not Collected' in panel
    assert 'Intelligence owns Recommendations' in panel
    assert 'scanner_observed = has_snapshot and aggregate.scanned_artifacts > 0' in panel
    assert 'aggregate.alert_sources_ready == analytics.provider_count' in panel


def test_registry_overview_panels_render_unknown_without_fabricating_evidence() -> None:
    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader(str(ROOT / 'app/templates')))
    env.globals['url_for'] = lambda endpoint, **kwargs: f'/{endpoint.replace(".", "/")}'
    aggregate_keys = (
        'artifacts',
        'stale_candidates',
        'running_artifacts',
        'runtime_bindings',
        'tag_only_bindings',
        'scanned_artifacts',
        'critical_findings',
        'critical_runtime_artifacts',
        'runtime_scan_gaps',
        'governance_projects_assessed',
        'retention_configured',
        'immutability_configured',
        'retention_not_configured',
        'alert_sources_ready',
        'active_alerts',
        'critical_alerts',
        'suppressed_alerts',
        'alert_source_fallbacks',
        'pull_activity',
    )
    context = {
        'aggregate': dict.fromkeys(aggregate_keys, 0),
        'snapshot_count': 0,
        'provider_count': 1,
        'summary_cards': [{'value': 'N/A'} for _ in range(4)],
        'capacity_outlook': {
            'highest_utilization': None,
            'nearest_quota_days': None,
            'quota_headroom_display': 'N/A',
            'growth_display': 'N/A',
        },
        'growth_rows': [],
        'growth_charts': {'artifacts': [], 'storage': []},
        'forecast_rows': [],
        'capacity_chart_rows': [],
        'activity_rows': [],
        'alert_source_rows': [],
        'insights': [],
        'latest_rows': [],
        'recommendation_count': 0,
        'active_signal_count': 0,
        'posture': {'label': 'Materialization Required', 'tone': 'warning'},
        'selected_provider_id': None,
        'snapshot_window': '24h',
        'data_readiness': {
            'label': 'Historical Materialization Required',
            'tone': 'warning',
            'eligible_count': 1,
            'covered_count': 0,
            'current_count': 0,
            'last_attempt_label': 'Never',
            'execution_label': 'Not Collected',
            'execution_tone': 'warning',
            'helper': 'Historical range evidence unavailable.',
        },
    }
    template = env.get_template('artifact_registry/partials/_analytics_overview_panel.html')
    domains = ('growth', 'capacity', 'usage', 'risk', 'governance', 'alerts', 'insights', 'evidence')
    for domain in domains:
        rendered = template.render(analytics=context, overview_domain=domain)
        assert f'data-registry-analytics-overview-domain="{domain}"' in rendered
        assert 'Provider Health' not in rendered
        if domain != 'evidence':
            assert 'Materialization Required' in rendered
            assert 'N/A' in rendered
            assert f'/artifact_registry/analytics_{domain}' in rendered
        else:
            assert 'Historical Materialization Required' in rendered
            assert 'No committed snapshots for the selected Registry and Time Range.' in rendered


def test_registry_capacity_chart_projection_requires_committed_valid_quota_evidence() -> None:
    from app.artifact_registry.presentation_analytics import _registry_capacity_chart_rows

    def project(name: str, usage: float, quota: float, *, registry: str = 'Harbor X300') -> dict[str, object]:
        return {
            'project_name': name,
            'registry_name': registry,
            'usage_bytes': usage,
            'quota_bytes': quota,
            'usage_display': f'{usage} B',
            'quota_display': f'{quota} B',
            'days_to_quota_display': 'No forecast',
        }

    rows = [
        project('zero', 0, 100),
        project('small', 6, 1000),
        project('over-quota', 150, 100),
        project('half', 50, 100),
        project('third', 30, 100),
        project('quarter', 25, 100),
        project('seven', 10, 100),
        project('missing-quota', 10, 0),
        project('negative-usage', -10, 100),
        project('nonfinite-usage', float('nan'), 100),
        project('nonfinite-quota', 5, float('inf')),
        project('invalid-type', True, 100),
        project('', 20, 100),
    ]
    projected = _registry_capacity_chart_rows(rows)
    assert len(projected) == 5
    assert [row['project_name'] for row in projected] == [
        'over-quota',
        'half',
        'third',
        'quarter',
        'seven',
    ]
    assert projected[0]['utilization_percent'] == 150.0
    assert projected[0]['utilization_display'] == '150.0%'
    assert projected[0]['usage_bytes'] == 150.0
    assert projected[0]['quota_bytes'] == 100.0
    assert projected[0]['forecast_label'] == 'No forecast'
    assert _registry_capacity_chart_rows([project('zero', 0, 100)])[0]['utilization_percent'] == 0.0
    assert _registry_capacity_chart_rows([project('missing-quota', 10, 0)]) == []
    assert _registry_capacity_chart_rows([]) == []


def test_registry_capacity_overview_chart_reuses_evidence_and_htmx_chart_contract() -> None:
    from jinja2 import Environment, FileSystemLoader

    partial = (ROOT / 'app/templates/artifact_registry/partials/_analytics_capacity_chart.html').read_text()
    overview = (ROOT / 'app/templates/artifact_registry/partials/_analytics_overview_panel.html').read_text()
    page = (ROOT / 'app/templates/artifact_registry/analytics.html').read_text()
    chart = (ROOT / 'app/static/js/artifact_registry/analytics_capacity_chart.js').read_text()
    present = (ROOT / 'app/artifact_registry/presentation_analytics.py').read_text()
    shared = (ROOT / 'app/templates/components/table_label.html').read_text()
    Environment().parse(partial)
    assert 'artifact_registry/partials/_analytics_capacity_chart.html' in overview
    assert 'data-registry-capacity-quota-series' in partial
    assert 'data-registry-capacity-quota-chart' in partial
    assert 'Project Quota Utilization Guide' in partial
    assert 'Quota Chart Not Available' in partial
    assert 'quota_rows|length ~' in partial
    assert 'analytics.capacity_chart_rows' in partial
    assert 'grid gap-4 p-4 lg:grid-cols-5 sm:p-5' in partial
    assert "analysis_surface.evidence_shell_classes('min-w-0 lg:col-span-3')" in partial
    assert "analysis_surface.evidence_shell_classes('min-w-0 lg:col-span-2')" in partial
    assert 'Peak observed utilization' in partial
    assert '100% = quota limit' in partial
    assert "analysis_surface.ranked_item_classes('min-w-0 p-3 sm:p-4')" in partial
    assert 'data-registry-capacity-axis-note' in partial
    assert 'aria-describedby="registry-capacity-chart-note"' in partial
    assert 'if (maxObserved <= 1) axisMax = 1' in chart
    assert 'else if (maxObserved <= 5) axisMax = 5' in chart
    assert 'else if (maxObserved <= 25) axisMax = 25' in chart
    assert 'else if (maxObserved > 100) axisMax = Math.ceil(maxObserved / 25) * 25' in chart
    assert "axisNote.textContent =" in chart
    assert 'lg:col-span-3' in partial
    assert 'lg:col-span-2' in partial
    assert 'aria-labelledby="registry-capacity-chart-title"' in partial
    assert 'aria-labelledby="registry-capacity-evidence-title"' in partial
    assert "table_label.status_label('Observed', 'normal', size='compact')" in partial
    assert 'Committed usage, quota and forecast status.' in partial
    assert '<dt class="text-content-muted">Used</dt>' in partial
    assert '<dt class="text-content-muted">Quota</dt>' in partial
    assert '<dt class="text-content-muted">Forecast</dt>' in partial
    assert 'Review Capacity Analysis for complete project evidence.' not in partial
    assert 'Quota utilization is observed; exhaustion forecasts require qualified growth history.' in overview
    assert 'metadata_label(' in shared
    assert '[:5]' in present or '[:5]' in partial
    assert "'capacity_chart_rows': _registry_capacity_chart_rows(forecast_rows)" in present
    assert 'js/artifact_registry/analytics_capacity_chart.js' in page
    assert 'vendor/chartjs/chart.umd.min.js' in page
    assert "type: 'bar'" in chart
    assert "indexAxis: 'y'" in chart
    assert 'new Chart(' in chart
    assert 'htmx:beforeSwap' in chart
    assert 'htmx:afterSwap' in chart
    assert 'kaori:analytics-tab-visible' in chart

    env = Environment(loader=FileSystemLoader(str(ROOT / 'app/templates')))
    rows = [
        {
            'project_name': 'demo',
            'registry_name': 'Harbor X300',
            'utilization_percent': 0.6,
            'utilization_display': '0.6%',
            'usage_bytes': 6.0,
            'quota_bytes': 1000.0,
            'usage_display': '6 B',
            'quota_display': '1000 B',
            'forecast_label': 'No forecast',
        }
    ]
    rendered = env.get_template('artifact_registry/partials/_analytics_capacity_chart.html').render(
        analytics={'capacity_chart_rows': rows}
    )
    assert 'demo' in rendered
    assert 'Harbor X300' in rendered
    assert '0.6%' in rendered
    assert rendered.count('Peak observed utilization') == 1
    assert 'Peak observed utilization' in rendered
    assert '100% = quota limit' in rendered
    assert 'registry-capacity-chart-note' in rendered
    assert 'data-registry-capacity-axis-note' in rendered
    assert 'No forecast' in rendered
    assert 'Observed' in rendered
    assert 'Used' in rendered and 'Quota' in rendered
    assert rendered.count('id="registry-capacity-chart-title"') == 1
    assert rendered.count('id="registry-capacity-evidence-title"') == 1
    assert 'data-registry-capacity-quota-chart' in rendered
    assert 'Quota Chart Not Available' not in rendered
    empty = env.get_template('artifact_registry/partials/_analytics_capacity_chart.html').render(
        analytics={'capacity_chart_rows': []}
    )
    assert 'Quota Chart Not Available' in empty
    assert 'data-registry-capacity-quota-chart' not in empty


def test_registry_analytics_uses_fast_shell_and_bounded_fragments() -> None:
    presentation = (ROOT / 'app/artifact_registry/presentation_analytics.py').read_text()
    routes = (ROOT / 'app/artifact_registry/routes.py').read_text()
    template = (ROOT / 'app/templates/artifact_registry/analytics.html').read_text()

    assert 'def build_analytics_shell(' in presentation
    assert "active_tab: str = 'overview'" in presentation
    assert 'analytics=build_analytics_shell(' in routes
    assert "@artifact_registry_bp.get('/analytics/section/<string:section>')" in routes
    assert "section='summary'" in template
    assert 'section=analytics.active_tab' in template
    assert 'hx-trigger="load"' in template
    assert 'Fast Shell · Committed Evidence' in template
    assert 'never waits on live Harbor, Alertmanager, Prometheus, or Thanos requests' in template


def test_registry_analytics_readiness_reuses_k8s_shared_controls_without_buttons() -> None:
    from jinja2 import Environment

    template_paths = (
        'app/templates/analytics/components/_controls_readiness.html',
        'app/templates/kubernetes/analytics/components/_analysis_workspace.html',
        'app/templates/artifact_registry/partials/_analytics_controls_readiness.html',
        'app/templates/artifact_registry/partials/_analytics_collect_live_state.html',
        'app/templates/artifact_registry/analytics.html',
    )
    templates = {path: (ROOT / path).read_text() for path in template_paths}
    for text in templates.values():
        Environment().parse(text)
    common, k8s, registry, live, page = templates.values()
    presenter = (ROOT / 'app/artifact_registry/presentation_analytics.py').read_text()

    assert '{% macro frame(' in common
    assert 'analysis_surface.snapshot_shell_classes()' in common
    assert 'analysis_surface.snapshot_header_icon_classes()' in common
    assert 'loading_bar.render(indicator_id, active=loading' in common
    assert '{% macro snapshot_card(' in common
    assert '{% macro source_card(' in common
    assert 'shared_readiness.frame(title, description, icon, indicator_id' in k8s
    assert '{% set outer_caller = caller %}' in k8s
    assert '{{ outer_caller() }}' in k8s
    assert 'shared_readiness.snapshot_card(' in k8s
    assert 'shared_readiness.frame(' in registry
    assert 'shared_readiness.source_card(' in registry
    assert 'shared_readiness.snapshot_card(' in registry
    assert 'Analytics Controls & Data Readiness' in registry
    assert "eyebrow='Analytics Overview' if analytics.active_tab == 'overview'" in registry
    assert "'Registry'" in registry
    assert "'Time Range'" in registry
    assert 'All Registries' not in registry
    assert "empty_label='No Registries Available' if not analytics.provider_options else none" in registry
    assert 'analytics.time_range_options' in registry
    assert "'time_range_options': get_allowed_time_ranges()" in presenter
    assert "legacy_label='Current (Instant)'" in registry
    assert 'Registry Source Status' in registry
    assert 'icon=none' in registry
    assert "'bg-status-normal'" in common
    assert "'bg-status-warning'" in common
    assert "'bg-status-critical'" in common
    assert "'bg-status-unknown'" in common
    assert "legacy_value='current'" in registry
    assert 'Latest Analytics Data Snapshot' in registry
    assert 'shared_readiness.selector(' in registry
    assert "'artifact-registry-analytics-provider'" in registry
    assert "'artifact-registry-analytics-window'" in registry
    assert "'provider_id'" in registry
    assert "'snapshot_window'" in registry
    assert 'analytics.provider_options' in registry
    assert 'shared_readiness.controls_grid()' in registry
    assert 'shared_readiness.readiness_grid()' in registry
    assert 'kubernetes/analytics/components/_analysis_workspace.html' not in registry
    assert 'hx-trigger="change delay:120ms"' in registry
    assert 'hx-push-url="true"' in registry
    assert 'hx-indicator="#artifact-registry-analytics-refresh-indicator"' in registry
    assert 'loading=readiness.is_active' in registry
    assert "header_content=worker_status if readiness.is_active else ''" in registry
    assert 'header_content' in common
    assert '{% if header_content %}{{ header_content }}{% endif %}' in common
    assert registry.index('header_content=worker_status') < registry.index(
        '<form id="artifact-registry-analytics-filter"'
    )
    assert registry.count('include "artifact_registry/partials/_analytics_collect_live_state.html"') == 1
    assert 'Collect Analytics Data' not in registry
    assert 'Configure Collection' not in registry
    assert 'hx-post=' not in registry
    assert 'action_button' not in registry
    assert 'hx-trigger="every 1s"' in live
    assert 'progress_bar.job_progress(' in live
    assert '{% if readiness.is_active %}' in registry
    assert "url_for('artifact_registry.analytics_materialization_resolve', section=analytics.active_tab" in page
    assert 'provider_id=analytics.selected_provider_id' in page
    assert 'snapshot_window=analytics.snapshot_window' in page
    assert 'hx-trigger="load once"' in page
    assert 'hx-indicator="#artifact-registry-analytics-refresh-indicator"' in page
    assert 'hx-select="#artifact-registry-analytics-page"' in page
    assert 'artifactRegistryAnalyticsMaterializationFinished from:body' in page


def test_registry_analytics_guide_explains_committed_source_and_history_boundaries() -> None:
    from jinja2 import Environment

    controls = (ROOT / 'app/templates/artifact_registry/partials/_analytics_controls_readiness.html').read_text()
    shared = (ROOT / 'app/templates/analytics/components/_controls_readiness.html').read_text()
    guide = (ROOT / 'app/templates/components/info_tip.html').read_text()
    Environment().parse(controls)

    assert '{% import "components/info_tip.html" as info_tip %}' in controls
    assert "info_tip.render('registry-analytics-controls-guide'," in controls
    assert "variant='guide'" in controls
    assert 'title_accessory=analytics_controls_guide' in controls
    assert 'macro frame(title, description, icon, indicator_id,' in shared
    assert "title_accessory=''" in shared
    assert 'data-kaori-info-tip-trigger' in guide
    assert 'Time Range selects a qualified analytics snapshot.' in controls
    assert 'Current (Instant) is not historical telemetry.' in controls
    assert 'Stale committed evidence remains readable but is not current.' in controls
    assert 'registered Analytics JobExecution workflow' in controls
    assert 'Normal page reads use committed KAORI state' in controls

    # Guide is read-only: never add an independent collection control or
    # substitute for the registered worker materialization boundary.
    assert 'hx-post=' not in controls
    assert 'Collect Analytics Data' not in controls
    assert 'Configure Collection' not in controls


def test_kubernetes_and_registry_render_shared_readiness_without_duplicate_shells() -> None:
    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader(str(ROOT / 'app/templates')))
    env.filters['user_datetime'] = lambda value, default='Unavailable': str(value or default)
    env.globals['url_for'] = lambda endpoint, **kwargs: f'/{endpoint.replace(".", "/")}'

    kubernetes = env.from_string(
        """
        {% import "kubernetes/analytics/components/_analysis_workspace.html" as controls %}
        {% call controls.controls_readiness(
            'Capacity Controls & Data Readiness',
            'Worker-backed analysis and committed snapshot.',
            'sliders-horizontal',
            'capacity-refresh-indicator',
            {'status_label': 'Waiting for Cluster'}
        ) %}
            <span>Cluster selector remains rendered</span>
        {% endcall %}
        """
    ).render()
    assert kubernetes.count('data-analytics-controls-readiness') == 1
    assert 'Cluster selector remains rendered' in kubernetes
    assert 'Metrics Source Status' in kubernetes
    assert 'Latest Data Snapshot' in kubernetes
    assert 'Capacity Controls & Data Readiness' in kubernetes

    registry = env.get_template('artifact_registry/partials/_analytics_controls_readiness.html').render(
        analytics={
            'active_tab': 'overview',
            'provider_options': [],
            'selected_provider_id': None,
            'snapshot_window': '24h',
            'alert_filters': {},
            'data_readiness': {
                'eligible_count': 1,
                'registered_count': 1,
                'covered_count': 1,
                'current_count': 1,
                'label': 'Current Snapshot',
                'tone': 'normal',
                'latest_generated_at': None,
                'latest_expiry_at': None,
                'last_attempt_label': 'Never',
                'helper': 'Current committed evidence.',
                'is_active': False,
                'execution_tone': 'normal',
                'collection_warning': None,
            },
        }
    )
    assert registry.count('data-analytics-controls-readiness') == 1
    assert 'Registry Source Status' in registry
    assert 'Latest Analytics Data Snapshot' in registry
    assert 'Analytics Controls & Data Readiness' in registry
    # The conditional belongs to Jinja source, not the rendered HTML output.
    registry_source = (ROOT / 'app/templates/artifact_registry/partials/_analytics_controls_readiness.html').read_text()
    assert "eyebrow='Analytics Overview' if analytics.active_tab == 'overview'" in registry_source
    assert 'Analytics Overview' in registry
    assert 'data-kaori-info-tip-variant="guide"' in registry
    assert 'registry-analytics-controls-guide-tooltip' in registry
    assert 'Registry Analytics Controls Guide' in registry
    assert 'Collect Analytics Data' not in registry
    assert 'Configure Collection' not in registry


def test_registry_analytics_scope_and_committed_measured_range_are_real_filters() -> None:
    from types import SimpleNamespace

    import pytest
    from werkzeug.exceptions import NotFound

    from app.artifact_registry.analytics_job_adapter import (
        analytics_snapshot_matches_window,
        normalize_registry_analytics_window,
    )
    from app.artifact_registry.presentation_analytics import _registry_analytics_scope

    identities = [SimpleNamespace(id=4), SimpleNamespace(id=9)]
    assert _registry_analytics_scope(4, identities) == 4
    assert _registry_analytics_scope(9, identities) == 9
    with pytest.raises(NotFound):
        _registry_analytics_scope(999, identities)
    assert _registry_analytics_scope(None, identities) == 4
    assert _registry_analytics_scope(None, []) is None
    ready_first = [
        SimpleNamespace(id=4, readiness_status='blocked'),
        SimpleNamespace(id=9, readiness_status='ready'),
    ]
    assert _registry_analytics_scope(None, ready_first) == 9
    assert _registry_analytics_scope(4, ready_first) == 4
    with pytest.raises(NotFound):
        _registry_analytics_scope(999, ready_first)

    assert normalize_registry_analytics_window('bogus') == '24h'
    assert normalize_registry_analytics_window('current') == 'current'
    for value in ('1h', '6h', '12h', '24h', '7d', '30d', '60d'):
        assert normalize_registry_analytics_window(value) == value
        assert analytics_snapshot_matches_window(SimpleNamespace(time_range=value), value)
        assert not analytics_snapshot_matches_window(SimpleNamespace(time_range='current'), value)
    assert analytics_snapshot_matches_window(SimpleNamespace(time_range='current'), 'current')

    readiness_source = (ROOT / 'app/artifact_registry/analytics_job_adapter.py').read_text()
    assert 'Historical Materialization Required' in readiness_source
    assert 'RegistryAnalyticsSnapshot.time_range == normalized_window' in readiness_source


def test_registry_analytics_selector_renders_only_explicit_registry_sources() -> None:
    from types import SimpleNamespace

    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader(str(ROOT / 'app/templates')))
    env.filters['user_datetime'] = lambda value, default='Unavailable': str(value or default)
    env.globals['url_for'] = lambda endpoint, **kwargs: f'/{endpoint.replace(".", "/")}'
    source_options = [
        SimpleNamespace(id=4, name='Harbor X300'),
        SimpleNamespace(id=9, name='Harbor X400'),
    ]
    page = {
        'active_tab': 'overview',
        'provider_options': source_options,
        'selected_provider_id': 9,
        'snapshot_window': '24h',
        'alert_filters': {},
        'data_readiness': {
            'eligible_count': 1,
            'registered_count': 1,
            'covered_count': 1,
            'current_count': 1,
            'label': 'Current Snapshot',
            'tone': 'normal',
            'latest_generated_at': None,
            'latest_expiry_at': None,
            'last_attempt_label': 'Never',
            'helper': 'Current evidence.',
            'is_active': False,
            'execution_tone': 'normal',
            'collection_warning': None,
        },
    }
    html = env.get_template('artifact_registry/partials/_analytics_controls_readiness.html').render(analytics=page)
    assert 'All Registries' not in html
    assert 'Harbor X300' in html and 'Harbor X400' in html
    selector = html.split('id="artifact-registry-analytics-provider"', 1)[1].split('</select>', 1)[0]
    assert selector.count('<option') == 2
    assert '<option value=""' not in selector
    assert 'value="9"' in selector and 'selected' in selector

    # Without registered sources, the control declares unavailability, not
    # an implicit All Registries or a widened committed query.
    page['provider_options'] = []
    page['selected_provider_id'] = None
    empty = env.get_template('artifact_registry/partials/_analytics_controls_readiness.html').render(analytics=page)
    assert 'No Registries Available' in empty
    assert 'All Registries' not in empty


def test_registry_analytics_risk_copy_stays_compact_without_changing_risk_semantics() -> None:
    from app.artifact_registry.presentation_analytics import _analytics_summary_cards

    aggregate = {'total_size_bytes': 1024, 'artifacts': 3, 'running_artifacts': 1}
    growth = {'size_per_day': 0, 'artifacts_per_day': 0, 'runtime_usage_percent': 33.3}
    cards = _analytics_summary_cards(aggregate, growth_rows=[], growth=growth, risk_candidate_count=1)
    risk = next(card for card in cards if card['label'] == 'Risk Candidates')
    assert risk['value'] == '1'
    assert risk['tone'] == 'warning'
    assert risk['detail'] == 'Cross-domain signals may overlap.'
    assert len(risk['detail']) <= 36


def test_registry_analytics_selector_preserves_scope_through_routes_and_alerts() -> None:
    routes = (ROOT / 'app/artifact_registry/routes.py').read_text()
    presentation = (ROOT / 'app/artifact_registry/presentation_analytics.py').read_text()
    shell = (ROOT / 'app/templates/artifact_registry/analytics.html').read_text()
    section = (ROOT / 'app/templates/artifact_registry/partials/_analytics_section.html').read_text()
    controls = (ROOT / 'app/templates/artifact_registry/partials/_analytics_controls_readiness.html').read_text()

    # A single fail-closed parser now owns explicit Registry provider scope.
    assert "value = request.args.get('provider_id')" in routes
    assert 'if not value.isascii() or not value.isdecimal() or len(value) > 18:' in routes
    assert 'if int(value) <= 0:' in routes
    assert routes.count('provider_id=_analytics_provider_id()') >= 3
    assert 'provider_id = _analytics_provider_id()' in routes
    assert routes.count("snapshot_window=request.args.get('snapshot_window', '24h', type=str)") >= 3
    assert 'analytics = build_analytics_shell(' in routes
    assert "'alert_search': request.args.get('alert_q', '', type=str)" in routes
    assert "'alert_page': request.args.get('alert_page', 1, type=int) or 1" in routes
    assert 'snapshot_window=window, **alert_params' in routes
    assert 'should_request_registry_analytics_materialization(' in routes
    assert 'build_registry_analytics_readiness(provider_id=provider_id, snapshot_window=window)' in routes
    # Legacy analytics redirects must retain all independently selected filters.
    redirect_args = routes.split('alert_args: dict[str, Any] = {', 1)[1]
    redirect_args = redirect_args.split('return redirect(', 1)[0]
    for query_key in ('provider_id', 'snapshot_window', 'alert_q'):
        assert f"'{query_key}'," in redirect_args
    assert 'selected_provider_id = _registry_analytics_scope(provider_id, identities)' in presentation
    assert 'bundle = _collect_analytics_rows(identities, snapshot_window=selected_window)' in presentation
    assert 'analytics_snapshot_matches_window(snapshot, snapshot_window)' in presentation
    assert 'selected_provider_id' in presentation
    assert 'snapshot_window' in presentation
    assert 'hx-push-url="true"' in controls
    assert 'action="{{ url_for(page_endpoint) }}"' in controls
    assert 'provider_id=analytics.selected_provider_id' in shell
    assert 'snapshot_window=analytics.snapshot_window' in shell
    assert "snapshot_window: str = '24h'" in presentation
    assert "request.args.get('snapshot_window', '24h', type=str)" in routes
    # djLint may split hidden field attributes over multiple lines.
    section_fields = ' '.join(section.split())
    assert 'name="provider_id" value="{{ analytics.selected_provider_id or \'\' }}"' in section_fields
    assert 'name="snapshot_window" value="{{ analytics.snapshot_window }}"' in section_fields
    assert "'snapshot_window': analytics.snapshot_window" in section
    assert 'artifact-registry-analytics-collect-live-state' not in controls
    assert "header_content=worker_status if readiness.is_active else ''" in controls


def test_registry_analytics_explicit_provider_scope_parser_fails_closed() -> None:
    import pytest
    from flask import Flask
    from werkzeug.exceptions import NotFound

    from app.artifact_registry.routes import _analytics_provider_id

    flask_app = Flask(__name__)
    with flask_app.test_request_context('/analytics'):
        assert _analytics_provider_id() is None

    for malformed in ('0', '-1', 'abc', '1a', '1.2', '1234567890123456789', '６'):
        with flask_app.test_request_context('/analytics', query_string={'provider_id': malformed}):
            with pytest.raises(NotFound):
                _analytics_provider_id()

    for value, expected in (('1', 1), ('42', 42), ('0002', 2)):
        with flask_app.test_request_context('/analytics', query_string={'provider_id': value}):
            assert _analytics_provider_id() == expected


def test_registry_analytics_materialization_is_bounded_and_worker_owned() -> None:
    routes = (ROOT / 'app/artifact_registry/routes.py').read_text()
    adapter = (ROOT / 'app/artifact_registry/analytics_job_adapter.py').read_text()
    presenter = (ROOT / 'app/artifact_registry/presentation_analytics.py').read_text()
    job_catalog = (ROOT / 'app/definitions/catalogs/platform_operations/jobs/registered_jobs.yaml').read_text()

    assert "@artifact_registry_bp.get('/analytics/materialization/resolve')" in routes
    assert "@permission_required('artifact_registry.view')" in routes
    # Materialization is guarded by source + measured-window readiness.
    materialization_guard = routes.split('if should_request_registry_analytics_materialization(', 1)[1]
    materialization_guard = materialization_guard.split('):', 1)[0]
    assert (
        'build_registry_analytics_readiness(provider_id=provider_id, snapshot_window=window)' in materialization_guard
    )
    assert 'dispatch_registered_job(' in routes
    assert "trigger_type='on_demand'" in routes
    assert "job_key='artifact_registry.analytics.materialize'" in routes
    assert 'requested_by_user_id=None' in routes
    assert 'JobWorkerUnavailable' in routes
    assert 'JobQuotaExceeded' in routes
    assert 'rollback_registry_analytics_materialization_dispatch()' in routes
    rollback = adapter.split('def rollback_registry_analytics_materialization_dispatch() -> None:', 1)[1]
    rollback = rollback.split('\ndef ', 1)[0]
    assert 'db.session.rollback()' in rollback
    assert 'db.session.rollback()' not in routes
    assert "'Cache-Control'] = 'no-store, max-age=0'" in routes
    assert "@artifact_registry_bp.post('/analytics/collect')" not in routes
    assert 'get_registry_analytics_job(public_id)' in routes
    assert 'artifactRegistryAnalyticsMaterializationFinished' in routes
    assert "'artifact_registry/partials/_analytics_controls_readiness.html'" in routes
    assert 'def should_request_registry_analytics_materialization(' in adapter
    assert 'timedelta(minutes=5)' in adapter
    assert "'latest_attempt_at': latest.created_at if latest else None" in adapter
    assert 'require_registered_worker=True' in adapter
    assert "queue_name='analytics-batch'" in adapter
    assert 'JobPolicy.query.filter_by(job_key=ANALYTICS_JOB_KEY).first()' in adapter
    assert 'get_or_create_job_policy(' not in adapter
    assert 'RegistryAnalyticsSnapshot.query' in adapter
    assert 'present_job_execution(active)' in adapter
    assert 'build_registry_analytics_readiness(' in presenter
    assert 'MetricsConsumer' not in presenter
    assert 'queue_name: analytics-batch' in job_catalog
    assert 'key: artifact_registry.analytics.materialize' in job_catalog


def test_registry_analytics_posture_classifies_missing_partial_and_current_snapshots() -> None:
    from app.artifact_registry.analytics_job_adapter import _analytics_snapshot_posture

    assert _analytics_snapshot_posture(eligible_count=0, covered_count=0, current_count=0)[0] == 'Blocked'
    assert _analytics_snapshot_posture(eligible_count=2, covered_count=0, current_count=0)[0] == 'Not Materialized'
    assert _analytics_snapshot_posture(eligible_count=2, covered_count=2, current_count=2)[0] == 'Current Snapshot'
    assert _analytics_snapshot_posture(eligible_count=3, covered_count=2, current_count=1)[0] == 'Partial Coverage'
    assert _analytics_snapshot_posture(eligible_count=2, covered_count=2, current_count=0)[0] == 'Stale Snapshot'


def test_registry_analytics_auto_collection_cooldown_and_evidence_checks() -> None:
    from datetime import UTC, datetime, timedelta

    from app.artifact_registry.analytics_job_adapter import (
        should_request_registry_analytics_materialization,
    )

    now = datetime(2026, 10, 10, 12, tzinfo=UTC)
    defaults = {
        'eligible_count': 2,
        'current_count': 0,
        'is_active': False,
        'latest_attempt_at': None,
    }
    assert should_request_registry_analytics_materialization(defaults, now=now)
    assert not should_request_registry_analytics_materialization({**defaults, 'eligible_count': 0}, now=now)
    assert not should_request_registry_analytics_materialization({**defaults, 'current_count': 2}, now=now)
    assert not should_request_registry_analytics_materialization({**defaults, 'is_active': True}, now=now)
    assert not should_request_registry_analytics_materialization(
        {**defaults, 'latest_attempt_at': now - timedelta(minutes=2)}, now=now
    )
    assert should_request_registry_analytics_materialization(
        {**defaults, 'latest_attempt_at': now - timedelta(minutes=6)}, now=now
    )
    assert not should_request_registry_analytics_materialization(
        {**defaults, 'latest_attempt_at': (now - timedelta(minutes=2)).replace(tzinfo=None)},
        now=now,
    )


def test_registry_alert_source_is_worker_materialized_and_provider_neutral() -> None:
    analytics = (ROOT / 'app/artifact_registry/analytics.py').read_text()
    presentation = (ROOT / 'app/artifact_registry/presentation_analytics.py').read_text()
    routes = (ROOT / 'app/artifact_registry/routes.py').read_text()
    definition = (
        ROOT / 'app/definitions/catalogs/integrations/observability/alert_source/providers/alertmanager.yaml'
    ).read_text()

    assert 'asset_type: registry_instance' in definition
    assert 'profile_key: registry-alerts-v1' in definition
    assert "scope_type='registry_instance'" in analytics
    assert 'list_alerts_for_scope(' in analytics
    assert 'ACTIVE_ALERTS_EXPRESSION' in analytics
    # The alert source and fallback rows are committed into the snapshot payload.
    assert 'alerts = _alert_evidence(identity)' in analytics
    assert "'alerts': alerts" in analytics
    assert 'snapshot.payload_json = payload' in analytics

    assert 'list_alerts_for_scope' not in presentation
    assert 'list_alerts_for_scope' not in routes
    assert 'MetricsConsumer' not in routes
    assert "@artifact_registry_bp.get('/analytics/alerts/table')" in routes


def test_registry_alert_workspace_reuses_committed_alert_evidence_contract() -> None:
    template = (ROOT / 'app/templates/artifact_registry/partials/_analytics_section.html').read_text()
    overview_tabs = (ROOT / 'app/templates/artifact_registry/partials/_analytics_overview_workspace.html').read_text()
    overview_panel = (ROOT / 'app/templates/artifact_registry/partials/_analytics_overview_panel.html').read_text()
    assert "('alerts', 'Alerts', 'triangle-alert')" in overview_tabs
    assert "url_for('artifact_registry.analytics_' ~ overview_domain" in overview_panel
    assert 'Alertmanager is primary. Metrics Source is fallback evidence.' in template
    assert 'committed Analytics materialization' in template
    assert 'alert_per_page' in template
    assert '[5, 10, 25, 50]' in template
    assert "url_for('artifact_registry.analytics_alerts_table')" in template


def test_registry_capacity_outlook_table_reuses_canonical_primitives() -> None:
    """Keep the materialized forecast content while reusing shared table geometry."""
    from jinja2 import Environment

    template = (ROOT / 'app/templates/artifact_registry/partials/_analytics_section.html').read_text(encoding='utf-8')
    # Verify the real owning template parses, without requiring a live Registry provider.
    Environment().parse(template)
    capacity = template.split("{% elif analytics.active_tab == 'capacity' %}", 1)[1].split(
        "{% elif analytics.active_tab == 'usage' %}", 1
    )[0]
    shared = (ROOT / 'app/templates/components/table_primitives.html').read_text(encoding='utf-8')

    for macro in (
        'table_classes',
        'head_classes',
        'header_cell_classes',
        'body_classes',
        'row_classes',
        'cell_classes',
    ):
        assert f'macro {macro}(' in shared
    assert '{% import "components/table_primitives.html" as table_ui %}' in template
    assert "table_ui.table_classes('min-w-[760px]')" in capacity
    assert 'table_ui.head_classes()' in capacity
    assert capacity.count('table_ui.header_cell_classes()') == 5
    assert capacity.count('scope="col"') == 5
    assert 'table_ui.body_classes()' in capacity
    assert 'table_ui.row_classes()' in capacity
    assert capacity.count('table_ui.cell_classes()') == 6
    assert 'overflow-x-auto' in capacity
    assert '<table class="min-w-full divide-y divide-outline-subtle text-sm">' not in capacity
    assert '<th class="px-4 py-3">' not in capacity

    for label in ('Registry / Project', 'Usage / Quota', 'Utilization', 'Growth', 'Forecast'):
        assert f'>{label}</th>' in capacity
    for value in (
        'row.project_name',
        'row.registry_name',
        'row.usage_display',
        'row.quota_display',
        'row.utilization_display',
        'row.growth_display',
        "table_label.status_indicator_label(row.days_to_quota_display, 'info')",
    ):
        assert value in capacity
    assert 'analytics.forecast_rows[:5]' in capacity
    assert 'colspan="5"' in capacity
    assert 'No qualified project quota forecast is available.' in capacity
    assert 'analytics.capacity_outlook.nearest_quota_days' in capacity
    assert 'analytics.capacity_outlook.quota_headroom_display' in capacity
