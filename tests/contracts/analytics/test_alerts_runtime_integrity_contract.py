from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_snapshot_dimensions_exclude_local_record_controls() -> None:
    routes = read('app/analytics/kubernetes/alerts/routes.py')
    snapshot_parameters = routes.split('def _snapshot_parameters', 1)[1].split('def _present', 1)[0]

    assert "'source': normalize_option(" in snapshot_parameters
    assert 'allowed=SOURCE_OPTIONS' in snapshot_parameters
    assert "request.args.get('cluster_id'" in snapshot_parameters
    for local_parameter in (
        'severity',
        'status',
        'namespace',
        'search',
        'alerts_page',
        'anomalies_page',
        'alerts_per_page',
        'anomalies_per_page',
        'tab',
    ):
        assert f"request.args.get('{local_parameter}'" not in snapshot_parameters


def test_fragment_transport_is_htmx_only_and_no_store() -> None:
    routes = read('app/analytics/kubernetes/alerts/routes.py')

    assert "request.headers.get('HX-Request', '').lower() == 'true'" in routes
    assert "return redirect(_full_page_url('alerts'))" in routes
    assert "return redirect(_full_page_url('anomalies'))" in routes
    assert "response.headers['Cache-Control'] = 'no-store, max-age=0'" in routes
    assert "response.headers['Vary'] = 'HX-Request'" in routes
    assert "response.headers['HX-Push-Url'] = _full_page_url(tab)" in routes


def test_alert_and_anomaly_pagination_state_is_independent() -> None:
    routes = read('app/analytics/kubernetes/alerts/routes.py')
    alerts_table = read('app/templates/analytics/kubernetes/alerts/partials/_alerts_table.html')
    anomalies_table = read('app/templates/analytics/kubernetes/alerts/partials/_anomalies_table.html')
    filters = read('app/templates/analytics/kubernetes/alerts/partials/_table_filters.html')

    assert "request.args.get('alerts_page', '1')" in routes
    assert "request.args.get('anomalies_page', '1')" in routes
    assert "'alerts_page', 'alerts_per_page'" in alerts_table
    assert "'anomalies_page', 'anomalies_per_page'" in anomalies_table
    assert "'alerts_page' if is_alert_table else 'anomalies_page'" in filters
    assert 'name="page"' not in alerts_table + anomalies_table + filters


def test_alert_queries_deduplicate_and_scope_anomalies_to_active_pods() -> None:
    profile = read('app/integrations/observability/metrics_source/query_profiles/kubernetes_v1.py')
    alert_queries = read('app/integrations/observability/metrics_source/query_profiles/alerts_v1.py')

    assert 'expression=alerts_v1.ACTIVE_ALERTS_EXPRESSION' in profile
    assert 'expression=alerts_v1.POD_RESTART_ANOMALY_QUERY' in profile
    assert 'expression=alerts_v1.POD_NOT_READY_ANOMALY_QUERY' in profile
    assert 'ALERTS{alertstate=~"pending|firing"}' in alert_queries
    assert 'max by (namespace, pod, container)' in alert_queries
    assert 'phase=~"Pending|Running"' in alert_queries
    assert 'and on (namespace, pod)' in alert_queries
    assert 'kube_pod_status_ready{condition="false"' in alert_queries


def test_source_normalization_and_deduplication_have_canonical_ownership() -> None:
    sources = read('app/analytics/kubernetes/alerts/sources.py')
    records = read('app/analytics/kubernetes/alerts/records.py')
    baseline = read('docs/architecture/code-health-debt-baseline.json')

    assert 'def normalize_alertmanager_item(' not in sources
    assert 'def normalize_prometheus_alert(' not in sources
    assert 'def filter_items(' not in sources
    assert 'def deduplicate_alerts(' in records
    assert "label.endswith('_replica')" in records
    assert "label.endswith('_replica_name')" in records
    assert "'alertstate'" in records
    assert 'strip().lower() == namespace_query' in records
    assert len(sources.splitlines()) <= 800
    assert 'app/analytics/kubernetes/alerts/sources.py::normalize_alertmanager_item' not in baseline


def test_anomaly_queries_fail_independently_and_expose_partial_evidence() -> None:
    anomalies = read('app/analytics/kubernetes/alerts/anomalies.py')

    assert 'def _query_anomaly_candidates(' in anomalies
    assert "signal_name='restart'" in anomalies
    assert "signal_name='readiness'" in anomalies
    assert "'available_queries': available_queries" in anomalies
    assert "'failed_queries': sorted(errors)" in anomalies
    assert 'One failed optional query no longer discards the successful signal family.' in anomalies


def test_local_record_filters_do_not_rewrite_global_page_posture() -> None:
    application = read('app/analytics/kubernetes/alerts/application.py')

    assert "global_summary = presented.get('summary')" in application
    assert "'record_summary': record_summary" in application
    assert "'all_alerts': raw_alerts" in application
    assert "'filtered_alerts': filtered_alerts" in application
    presentation = application.split('def present_alerts_materialized_context', 1)[1]
    assert 'alerts=raw_alerts' in presentation
    assert 'anomalies=raw_anomalies' in presentation


def test_report_reads_committed_snapshot_instead_of_live_providers() -> None:
    report = read('app/reports/export/payloads/alerts.py')

    assert "dataset_key='analytics.alerts'" in report
    assert "parameters={'cluster_id': cluster_id, 'source': 'auto'}" in report
    assert 'get_alerts_context(' not in report
    assert 'MetricsService(' not in report
    assert 'get_alertmanager_alerts' not in report
    assert "'committed_evidence_available': bool(context)" in report


def test_overview_does_not_present_incomplete_evidence_as_stable() -> None:
    snapshots = read('app/analytics/kubernetes/alerts/snapshots.py')
    overview = read('app/templates/analytics/kubernetes/overview/partials/_alerts_snapshot.html')

    assert "return 'Limited Evidence', 'unknown'" in snapshots
    assert "'evidence_complete': evidence_complete" in snapshots
    assert 'not alerts.evidence_complete|default(false)' in overview
    assert 'Restore Complete Signal Evidence' in overview


def test_alert_overview_fields_do_not_leak_into_workload_projection() -> None:
    overview = read('app/analytics/kubernetes/overview/service.py')
    workload_projection = overview.split('def _get_workload_snapshot', 1)[1].split(
        'def _get_top_consumers_snapshot', 1
    )[0]

    assert "'status': risk_meta['label']" in workload_projection
    assert "'tone': risk_meta['tone']" in workload_projection
    assert 'anomaly_evidence_partial' not in workload_projection
    assert 'evidence_complete' not in workload_projection


def test_signal_overview_cannot_report_normal_when_evidence_is_incomplete() -> None:
    signals = read('app/analytics/kubernetes/alerts/signals.py')
    application = read('app/analytics/kubernetes/alerts/application.py')

    assert 'if not evidence_complete:' in signals
    assert "'label': 'Limited Evidence'" in signals
    assert "'level': 'unknown'" in signals
    assert 'is_alert_evidence_complete(' in application
    assert 'evidence_complete=evidence_complete' in application


def test_incomplete_anomaly_evidence_cannot_generate_normal_baseline_recommendation() -> None:
    engine = read('app/intelligence/recommendation_engine.py')
    alerts_builder = engine.split('def build_alerts_actionable_recommendations', 1)[1].split(
        'def get_alerts_affected_resource_count', 1
    )[0]

    assert "title='Restore Complete Anomaly Evidence'" in alerts_builder
    assert "anomaly_source_status.get('partial', False)" in alerts_builder
    assert "not bool(anomaly_source_status.get('connected', False))" in alerts_builder
    assert 'and anomaly_evidence_incomplete' in alerts_builder
