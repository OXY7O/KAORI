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


def test_kubernetes_runtime_history_supplies_cluster_id_and_owning_endpoints() -> None:
    runtime = read('app/templates/integrations/partials/_runtime_history.html')

    assert "'cluster_id': cluster.id" in runtime
    assert "endpoint='integrations.kubernetes_runtime_history'" in runtime
    assert "href_endpoint='integrations.kubernetes_detail'" in runtime
    assert "hx_target='#' ~ runtime_history_id" in runtime
    assert "hx_swap='outerHTML'" in runtime
