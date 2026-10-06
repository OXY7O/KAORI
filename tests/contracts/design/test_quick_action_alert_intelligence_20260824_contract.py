from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_alert_center_quick_action_routes_to_alert_intelligence() -> None:
    navbar = read('app/templates/components/navigation/navbar.html')
    marker = '>Alert Center<'
    assert marker in navbar

    action = navbar[navbar.index(marker) - 700 : navbar.index(marker) + 700]
    assert "url_for('alert_intelligence.index')" in action
    assert "url_for('analytics.alerts')" not in action
    assert 'Review active alert cases, ownership, suppression, and response state.' in action


def test_notification_deck_change_event_bridge_keeps_three_tab_state() -> None:
    navbar = read('app/templates/components/navigation/navbar.html')

    assert '@kaori:notifications-changed.window="if ($event.detail?.tab' in navbar
    assert "['activity', 'inbox', 'notifications'].includes($event.detail?.tab)" in navbar
    assert 'notificationDeckTab = $event.detail.tab' in navbar
    assert "$event.detail.tab === 'inbox' ? 'activity' : $event.detail.tab" not in navbar
    assert 'queueNotificationDeckRefresh()' in navbar
