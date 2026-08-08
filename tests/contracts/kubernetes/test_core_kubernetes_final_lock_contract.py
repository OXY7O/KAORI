from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_core_kubernetes_final_lock_is_documented_and_quality_gated() -> None:
    lock = read('docs/design/KAORI_CORE_KUBERNETES_LOCK_V1.md')
    gate = read('scripts/quality_gate.sh')
    ui_lock = read('scripts/verify_core_workspace_ui_lock.py')

    for label in (
        'Welcome',
        'Kubernetes Dashboard',
        'Kubernetes Inventory',
        'Kubernetes Analytics',
        'Kubernetes Operations',
        'Kubernetes Governance',
    ):
        assert label in lock

    assert 'Status: Final Lock v1' in lock
    assert 'Default table page size is 5' in lock
    assert '5 / 10 / 25 / 50' in lock
    assert 'verify_core_kubernetes_final_lock.py' in gate
    assert 'verify_analytics_compact_label_standard.py' in gate
    assert "'app/templates/dashboards/kubernetes/'" in ui_lock


def test_core_kubernetes_final_lock_keeps_obsolete_paths_removed() -> None:
    cleanup = read('scripts/cleanup_obsolete_files.sh')
    obsolete = (
        'app/dashboards/kubernetes/snapshot_builder.py',
        'app/static/js/analytics_capacity.js',
        'app/static/js/analytics_forecast.js',
        'app/templates/kubernetes_operations/_components.html',
        'app/templates/governance/tls_certificates/partials/_inventory_scope.html',
        'app/static/js/inventory/topology_bootstrap.js',
    )
    for relative in obsolete:
        assert not (ROOT / relative).exists()
        assert f"'{relative}'" in cleanup
