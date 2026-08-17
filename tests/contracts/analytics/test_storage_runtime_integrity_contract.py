from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_storage_runtime_has_explicit_evidence_domain_and_presentation_ownership() -> None:
    service = read('app/analytics/kubernetes/storage/service.py')
    evidence = read('app/analytics/kubernetes/storage/evidence.py')
    domain = read('app/analytics/kubernetes/storage/domain.py')
    presentation = read('app/analytics/kubernetes/storage/presentation.py')

    assert 'class StorageEvidenceCollector' in evidence
    assert 'def build_storage_payload' in domain
    assert 'def build_storage_posture' in domain
    assert 'def present_storage_materialized_context' in presentation
    assert 'StorageAnalysisService.__new__' not in service
    assert 'get_storage_capacity_summary' not in service


def test_storage_collector_queries_each_canonical_signal_once() -> None:
    evidence = read('app/analytics/kubernetes/storage/evidence.py')
    query_profile = read('app/integrations/observability/metrics_source/query_profiles/kubernetes_v1.py')

    assert 'PVC_CAPACITY_BY_CLAIM_QUERY' in evidence
    assert 'max by (namespace, persistentvolumeclaim)' in query_profile
    for legacy in (
        'PVC_REQUESTED_TOTAL_QUERY',
        'PVC_USED_TOTAL_QUERY',
        'PVC_AVAILABLE_TOTAL_QUERY',
        'PVC_COUNT_QUERY',
        'PV_CAPACITY_QUERY',
        'PV_COUNT_QUERY',
        'PV_RECLAIM_POLICY_QUERY',
    ):
        assert legacy not in query_profile


def test_storage_partial_endpoints_are_htmx_only_and_not_cacheable() -> None:
    routes = read('app/analytics/kubernetes/storage/routes.py')

    assert "request.headers.get('HX-Request'" in routes
    assert "return redirect(_full_storage_url('filesystem'))" in routes
    assert 'return redirect(_full_storage_url(selected_tab))' in routes
    assert "response.headers['Cache-Control'] = 'no-store, max-age=0'" in routes
    assert "response.headers['Vary'] = 'HX-Request'" in routes


def test_storage_filters_preserve_tab_and_lazy_urls_preserve_local_state() -> None:
    controls = read('app/templates/analytics/kubernetes/storage/partials/_controls_readiness.html')
    section = read('app/templates/analytics/kubernetes/storage/partials/_storage_section.html')

    assert 'data-analytics-preserve-tab' in controls
    assert 'filesystem_page=storage_summary.node_filesystem.pagination.page' in section
    assert 'pvc_search=selected_pvc_search' in section
    assert 'pvc_page=storage_summary.persistent_storage.pvc_pagination.page' in section
    assert 'pv_search=selected_pv_search' in section
    assert 'pv_page=storage_summary.persistent_storage.pv_pagination.page' in section


def test_storage_templates_render_domain_status_without_local_threshold_logic() -> None:
    paths = (
        'app/templates/analytics/kubernetes/storage/partials/_hero.html',
        'app/templates/analytics/kubernetes/storage/partials/_overview.html',
        'app/templates/analytics/kubernetes/storage/partials/_capacity_utilization_panel.html',
    )
    for path in paths:
        source = read(path)
        assert '>= 90' not in source, path
        assert '>= 75' not in source, path
        assert 'pressure_tone(' not in source, path
    assert 'table_label.status_label(posture.label' in read(
        'app/templates/analytics/kubernetes/storage/partials/_overview.html'
    )


def test_pvc_ui_and_report_use_observed_capacity_as_pressure_denominator() -> None:
    pvc = read('app/templates/analytics/kubernetes/storage/partials/_persistent_volume_claims_panel.html')
    report = read('app/reports/export/html_pdf/storage_analysis.py')

    assert 'of observed capacity' in pvc
    assert 'row.used }} / {{ row.capacity' in pvc
    assert 'of requested' not in pvc
    assert "'boundary': 'Observed Volume Capacity'" in report
