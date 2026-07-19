from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_factory_cleanup_is_registered() -> None:
    source = (ROOT / 'app/commands/__init__.py').read_text()
    assert 'factory_reset_integrations' in source
    assert 'app.cli.add_command(factory_reset_integrations)' in source


def test_cleanup_preserves_clusters_and_rebuilds_kubernetes() -> None:
    source = (ROOT / 'app/integrations/factory_cleanup.py').read_text()
    assert 'Cluster.query' in source
    assert 'Cluster.query.delete' not in source
    assert "provider_type='kubernetes'" in source
    assert 'KubernetesConnection(' in source
    assert "asset_type='kubernetes_cluster'" in source
    assert 'PrometheusInstance.query.delete' in source
    assert 'AlertmanagerInstance.query.delete' in source


def test_kubernetes_is_visible_in_integrations_navigation() -> None:
    navigation = (ROOT / 'app/templates/components/navigation/integrations_menu.html').read_text()
    routes = (ROOT / 'app/integrations/routes.py').read_text()
    service = (ROOT / 'app/integrations/service.py').read_text()
    assert "url_for('integrations.kubernetes')" in navigation
    assert "@integrations_bp.get('/kubernetes')" in routes
    assert 'def build_kubernetes_page' in service
