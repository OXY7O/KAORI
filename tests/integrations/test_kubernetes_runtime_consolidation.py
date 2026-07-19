from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_kubernetes_is_managed_from_integrations_workspace() -> None:
    routes = _read('app/integrations/routes.py')
    sidebar = _read('app/templates/components/navigation/sidebar.html')
    cluster_routes = _read('app/cluster/routes.py')
    assert "'/kubernetes/<string:cluster_id>'" in routes
    assert 'kubernetes_runtime_refresh' in routes
    assert 'K8s Cluster' not in sidebar
    assert "redirect(url_for('integrations.kubernetes'" in cluster_routes


def test_kubernetes_runtime_uses_canonical_connection_provider_record() -> None:
    adapter = _read('app/integrations/runtime/kubernetes_adapter.py')
    tasks = _read('app/integrations/runtime/tasks.py')
    assert 'KubernetesConnection' in adapter
    assert "provider = 'kubernetes'" in adapter
    assert "('kubernetes', kubernetes_runtime_adapter" in tasks
    assert 'blocked_features' in adapter
    assert 'legacy_features' in adapter


def test_one_shot_legacy_commands_are_not_registered() -> None:
    commands = _read('app/commands/__init__.py')
    assert 'audit_integration_legacy' not in commands
    assert 'reconcile_integration_legacy' not in commands
    assert 'factory_reset_integrations' not in commands
    assert 'refresh_integration_runtime_command' in commands
