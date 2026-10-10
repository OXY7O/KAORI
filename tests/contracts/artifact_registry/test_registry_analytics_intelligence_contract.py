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


def test_registry_analytics_workspace_is_reusable_and_intelligence_bounded() -> None:
    shell = (ROOT / 'app/templates/artifact_registry/analytics.html').read_text()
    section = (ROOT / 'app/templates/artifact_registry/partials/_analytics_section.html').read_text()
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
        assert f"'artifact_registry.analytics_{tab}'" in shell
        assert f"'{tab}'" in presentation

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

    assert "{% macro frame(" in common
    assert 'analysis_surface.snapshot_shell_classes()' in common
    assert 'analysis_surface.snapshot_header_icon_classes()' in common
    assert 'loading_bar.render(indicator_id, active=loading' in common
    assert "{% macro snapshot_card(" in common
    assert "{% macro source_card(" in common
    assert 'shared_readiness.frame(title, description, icon, indicator_id' in k8s
    assert 'shared_readiness.snapshot_card(' in k8s
    assert 'shared_readiness.frame(' in registry
    assert 'shared_readiness.source_card(' in registry
    assert 'shared_readiness.snapshot_card(' in registry
    assert 'Analytics Controls & Data Readiness' in registry
    assert 'Registry Scope' in registry
    assert 'Analysis Window' in registry
    assert 'All Eligible Registry Providers' in registry
    assert 'Current Committed Snapshot' in registry
    assert 'loading=readiness.is_active' in registry
    assert 'Collect Analytics Data' not in registry
    assert 'Configure Collection' not in registry
    assert 'hx-post=' not in registry
    assert 'action_button' not in registry
    assert 'hx-trigger="every 1s"' in live
    assert 'progress_bar.job_progress(' in live
    assert "{% if readiness.is_active %}" in registry
    assert "hx-get=\"{{ url_for('artifact_registry.analytics_materialization_resolve') }}\"" in page
    assert 'hx-trigger="load once"' in page
    assert 'hx-indicator="#artifact-registry-analytics-refresh-indicator"' in page
    assert 'hx-select="#artifact-registry-analytics-page"' in page
    assert 'artifactRegistryAnalyticsMaterializationFinished from:body' in page


def test_registry_analytics_materialization_is_bounded_and_worker_owned() -> None:
    routes = (ROOT / 'app/artifact_registry/routes.py').read_text()
    adapter = (ROOT / 'app/artifact_registry/analytics_job_adapter.py').read_text()
    presenter = (ROOT / 'app/artifact_registry/presentation_analytics.py').read_text()
    job_catalog = (
        ROOT / 'app/definitions/catalogs/platform_operations/jobs/registered_jobs.yaml'
    ).read_text()

    assert "@artifact_registry_bp.get('/analytics/materialization/resolve')" in routes
    assert "@permission_required('artifact_registry.view')" in routes
    assert "should_request_registry_analytics_materialization(readiness)" in routes
    assert "dispatch_registered_job(" in routes
    assert "trigger_type='on_demand'" in routes
    assert "job_key='artifact_registry.analytics.materialize'" in routes
    assert "requested_by_user_id=None" in routes
    assert "JobWorkerUnavailable" in routes
    assert "JobQuotaExceeded" in routes
    assert "db.session.rollback()" in routes
    assert "'Cache-Control'] = 'no-store, max-age=0'" in routes
    assert "@artifact_registry_bp.post('/analytics/collect')" not in routes
    assert "get_registry_analytics_job(public_id)" in routes
    assert "artifactRegistryAnalyticsMaterializationFinished" in routes
    assert "'artifact_registry/partials/_analytics_controls_readiness.html'" in routes
    assert "def should_request_registry_analytics_materialization(" in adapter
    assert "timedelta(minutes=5)" in adapter
    assert "'latest_attempt_at': latest.created_at if latest else None" in adapter
    assert "require_registered_worker=True" in adapter
    assert "queue_name='analytics-batch'" in adapter
    assert "JobPolicy.query.filter_by(job_key=ANALYTICS_JOB_KEY).first()" in adapter
    assert "get_or_create_job_policy(" not in adapter
    assert "RegistryAnalyticsSnapshot.query" in adapter
    assert "present_job_execution(active)" in adapter
    assert "build_registry_analytics_readiness()" in presenter
    assert "MetricsConsumer" not in presenter
    assert "queue_name: analytics-batch" in job_catalog
    assert "key: artifact_registry.analytics.materialize" in job_catalog


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
    assert not should_request_registry_analytics_materialization(
        {**defaults, 'eligible_count': 0}, now=now
    )
    assert not should_request_registry_analytics_materialization(
        {**defaults, 'current_count': 2}, now=now
    )
    assert not should_request_registry_analytics_materialization(
        {**defaults, 'is_active': True}, now=now
    )
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
    assert "'alerts': state.alerts" in analytics

    assert 'list_alerts_for_scope' not in presentation
    assert 'list_alerts_for_scope' not in routes
    assert 'MetricsConsumer' not in routes
    assert "@artifact_registry_bp.get('/analytics/alerts/table')" in routes


def test_registry_alert_workspace_reuses_committed_alert_evidence_contract() -> None:
    template = (ROOT / 'app/templates/artifact_registry/partials/_analytics_section.html').read_text()
    shell = (ROOT / 'app/templates/artifact_registry/analytics.html').read_text()

    assert "'artifact_registry.analytics_alerts'" in shell
    assert 'Alertmanager is primary. Metrics Source is fallback evidence.' in template
    assert 'committed Analytics materialization' in template
    assert 'alert_per_page' in template
    assert '[5, 10, 25, 50]' in template
    assert "url_for('artifact_registry.analytics_alerts_table')" in template
