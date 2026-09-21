from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_object_storage_dashboard_uses_kaori_alert_cases_not_raw_source_rows() -> None:
    service = read('app/storage/object_storage/dashboard/service.py')
    shared = read('app/intelligence/alert_intelligence/dashboard_cases.py')
    alerts = read('app/templates/storage/object_storage/dashboard/partials/_alerts_summary.html')

    assert 'active_recommendation_alert_cases' in service
    assert "domain='object_storage'" in service
    assert "AlertCase.source_type == 'recommendation'" in shared
    assert "AlertCase.source_state.in_(('firing', 'unknown'))" in shared
    assert "AlertCase.workflow_state != 'closed'" in shared
    assert "'source_label': 'Alert Intelligence'" in service
    assert "'source_detail': 'Active AlertCase records'" in service
    assert 'Active KAORI AlertCase posture and recent cases.' in alerts
    assert "url_for('alert_intelligence.index'" in alerts
    actions = read('app/templates/storage/object_storage/dashboard/partials/_recommended_actions.html')
    assert "url_for('intelligence.recommendation_details'" in actions
    assert 'get_dashboard_recommendation_findings' in service
    assert 'Active Alertmanager and Metrics Source Object Storage alert signals.' not in alerts
    assert 'Alert evidence is unavailable in the committed analytics snapshot.' not in alerts
    assert 'Select an Object Storage system to view KAORI alert cases.' in alerts


def test_dashboard_response_guidance_explains_alert_provenance() -> None:
    kubernetes = read('app/templates/kubernetes/dashboard/partials/_alert_response_guidance.html')
    object_storage = read('app/templates/storage/object_storage/dashboard/partials/_alert_response_guidance.html')

    for content in (kubernetes, object_storage):
        assert 'Alert Data Source' in content
        assert 'KAORI Alert Intelligence · Active AlertCase records' in content
        assert 'Recommendation-origin durable alert cases' not in content
        assert 'Raw source alerts remain in Analytics' not in content


def test_topology_details_matches_notification_deck_desktop_width() -> None:
    visualization = read('app/templates/components/visualization_workspace.html')
    notification_deck = read('app/templates/components/navigation/_notification_center.html')

    assert "'right-0 border-l max-w-lg'" in visualization
    assert 'w-full max-w-none flex-col' in notification_deck
    assert 'sm:max-w-lg' in notification_deck


def test_inventory_authority_copy_is_compact_and_object_storage_hero_has_more_context() -> None:
    kubernetes_templates = '\n'.join(
        read(path)
        for path in (
            'app/templates/kubernetes/inventory/overview/partials/_cluster_detail_content.html',
            'app/templates/kubernetes/inventory/workloads/partials/_workload_detail_content.html',
            'app/templates/kubernetes/inventory/pods/partials/_pod_detail_content.html',
            'app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html',
            'app/templates/kubernetes/inventory/namespaces/partials/_namespace_detail_content.html',
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
    assert 'Review committed inventory coverage and system scope across registered Object Storage systems.' in hero
    assert 'Review committed fleet posture across managed systems and inventory assets.' not in hero
