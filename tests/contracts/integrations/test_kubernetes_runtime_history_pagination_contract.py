from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_numeric_pagination_preserves_route_view_arguments() -> None:
    pagination = read('app/templates/components/pagination.html')

    assert 'request.view_args.copy() if request.view_args else {}' in pagination
    assert 'first_args.update(query_params.copy() if query_params else request.args.to_dict())' in pagination
    assert 'page_args.update(query_params.copy() if query_params else request.args.to_dict())' in pagination
    assert 'last_args.update(query_params.copy() if query_params else request.args.to_dict())' in pagination


def test_runtime_history_pagination_uses_provider_owned_routing() -> None:
    runtime = read('app/templates/integrations/partials/_runtime_history.html')
    kubernetes_detail = read('app/templates/integrations/kubernetes/detail.html')
    kubernetes_workspace = read('app/templates/integrations/kubernetes/partials/_runtime_workspace.html')
    prometheus = read('app/templates/prometheus/partials/_runtime_history.html')
    alertmanager = read('app/templates/alertmanager/partials/_runtime_history.html')

    assert 'runtime_history_route_args_value.copy()' in runtime
    assert 'endpoint=runtime_history_endpoint_name' in runtime
    assert 'href_endpoint=runtime_history_detail_endpoint_name' in runtime
    assert "hx_target='#' ~ runtime_history_id" in runtime
    assert "hx_swap='outerHTML'" in runtime
    assert 'cluster.id' not in runtime

    for template in (kubernetes_detail, kubernetes_workspace):
        assert "runtime_history_route_args={'cluster_id': cluster.id}" in template
        assert "runtime_history_endpoint='integrations.kubernetes_runtime_history'" in template
        assert "runtime_history_detail_endpoint='integrations.kubernetes_detail'" in template

    assert "runtime_history_route_args = {'instance_id': instance.id}" in prometheus
    assert "runtime_history_route_args = {'instance_id': instance.id}" in alertmanager


def test_full_page_kubernetes_detail_reads_requested_history_page() -> None:
    routes = read('app/integrations/routes.py')

    assert "request.args.get('page', 1, type=int)" in routes
    assert "request.args.get('per_page', 5, type=int)" in routes
    assert 'if history_page is not None' in routes
    assert 'if history_per_page is not None' in routes


def test_runtime_history_full_page_fallback_opens_runtime_tab() -> None:
    runtime = read('app/templates/integrations/partials/_runtime_history.html')
    detail = read('app/templates/integrations/kubernetes/detail.html')

    assert 'name="tab" value="{{ runtime_history_tab_name }}"' in runtime
    assert "runtime_history_tab|default('runtime', true)" in runtime
    assert "url.searchParams.get('tab')" in detail
    assert 'syncTabFromLocation()' in detail
    assert "nextUrl.searchParams.set('tab', tab)" in detail


def test_runtime_history_footer_uses_kaori_inventory_wording() -> None:
    runtime = read('app/templates/integrations/partials/_runtime_history.html')

    assert 'Runtime Observations</p>' in runtime
    assert '>Rows</span>' in runtime
    assert '> observations</p>' not in runtime
