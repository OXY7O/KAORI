from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_notification_activity_verifier_is_release_gated() -> None:
    quality_gate = read('scripts/quality_gate.sh')
    registry = read('scripts/release_surface_registry.py')

    assert 'python scripts/verify_notification_activity_center.py' in quality_gate
    assert "'scripts/verify_notification_activity_center.py'" in registry


def test_notification_deck_operator_actions_use_final_title_case() -> None:
    activity = read('app/templates/notifications/partials/_notification_deck_activity.html')
    notifications = read('app/templates/notifications/partials/_notification_deck_notifications.html')
    items = read('app/templates/notifications/components/_activity_center_items.html')
    shell = read('app/templates/components/navigation/_notification_center.html')

    for token in ('Processes in Progress', 'No Process Is Running', '&nbsp;Active'):
        assert token in activity
    for token in ('Recent Notifications', 'Mark All Read', 'Needs Attention', 'Need Attention'):
        assert token in notifications
    for token in ('View Details', 'Mark Read'):
        assert token in items
    assert 'View All <i' in shell

    for legacy in ('Processes in progress', 'No process is running', '&nbsp;active'):
        assert legacy not in activity
    for legacy in ('Recent notifications', 'Mark all read', ' need attention'):
        assert legacy not in notifications
    for legacy in ('View details', 'Mark read'):
        assert legacy not in items
    assert 'View all <i' not in shell


def test_notification_activity_verifier_tracks_current_shared_tab_and_progress_geometry() -> None:
    verifier = read('scripts/verify_notification_activity_center.py')

    assert 'rounded-xl border border-outline-default bg-surface-hover p-1' in verifier
    assert 'w-1/4 rounded-full bg-kaori-primary/55' in verifier
    assert 'framed_workspace_tabs.render_navigation(' in verifier
    assert 'rounded-xl border border-kaori-primary/20 bg-kaori-soft p-1' not in verifier
    assert 'w-1/3 rounded-full bg-kaori-primary/60' not in verifier
