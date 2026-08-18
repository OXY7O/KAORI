from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[3]


class AbortSignal(RuntimeError):
    def __init__(self, status_code: int) -> None:
        super().__init__(f'abort:{status_code}')
        self.status_code = status_code


class FakeBlueprint:
    def __init__(self, _name: str, _import_name: str, **_kwargs: Any) -> None:
        self.before_requests: list[Any] = []

    def route(self, *_args: Any, **_kwargs: Any):
        def decorator(function):
            return function

        return decorator

    def before_request(self, function):
        self.before_requests.append(function)
        return function


def _load_routes(monkeypatch, *, authorized: bool = True, has_clusters: bool = True):
    state: dict[str, Any] = {
        'authorized': authorized,
        'has_clusters': has_clusters,
        'permission_checks': [],
        'cluster_checks': 0,
        'overview_calls': [],
        'section_calls': [],
        'render_calls': [],
    }

    for package in ('app', 'app.kubernetes.cluster', 'app.dashboards', 'app.kubernetes.dashboard', 'app.access.rbac'):
        module = ModuleType(package)
        module.__path__ = []
        monkeypatch.setitem(sys.modules, package, module)

    request = SimpleNamespace(args={}, headers={}, endpoint='kubernetes_dashboard.section')
    flask = ModuleType('flask')
    flask.Blueprint = FakeBlueprint
    flask.request = request

    def abort(status_code: int):
        raise AbortSignal(status_code)

    def render_template(template_name: str, **context: Any):
        state['render_calls'].append((template_name, context))
        return {'template': template_name, 'context': context}

    flask.abort = abort
    flask.render_template = render_template
    monkeypatch.setitem(sys.modules, 'flask', flask)

    onboarding = ModuleType('app.kubernetes.cluster.onboarding')

    def has_registered_clusters() -> bool:
        state['cluster_checks'] += 1
        return bool(state['has_clusters'])

    onboarding.has_registered_clusters = has_registered_clusters
    monkeypatch.setitem(sys.modules, onboarding.__name__, onboarding)

    service = ModuleType('app.kubernetes.dashboard.service')

    def get_dashboard_overview(**kwargs: Any):
        state['overview_calls'].append(kwargs)
        return SimpleNamespace(name='overview')

    def get_dashboard_section(section: str, **kwargs: Any):
        state['section_calls'].append((section, kwargs))
        return SimpleNamespace(name=section)

    service.get_dashboard_overview = get_dashboard_overview
    service.get_dashboard_section = get_dashboard_section
    monkeypatch.setitem(sys.modules, service.__name__, service)

    decorators = ModuleType('app.access.rbac.decorators')

    def permission_required(permission: str):
        def decorator(function):
            def protected(*args: Any, **kwargs: Any):
                state['permission_checks'].append(permission)
                if not state['authorized']:
                    return {'forbidden': permission}, 403
                return function(*args, **kwargs)

            protected.__name__ = function.__name__
            protected.__wrapped__ = function
            return protected

        return decorator

    decorators.permission_required = permission_required
    monkeypatch.setitem(sys.modules, decorators.__name__, decorators)

    module_name = 'app.kubernetes.dashboard.routes'
    spec = importlib.util.spec_from_file_location(module_name, ROOT / 'app/kubernetes/dashboard/routes.py')
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)
    return module, state, request, module.kubernetes_dashboard_bp


def _dispatch(blueprint: FakeBlueprint, view, *args: Any):
    for before_request in blueprint.before_requests:
        response = before_request()
        if response is not None:
            return response
    return view(*args)


def test_lazy_section_authorization_runs_before_clusterless_blocker(monkeypatch) -> None:
    routes, state, _request, blueprint = _load_routes(monkeypatch, authorized=False, has_clusters=False)

    response = _dispatch(blueprint, routes.section, 'capacity_snapshot')

    assert response == ({'forbidden': 'dashboard.view'}, 403)
    assert state['permission_checks'] == ['dashboard.view']
    assert state['cluster_checks'] == 0
    assert state['section_calls'] == []
    assert state['render_calls'] == []


def test_authorized_clusterless_section_renders_onboarding_without_data_read(monkeypatch) -> None:
    routes, state, _request, blueprint = _load_routes(monkeypatch, authorized=True, has_clusters=False)

    response = _dispatch(blueprint, routes.section, 'alerts_summary')

    assert response['template'] == 'components/cluster/_onboarding_banner.html'
    assert state['permission_checks'] == ['dashboard.view']
    assert state['cluster_checks'] == 1
    assert state['section_calls'] == []


def test_unknown_section_returns_404_before_cluster_probe(monkeypatch) -> None:
    routes, state, _request, blueprint = _load_routes(monkeypatch, authorized=True, has_clusters=False)

    try:
        _dispatch(blueprint, routes.section, 'not-a-dashboard-section')
    except AbortSignal as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError('Unknown dashboard sections must abort with 404.')

    assert state['permission_checks'] == ['dashboard.view']
    assert state['cluster_checks'] == 0
    assert state['section_calls'] == []


def test_authorized_section_reads_dashboard_only_after_cluster_readiness(monkeypatch) -> None:
    routes, state, request, blueprint = _load_routes(monkeypatch, authorized=True, has_clusters=True)
    request.args = {
        'cluster_id': 'cluster-1',
        'cluster_health_page': '2',
        'cluster_health_per_page': '10',
    }

    response = _dispatch(blueprint, routes.section, 'cluster_health')

    assert state['permission_checks'] == ['dashboard.view']
    assert state['cluster_checks'] == 1
    assert state['section_calls'] == [
        (
            'cluster_health',
            {
                'selected_cluster_id': 'cluster-1',
                'cluster_health_page': '2',
                'cluster_health_per_page': 10,
            },
        )
    ]
    assert response['template'] == 'kubernetes/dashboard/partials/_cluster_health.html'


def test_dashboard_tab_selection_is_bounded_to_canonical_tabs(monkeypatch) -> None:
    routes, _state, request, _blueprint = _load_routes(monkeypatch)

    request.args = {'tab': 'capacity'}
    assert routes._active_tab() == 'capacity'

    request.args = {'tab': 'unknown'}
    assert routes._active_tab() == 'overview'


def test_cluster_health_page_size_rejects_unbounded_values(monkeypatch) -> None:
    routes, _state, request, _blueprint = _load_routes(monkeypatch)

    for value in ('5', '10', '25', '50'):
        request.args = {'cluster_health_per_page': value}
        assert routes._cluster_health_per_page() == int(value)

    for value in ('0', '5000', 'invalid'):
        request.args = {'cluster_health_per_page': value}
        assert routes._cluster_health_per_page() == 5


def test_dashboard_index_requires_permission_before_building_context(monkeypatch) -> None:
    routes, state, request, blueprint = _load_routes(monkeypatch, authorized=False)
    request.endpoint = 'kubernetes_dashboard.index'

    response = _dispatch(blueprint, routes.index)

    assert response == ({'forbidden': 'dashboard.view'}, 403)
    assert state['permission_checks'] == ['dashboard.view']
    assert state['overview_calls'] == []
