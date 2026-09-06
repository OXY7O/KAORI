from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_shared_hero_component_owns_blocked_context_body() -> None:
    component = read('app/templates/components/page_hero.html')

    assert 'macro blocked_context_body(' in component
    assert 'context_panel_classes()' in component
    assert 'context_panel_metrics_classes()' in component
    assert 'context_header_status(' in component
    assert 'context_info(' in component


def test_dashboard_blocked_state_is_family_consistent() -> None:
    component = read('app/templates/components/page_hero.html')
    kubernetes = read('app/templates/kubernetes/dashboard/partials/_hero.html')
    object_storage = read('app/templates/storage/object_storage/dashboard/partials/_hero.html')
    object_storage_content = read('app/templates/storage/object_storage/dashboard/partials/_content.html')

    assert "dashboard_state = 'blocked' if cluster_onboarding.is_blocked else 'normal'" in kubernetes
    assert "dashboard_state = 'blocked' if not dashboard.systems else 'normal'" in object_storage
    assert "'Object Storage Setup Required'" in object_storage
    assert "'Register an Object Storage system to activate operational signals.'" in object_storage
    assert "'normal'\n) }}" not in object_storage
    assert 'blocked_context_body(' in component
    assert 'storage/object_storage/inventory/components/_onboarding_banner.html' in object_storage_content
    assert 'Register Object Storage First' not in object_storage_content


def test_operational_workspace_blocked_contexts_share_one_renderer() -> None:
    kubernetes = read('app/templates/components/cluster/_hero_blocked_context.html')
    object_storage = read('app/templates/storage/object_storage/inventory/components/_hero_blocked_context.html')

    for source in (kubernetes, object_storage):
        assert 'page_hero.blocked_context_body(' in source
        assert '<div class="{{ page_hero.context_panel_classes() }}">' not in source
        assert 'page_hero.context_panel_metrics_classes()' not in source

    assert 'Connected Clusters' in kubernetes
    assert 'Workspace State' in kubernetes
    assert 'Registered Systems' in object_storage
    assert 'Workspace State' in object_storage


def test_analytics_blocked_heroes_prioritize_scope_and_missing_evidence() -> None:
    kubernetes = read('app/templates/kubernetes/analytics/components/_blocked_posture.html')
    object_storage = read('app/templates/storage/object_storage/analytics/partials/_hero_blocked_posture.html')

    for source in (kubernetes, object_storage):
        assert 'page_hero.blocked_context_body(' in source
        assert "'Active Scope'" in source
        assert "'Missing Evidence'" in source
        assert "'Current Step'" not in source
        assert "'Progress'" not in source

    assert 'Operational Metrics' in kubernetes
    assert 'Cluster Context' in kubernetes
    assert 'Alert Evidence' in kubernetes
    assert 'System Context' in object_storage
    assert 'Inventory Snapshot' in object_storage
    assert 'Analytics Snapshot' in object_storage


def test_analytics_dependency_blocker_exposes_current_action() -> None:
    blocker = read('app/templates/components/dependencies/_blocker.html')
    object_storage = read('app/templates/storage/object_storage/analytics/partials/_dependency_blocker.html')

    assert 'Analytics Setup Path' in blocker
    assert 'Current Blocker' in blocker
    assert 'Missing dependency:' in blocker
    assert 'dependency_missing_label' in blocker
    assert 'dependency_action_url' in blocker
    assert 'dependency_blocker.action_label' in blocker
    assert 'dependency_blocker.permission' in blocker
    assert 'dependency_missing_label' in object_storage


def test_blocked_readiness_contract_is_documented_by_profile() -> None:
    hero = read('docs/design/components/HERO.md')
    dashboard = read('docs/design/patterns/OPERATIONAL_DASHBOARD.md')
    analytics = read('docs/design/components/ANALYTICS_HERO.md')

    assert 'Blocked readiness grammar' in hero
    assert 'Operational workspace blocked context' in hero
    assert 'Active Scope' in hero
    assert 'Missing Evidence' in hero
    assert 'Dashboard Readiness' in dashboard
    assert 'Object Storage Setup Required' in dashboard
    assert 'Analytics Readiness' in analytics
    assert 'Missing Evidence' in analytics
