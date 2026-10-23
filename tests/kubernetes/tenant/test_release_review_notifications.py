"""Tenant Release approval outcome notification contracts (#2867)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from flask import Flask

from app.kubernetes.tenant import release_review_notifications as receipts


def _approval() -> dict[str, str | int]:
    return {
        'requested_by': 11,
        'approved_by': 22,
        'plan_sha256': 'a' * 64,
    }


def test_review_outcome_reaches_only_requester_and_actual_reviewer(monkeypatch):
    recorded: list[dict] = []
    monkeypatch.setattr(receipts, 'url_for', lambda *args, **kwargs: '/tenants/t-1/manage?release_step=approval')
    monkeypatch.setattr(receipts, 'create_notification', lambda **kwargs: recorded.append(kwargs))

    with Flask(__name__).app_context():
        receipts.notify_release_handoff_review_recorded(tenant_id='t-1', approval=_approval())

    assert [record['user_id'] for record in recorded] == [11, 22]
    assert {record['metadata']['recipient_role'] for record in recorded} == {'requester', 'reviewer'}
    assert all(record['status'] == 'success' for record in recorded)
    assert all(record['event_type'] == 'kubernetes_tenant_release_handoff_review_recorded' for record in recorded)
    assert all(record['action_url'].endswith('release_step=approval') for record in recorded)
    assert all('Release remain separate' in record['message'] for record in recorded)
    assert all(record['metadata']['plan_sha256'] == 'a' * 64 for record in recorded)


def test_failed_requester_receipt_does_not_prevent_reviewer_receipt(monkeypatch):
    sent: list[int] = []
    rollbacks: list[bool] = []

    def deliver(**kwargs):
        if kwargs['user_id'] == 11:
            raise RuntimeError('notification storage unavailable for recipient')
        sent.append(kwargs['user_id'])

    monkeypatch.setattr(receipts, 'url_for', lambda *args, **kwargs: '/tenants/t-1/manage')
    monkeypatch.setattr(receipts, 'create_notification', deliver)
    monkeypatch.setattr(receipts, 'db', SimpleNamespace(session=SimpleNamespace(rollback=lambda: rollbacks.append(True))))

    with Flask(__name__).app_context():
        receipts.notify_release_handoff_review_recorded(tenant_id='t-1', approval=_approval())

    assert rollbacks == [True]
    assert sent == [22]


def test_receipt_is_post_commit_and_separate_from_governance_authority():
    root = Path(__file__).resolve().parents[3]
    routes = (root / 'app/kubernetes/tenant/routes.py').read_text(encoding='utf-8')
    approval = (root / 'app/kubernetes/tenant/release_handoff_approval.py').read_text(encoding='utf-8')
    constants = (root / 'app/platform_operations/notifications/constants.py').read_text(encoding='utf-8')
    handler = routes.split('def approve_tenant_release_handoff_route(', 1)[1].split(
        "@tenant_bp.post('/tenants/<string:tenant_id>/release-handoff/successor-reference')", 1
    )[0]

    assert handler.index('approve_release_handoff_plan_committed(') < handler.index(
        'notify_release_handoff_review_recorded(tenant_id=tenant_id, approval=result)'
    )
    assert "action='tenant.release.handoff_acknowledged'" in approval
    assert "'provider_handoff_verified': False" in approval
    assert "'release_authorized': False" in approval
    assert "'kubernetes_tenant_release_handoff_review_recorded'" in constants
