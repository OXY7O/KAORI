from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_capacity_collects_each_required_signal_once_and_keeps_filesystem_optional() -> None:
    evidence = read('app/analytics/kubernetes/capacity/evidence.py')
    service = read('app/analytics/kubernetes/capacity/service.py')

    assert 'class CapacityEvidenceCollector' in evidence
    assert 'def collect(self, *, time_range: str)' in evidence
    assert 'def optional_scalar(self, query: str)' in evidence
    assert "required_capabilities=('instant_query',)" in evidence
    assert 'except PrometheusError:' in evidence
    assert 'filesystem_capacity=self.optional_scalar(NODE_FILESYSTEM_CAPACITY_QUERY)' in evidence
    assert 'evidence = self.evidence_collector.collect(time_range=time_range)' in service
    assert 'get_storage_capacity()' not in service
    assert 'get_storage_usage()' not in service
    assert 'get_storage_available()' not in service


def test_capacity_queries_use_ready_worker_boundary_for_every_schedulable_signal() -> None:
    profile = read('app/integrations/prometheus/query_profiles/kubernetes_v1.py')
    evidence = read('app/analytics/kubernetes/capacity/evidence.py')

    required_keys = (
        'CURRENT_WORKER_PODS_QUERY',
        'WORKER_CPU_USAGE_QUERY',
        'WORKER_MEMORY_USAGE_QUERY',
        'WORKER_CPU_REQUESTS_TOTAL_QUERY',
        'WORKER_CPU_LIMITS_TOTAL_QUERY',
        'WORKER_MEMORY_REQUESTS_TOTAL_QUERY',
        'WORKER_MEMORY_LIMITS_TOTAL_QUERY',
        'WORKER_CPU_PEAK_QUERY_TEMPLATE',
        'WORKER_MEMORY_PEAK_QUERY_TEMPLATE',
        'READY_WORKER_NODE_COUNT_QUERY',
        'WORKER_CPU_ALLOCATABLE_QUERY',
        'WORKER_MEMORY_ALLOCATABLE_QUERY',
        'WORKER_POD_ALLOCATABLE_QUERY',
    )
    for key in required_keys:
        definition = profile.split(f"'analytics.capacity.queries.{key}': QueryDefinition(", 1)[1].split('    ),', 1)[0]
        assert 'kube_node_status_condition{condition="Ready",status="true"}' in definition, key
        assert 'kube_node_role{role=~"control-plane|master"}' in definition, key
        assert key in evidence


def test_capacity_removes_unscoped_legacy_query_definitions() -> None:
    profile = read('app/integrations/prometheus/query_profiles/kubernetes_v1.py')

    removed = (
        'CURRENT_PODS_QUERY',
        'CPU_REQUESTS_TOTAL_QUERY',
        'CPU_LIMITS_TOTAL_QUERY',
        'MEMORY_REQUESTS_TOTAL_QUERY',
        'MEMORY_LIMITS_TOTAL_QUERY',
        'CPU_PEAK_QUERY_TEMPLATE',
        'MEMORY_PEAK_QUERY_TEMPLATE',
    )
    for key in removed:
        assert f"'analytics.capacity.queries.{key}'" not in profile


def test_capacity_capability_validation_includes_readiness_and_node_labels() -> None:
    capabilities = read('app/definitions/catalogs/integrations/prometheus.yaml')
    audit = read('app/integrations/prometheus/query_profiles/audit.py')

    capacity_block = capabilities.split('key: capacity_metrics', 1)[1].split('key: resource_requests_limits', 1)[0]
    assert 'kube_node_status_condition' in capacity_block
    assert "'kube_node_status_condition': {'node', 'condition', 'status'}" in audit
    requirement_block = audit.split('_RESOURCE_COMMITMENT_LABEL_REQUIREMENTS = {', 1)[1].split('\n}\n', 1)[0]
    assert "{'namespace', 'node', 'pod', 'resource', 'unit'}" in requirement_block


def test_capacity_domain_separates_schedulable_capacity_from_filesystem_reference() -> None:
    domain = read('app/analytics/kubernetes/capacity/domain.py')
    presenter = read('app/analytics/kubernetes/capacity/presentation.py')
    recommendation_engine = read('app/intelligence/recommendation_engine.py')

    assert "SCHEDULING_RESOURCES = ('cpu', 'memory', 'pods')" in domain
    assert "'scheduling_resource': False" in domain
    assert 'not Kubernetes allocatable capacity' in domain
    assert "if item['scheduling_resource'] and item['headroom'] is not None:" in presenter
    assert "item.get('scheduling_resource') is False" in recommendation_engine


def test_capacity_snapshot_and_filter_preserve_exact_evidence_semantics() -> None:
    service = read('app/analytics/kubernetes/capacity/service.py')
    controls = read('app/templates/analytics/kubernetes/capacity/partials/_controls_readiness.html')
    routes = read('app/analytics/kubernetes/capacity/routes.py')

    assert 'if not result.available:' in service
    assert "if item.get('evidence_available') is False:" in service
    assert "parameters.pop('tab', None)" in routes
    assert 'data-analytics-preserve-tab' in controls
    assert '<input type="hidden" name="tab"' in controls


def test_dashboard_capacity_adapter_preserves_unavailable_evidence() -> None:
    dashboard = read('app/dashboards/kubernetes/sections/capacity.py')

    assert "section.get('evidence_available') is not False" in dashboard
    assert "description='Ready-worker capacity evidence unavailable'" in dashboard
    assert 'used_percent=None' in dashboard
    assert 'headroom_percent=None' in dashboard


def test_capacity_presenter_and_domain_have_canonical_ownership() -> None:
    common = read('app/analytics/kubernetes/common/presentation.py')
    route = read('app/analytics/kubernetes/capacity/routes.py')
    service = read('app/analytics/kubernetes/capacity/service.py')

    assert 'def present_capacity_context' not in common
    assert 'from app.analytics.kubernetes.capacity.presentation import present_capacity_context' in route
    assert 'from app.analytics.kubernetes.capacity.domain import (' in service
    assert 'capacity_posture = build_capacity_posture(' in service
    assert len(read('app/analytics/kubernetes/capacity/service.py').splitlines()) < 800
