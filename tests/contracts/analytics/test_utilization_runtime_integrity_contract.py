import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def load_presentation_module():
    coercion = types.ModuleType('app.analytics.common.coercion')

    def safe_float(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    coercion.safe_float = safe_float
    coercion.safe_int = lambda value: int(round(safe_float(value)))
    module_names = ('app', 'app.analytics', 'app.analytics.common', 'app.analytics.common.coercion')
    previous = {name: sys.modules.get(name) for name in module_names}
    try:
        sys.modules['app'] = types.ModuleType('app')
        sys.modules['app.analytics'] = types.ModuleType('app.analytics')
        sys.modules['app.analytics.common'] = types.ModuleType('app.analytics.common')
        sys.modules['app.analytics.common.coercion'] = coercion
        spec = importlib.util.spec_from_file_location(
            'kaori_utilization_presentation_contract',
            ROOT / 'app/analytics/utilization/presentation.py',
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for name, value in previous.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value


PRESENTATION = load_presentation_module()
build_summary_presentation = PRESENTATION.build_summary_presentation
build_trend_options = PRESENTATION.build_trend_options
build_trend_presentation = PRESENTATION.build_trend_presentation


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def definition(source: str, key: str) -> str:
    start = source.index(f'    {key!r}: QueryDefinition(')
    next_definition = source.find("\n    '", start + 8)
    return source[start:] if next_definition == -1 else source[start:next_definition]


def complete_summary(**overrides):
    summary = {
        'cpu_usage': 2.0,
        'cpu_capacity': 8.0,
        'cpu_utilization': 25.0,
        'memory_usage': 8 * 1024**3,
        'memory_capacity': 32 * 1024**3,
        'memory_utilization': 25.0,
        'storage_usage': 100 * 1024**3,
        'storage_capacity': 500 * 1024**3,
        'storage_utilization': 20.0,
        'pod_count': 20,
        'pod_capacity': 110,
        'pod_utilization': 18.18,
    }
    summary.update(overrides)
    return summary


def test_initial_utilization_request_does_not_resolve_hidden_datasets() -> None:
    routes = read('app/analytics/utilization/routes.py')
    base_start = routes.index('def _base_context_or_state')
    base_end = routes.index("@permission_required('analytics.view')", base_start)
    base = routes[base_start:base_end]

    assert "dataset_key='analytics.utilization.summary'" not in base  # _PAGE owns the key
    assert 'analytics.utilization.trend' not in base
    assert 'analytics.utilization.node' not in base
    assert 'Trend and node datasets are intentionally not resolved here' in base


def test_summary_materialization_does_not_query_hidden_tab_payloads() -> None:
    source = read('app/analytics/utilization/materialization.py')
    start = source.index('def get_utilization_summary_context')
    end = source.index('def get_utilization_trend_context', start)
    summary_builder = source[start:end]

    assert 'service.get_node_names()' not in summary_builder
    assert 'service.get_worker_node_names()' not in summary_builder
    assert 'service.get_detail_summary(' not in summary_builder
    assert 'service.get_summary_table(' not in summary_builder
    assert "'available_nodes'" not in summary_builder
    assert "'available_worker_nodes'" not in summary_builder
    assert "'detail_summary'" not in summary_builder


def test_trend_window_labels_are_owned_by_python_presentation() -> None:
    template = read('app/templates/analytics/utilization/partials/_readiness_scope.html')
    options = build_trend_options((1, 24, 168, 720, 1440), 168)

    assert [option['label'] for option in options] == [
        'Last 1 Hour',
        'Last 24 Hours',
        'Last 7 Days',
        'Last 30 Days',
        'Last 60 Days',
    ]
    assert [option['value'] for option in options if option['selected']] == [168]
    assert 'trend_options' in template
    assert "{1: 'Last 1 Hour'" not in template


def test_fragment_routes_require_htmx_and_disable_cache() -> None:
    routes = read('app/analytics/utilization/routes.py')

    assert "request.headers.get('HX-Request') == 'true'" in routes
    assert "return _redirect_to_workspace(tab='trend')" in routes
    assert "return _redirect_to_workspace(tab='nodes')" in routes
    assert "response.headers['Cache-Control'] = 'no-store, max-age=0'" in routes
    assert "response.headers['Vary'] = 'HX-Request'" in routes


def test_worker_utilization_queries_use_allocatable_capacity_and_role_boundary() -> None:
    profile = read('app/integrations/prometheus/query_profiles/kubernetes_v1.py')

    for key in (
        'analytics.utilization.queries.CPU_CAPACITY',
        'analytics.utilization.queries.CPU_UTILIZATION',
        'analytics.utilization.queries.MEMORY_CAPACITY',
        'analytics.utilization.queries.MEMORY_UTILIZATION',
        'analytics.utilization.queries.POD_CAPACITY',
        'analytics.utilization.queries.POD_UTILIZATION',
    ):
        query = definition(profile, key)
        assert 'kube_node_status_allocatable' in query
        assert 'kube_node_status_capacity' not in query
        assert 'role=~"control-plane|master"' in query
        assert 'unless on(node)' in query

    for key in (
        'analytics.utilization.queries.CPU_UTILIZATION_BY_NODE',
        'analytics.utilization.queries.MEMORY_UTILIZATION_BY_NODE',
        'analytics.utilization.queries.POD_UTILIZATION_BY_NODE',
    ):
        query = definition(profile, key)
        assert 'kube_node_status_allocatable' in query
        assert 'kube_node_status_capacity' not in query
        assert 'unit=' in query


def test_overview_snapshot_adapter_preserves_missing_denominator_as_none() -> None:
    service = read('app/analytics/utilization/service.py')
    start = service.index('def get_utilization_snapshot(')
    snapshot_adapter = service[start:]

    assert 'if capacity_key not in summary or safe_float(summary.get(capacity_key)) <= 0' in snapshot_adapter
    assert "'cpu_percent': percent('cpu_utilization', 'cpu_capacity')" in snapshot_adapter
    assert "'memory_percent': percent('memory_utilization', 'memory_capacity')" in snapshot_adapter
    assert "'storage_percent': percent('storage_utilization', 'storage_capacity')" in snapshot_adapter
    assert "'pod_percent': percent('pod_utilization', 'pod_capacity')" in snapshot_adapter


def test_missing_capacity_is_unknown_not_healthy_zero() -> None:
    presentation = build_summary_presentation(
        summary=complete_summary(cpu_capacity=0, cpu_usage=0, cpu_utilization=0),
        cluster_info={'total_nodes': 3, 'ready_nodes': 3},
        trend_hours=24,
    )
    cpu = next(item for item in presentation['resource_rows'] if item['key'] == 'cpu')

    assert cpu['available'] is False
    assert cpu['value'] is None
    assert cpu['value_display'] == 'N/A'
    assert cpu['status'] == 'Unknown'
    assert presentation['posture_label'] == 'Limited Evidence'
    assert presentation['posture_tone'] == 'warning'


def test_zero_usage_with_valid_capacity_remains_normal_evidence() -> None:
    presentation = build_summary_presentation(
        summary=complete_summary(cpu_capacity=8, cpu_usage=0, cpu_utilization=0),
        cluster_info={'total_nodes': 3, 'ready_nodes': 3},
        trend_hours=168,
    )
    cpu = next(item for item in presentation['resource_rows'] if item['key'] == 'cpu')

    assert cpu['available'] is True
    assert cpu['value'] == 0.0
    assert cpu['status'] == 'Normal'
    assert presentation['time_range_label'] == 'Last 7 Days'


def test_trend_presentation_preserves_no_data_semantics() -> None:
    presentation = build_trend_presentation(
        trend_summary={
            'resources': {
                'cpu': {'current': 0, 'average': 0, 'peak': 0, 'sample_count': 0},
                'memory': {'current': 0, 'average': 0, 'peak': 0, 'sample_count': 0},
                'pods': {'current': 0, 'average': 0, 'peak': 0, 'sample_count': 0},
            },
            'posture': 'No Data',
            'tone': 'unknown',
            'sample_count': 0,
        },
        trend_hours=720,
        selected_node='',
    )

    assert presentation['current_highest_display'] == 'N/A'
    assert presentation['peak_value_display'] == 'N/A'
    assert all(item['current_display'] == 'N/A' for item in presentation['resource_rows'])
    assert presentation['time_range_label'] == 'Last 30 Days'


def test_utilization_chart_aligns_timestamps_and_does_not_clip_above_100() -> None:
    script = read('app/static/js/analytics_utilization.js')
    trend = read('app/templates/analytics/utilization/partials/_trend.html')

    assert 'alignedSeries' in script
    assert 'new Set(' in script
    assert 'byTimestamp.get(timestamp) ?? null' in script
    assert 'Intl.DateTimeFormat' in script
    assert 'suggestedMax: suggestedMaximum' in script
    assert 'max: 100' not in script
    assert 'spanGaps: true' in script
    assert "'trend_hours': trend_hours" in trend
    assert 'metric_tone' not in trend


def test_utilization_presentation_owns_template_derived_status() -> None:
    hero = read('app/templates/analytics/utilization/partials/_hero.html')
    overview = read('app/templates/analytics/utilization/partials/_overview.html')
    current = read('app/templates/analytics/utilization/partials/_current_summary.html')
    node = read('app/templates/analytics/utilization/partials/_node_detail.html')
    service = read('app/analytics/utilization/service.py')

    assert 'utilization_presentation' in hero
    assert 'utilization_presentation' in overview
    assert 'utilization_presentation' in current
    assert 'node_presentation' in node
    assert '{% set highest_util' not in hero
    assert "'Critical' if value" not in overview
    assert 'def get_selected_cluster(' not in service
    assert 'def _build_utilization_service(' not in service
    assert 'resolve_instance_for_cluster' not in service
