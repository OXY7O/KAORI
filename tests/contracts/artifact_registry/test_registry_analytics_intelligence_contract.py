from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_registry_analytics_is_worker_materialized_and_page_reads_snapshot() -> None:
    analytics = (ROOT / 'app/artifact_registry/analytics.py').read_text()
    presentation = (ROOT / 'app/artifact_registry/presentation.py').read_text()
    routes = (ROOT / 'app/artifact_registry/routes.py').read_text()
    jobs = (
        ROOT / 'app/definitions/catalogs/platform_operations/jobs/registered_jobs.yaml'
    ).read_text()

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
    standard = (
        ROOT / 'docs/architecture/domain-intelligence-ownership-standard.md'
    ).read_text()
    assert 'Intelligence owns recommendation semantics' in standard
    assert 'Automation Control' in standard
    assert 'Direct Recommendation → provider mutation is not allowed.' in standard

def test_registry_scan_gap_recommendation_uses_usable_scan_evidence_semantics() -> None:
    evaluator = (ROOT / 'app/intelligence/registry_recommendations.py').read_text()
    rules = (ROOT / 'app/definitions/catalogs/intelligence/rules.yaml').read_text()

    assert 'from app.artifact_registry.security.contracts import registry_scan_evidence_ready' in evaluator
    assert "if not registry_scan_evidence_ready(artifact.scan_status):" in evaluator
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
    profile = (
        ROOT
        / 'app/integrations/observability/metrics_source/query_profiles/registry_harbor_v1.py'
    ).read_text()

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
    template = (
        ROOT / 'app/templates/artifact_registry/analytics.html'
    ).read_text()
    presentation = (ROOT / 'app/artifact_registry/presentation.py').read_text()
    routes = (ROOT / 'app/artifact_registry/routes.py').read_text()

    assert 'components/framed_workspace_tabs.html' in template
    assert 'framed_workspace_tabs.render_navigation' in template
    for section in (
        'Analytics Summary',
        'Analytics Workspace',
        'Registry Growth',
        'Capacity Outlook',
        'Artifact Usage',
        'Risk Concentration',
        'Governance Gaps',
        'Derived Insights',
        'Central Intelligence',
    ):
        assert section in template

    for tab in ('growth', 'capacity', 'usage', 'risk', 'governance', 'insights'):
        assert f"'{tab}'" in template
        assert f"'{tab}'" in presentation

    assert "active_tab=request.args.get('tab', 'growth', type=str)" in routes
    assert 'no request-time Harbor or Prometheus dependency' in template
    assert 'never auto-cleaned' in template
    assert 'recommendation lifecycle, Accepted Risk, escalation, and automation control remain centrally governed' in template
    assert "url_for('intelligence.recommendations', domain='registry')" in template

    assert "aggregate['inflight_requests'] > 100" not in presentation
    assert "aggregate['task_queue_size'] > 0" not in presentation

