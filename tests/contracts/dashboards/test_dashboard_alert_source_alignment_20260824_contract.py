from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_dashboard_alert_summary_uses_source_boundary_without_overclaiming() -> None:
    kubernetes = read('app/templates/dashboards/kubernetes/partials/_alerts_summary.html')
    object_storage = read('app/templates/dashboards/object_storage/partials/_alerts_summary.html')

    assert 'Alert Intelligence' in kubernetes
    assert 'Alert Intelligence' in object_storage
    assert 'Prometheus + Alertmanager' in kubernetes
    assert 'Prometheus + Alertmanager' in object_storage
    assert 'Kubernetes Alerts' in kubernetes
    assert 'Object Storage Alerts' in object_storage


def test_dashboard_alert_summary_does_not_use_inventory_as_alert_authority() -> None:
    kubernetes = read('app/templates/dashboards/kubernetes/partials/_alerts_summary.html')
    object_storage = read('app/templates/dashboards/object_storage/partials/_alerts_summary.html')

    for source in (kubernetes, object_storage):
        assert 'Inventory Snapshot' not in source
        assert 'Inventory Sync' not in source
        assert 'inventory snapshot' not in source.lower()
        assert 'inventory sync' not in source.lower()


def test_dashboard_alert_source_alignment_is_explicit_in_presentation_services() -> None:
    kubernetes = read('app/dashboards/kubernetes/presentation.py')
    object_storage = read('app/dashboards/object_storage/presentation.py')

    assert 'Prometheus + Alertmanager' in kubernetes
    assert 'Prometheus + Alertmanager' in object_storage
    assert 'alert_source' in kubernetes
    assert 'alert_source' in object_storage


def test_inventory_authority_copy_is_compact_and_object_storage_hero_has_more_context() -> None:
    kubernetes_templates = ''.join(
        read(path)
        for path in (
            'app/templates/kubernetes/inventory/overview/partials/_inventory_snapshot.html',
            'app/templates/kubernetes/inventory/nodes/partials/_table.html',
            'app/templates/kubernetes/inventory/namespaces/partials/_table.html',
            'app/templates/kubernetes/inventory/workloads/partials/_table.html',
            'app/templates/kubernetes/inventory/pods/partials/_table.html',
            'app/templates/kubernetes/inventory/services/partials/_table.html',
            'app/templates/kubernetes/inventory/ingresses/partials/_table.html',
            'app/templates/kubernetes/inventory/storage/partials/_table.html',
        )
    )
    object_storage_detail = read(
        'app/templates/storage/object_storage/inventory/systems/partials/_system_detail_content.html'
    )
    object_storage_presentation = read('app/storage/object_storage/inventory/presentation.py')
    hero = read('app/templates/storage/object_storage/inventory/overview/partials/_hero.html')

    assert 'Latest committed inventory snapshot; no live Kubernetes API query.' in kubernetes_templates
    assert (
        'This detail reads the latest committed database snapshot. It does not query the Kubernetes API live.'
        not in kubernetes_templates
    )
    assert (
        'Committed Object Storage Inventory; provider configuration and live health remain integration-owned.'
        in object_storage_detail
    )
    assert 'Latest committed Inventory Sync snapshot; no live provider query.' in object_storage_presentation
    assert (
        'Review committed inventory coverage, readiness, and system scope across registered Object Storage environments.'
        in hero
    )
    assert 'Review committed fleet posture across managed systems and inventory assets.' not in hero
