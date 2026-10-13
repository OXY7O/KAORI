from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding='utf-8')


def test_generate_namespace_query_limits_to_explicit_selected_cluster() -> None:
    service = read('app/reports/generate/service.py')
    scope = read('app/reports/scope.py')
    assert '_get_namespace_options_by_cluster(selected_cluster_id)' in service
    assert "selected_report_type['scope_asset_type'] == KUBERNETES_CLUSTER_ASSET_TYPE" in service
    assert 'if cluster_id:' in scope
    assert 'NamespaceInventory.cluster_id == cluster_id' in scope
    assert 'get_generate_namespace_options(cluster_id: str)' in service


def test_namespace_endpoint_uses_reports_generate_permission_and_is_json_only() -> None:
    routes = read('app/reports/generate/routes.py')
    registry = read('app/reports/routes.py')
    assert "@permission_required('reports.generate')\ndef generate_namespace_options()" in routes
    assert "'namespaces': get_generate_namespace_options(cluster_id)" in routes
    assert "endpoint='generate_namespace_options'" in registry
    assert "methods=['GET']" in registry


def test_wizard_fetches_only_selected_cluster_namespace_choices() -> None:
    page = read('app/templates/reports/generate/index.html')
    runtime = read('app/static/js/reports/generate.js')
    assert "url_for('reports.generate_namespace_options')" in page
    assert "const namespaceOptionsUrl = bootstrap.namespace_options_url || ''" in runtime
    assert 'namespaceOptionsByCluster[clusterId] || []' in runtime
    assert 'encodeURIComponent(clusterId)' in runtime
    assert 'payload.cluster_id !== clusterId' in runtime
    assert 'namespaceRequests.has(clusterId)' in runtime
