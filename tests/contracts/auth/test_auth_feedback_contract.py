from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AUTH_ROUTES = ROOT / 'app/auth/routes.py'
AUTH_LAYOUT = ROOT / 'app/templates/layouts/auth.html'


def test_auth_routes_use_canonical_transient_feedback() -> None:
    source = AUTH_ROUTES.read_text(encoding='utf-8')

    assert 'from flask import Blueprint, current_app, flash,' not in source
    assert 'from app.notifications.service import queue_transient_feedback' in source
    assert 'flash(' not in source
    assert source.count('queue_transient_feedback(') >= 10


def test_auth_layout_renders_queued_feedback() -> None:
    source = AUTH_LAYOUT.read_text(encoding='utf-8')

    assert 'load_quick_action_feedback()' in source
    assert 'components/navigation/_quick_sync_result.html' in source
    assert 'data-quick-action-toast-close' in source or 'dismissQuickActionToast' in source
    assert 'window.dismissQuickActionToast' in source


def test_auth_feedback_remains_non_persistent() -> None:
    source = AUTH_ROUTES.read_text(encoding='utf-8')

    assert 'record_operational_activity' not in source
    assert 'create_notification' not in source
    assert 'record_authentication_activity' in source
