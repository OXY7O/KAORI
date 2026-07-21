from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_provider_delete_is_guarded_by_bindings_and_active_jobs() -> None:
    prometheus = read('app/prometheus/service.py')
    alertmanager = read('app/alertmanager/service.py')
    deletion = read('app/integrations/deletion.py')

    assert "provider_type='prometheus'" in prometheus
    assert "provider_type='alertmanager'" in alertmanager
    assert 'provider_deletion_guard' in prometheus
    assert 'provider_deletion_guard' in alertmanager
    assert 'ACTIVE_JOB_STATUSES' in deletion
    assert 'active KAORI job(s)' in deletion


def test_kubernetes_delete_preserves_shared_sources_and_blocks_live_dependencies() -> None:
    service = read('app/cluster/service.py')
    lifecycle = read('app/templates/integrations/kubernetes/partials/_inventory_lifecycle.html')

    assert 'kubernetes_deletion_guard' in service
    assert 'Secret Reveal request(s)' in read('app/integrations/deletion.py')
    assert 'Shared Prometheus/Alertmanager instances' in lifecycle
    assert 'Deleting this Kubernetes connection removes only its Prometheus and Alertmanager bindings.' in lifecycle
    assert 'Deletion Is Currently Blocked' in lifecycle


def test_inventory_operational_use_is_informative_and_full_width() -> None:
    template = read('app/templates/integrations/kubernetes/partials/_inventory_lifecycle.html')

    assert 'KAORI Operational Consumers' in template
    assert 'Bound Observability Sources' in template
    assert 'Removed With the Connection' in template
    assert 'Retained After Deletion' in template
    assert 'Generated Nodes' not in template
    assert 'Discovered Nodes' in template


def test_jobs_refresh_updates_workspace_and_hero_oob() -> None:
    jobs = read('app/templates/integrations/jobs.html')
    routes = read('app/integrations/routes.py')
    refresh = read('app/templates/integrations/jobs/partials/_status_refresh.html')

    assert "fragment='status'" in jobs
    assert "fragment == 'status'" in routes
    assert "_hero_metadata.html" in refresh
    assert "_hero_context_metrics.html" in refresh
    assert 'hx-swap-oob="outerHTML"' in read('app/templates/integrations/jobs/partials/_hero_metadata.html')
    assert 'hx-swap-oob="outerHTML"' in read('app/templates/integrations/jobs/partials/_hero_context_metrics.html')
