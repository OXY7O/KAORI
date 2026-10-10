"""Committed-state multi-approver Work Inbox: no second approval authority."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.kubernetes.tenant import approval_inbox


def _plan(now: datetime, *, requester: int = 1, sha: str = "a" * 64) -> dict:
    return {
        "status": "pending_independent_approval",
        "plan_sha256": sha,
        "requested_by": requester,
        "requested_at": now.isoformat(),
        "change_reference": "CHG-2026-001",
    }


def _item(monkeypatch, *, plan: dict, user_id: int, current_sha: str | None = None,
          approvals: dict | None = None, now: datetime | None = None):
    clock = now or datetime.now(UTC)
    monkeypatch.setattr(
        approval_inbox, "url_for",
        lambda endpoint, **kwargs: f"/tenant/{kwargs.get('manage_tenant_id')}",
    )
    return approval_inbox._present_handoff_request(
        plan=plan,
        tenant=SimpleNamespace(name="tenant-uat-demo", id="tenant-id"),
        current_sha=current_sha or plan["plan_sha256"],
        approvals=approvals or {},
        user_id=user_id,
        now=clock,
    )


def test_four_eligible_accounts_have_one_pending_plan_not_four_votes(monkeypatch):
    now = datetime.now(UTC)
    plan = _plan(now)
    assert _item(monkeypatch, plan=plan, user_id=1, now=now) is None
    rows = [_item(monkeypatch, plan=plan, user_id=uid, now=now) for uid in (2, 3, 4, 5)]
    assert all(row["state"] == "Pending" and row["is_pending"] for row in rows)
    assert {row["plan_sha256"] for row in rows} == {plan["plan_sha256"]}
    assert all(row["action_url"] == "/tenant/tenant-id" for row in rows)


def test_first_approval_resolves_other_three_without_expiration(monkeypatch):
    now = datetime.now(UTC)
    plan = _plan(now)
    approvals = {
        plan["plan_sha256"]: {
            "status": "acknowledged_pending_provider_handoff",
            "approved_by": 3,
        }
    }
    statuses = {
        uid: _item(monkeypatch, plan=plan, user_id=uid, approvals=approvals, now=now)
        for uid in (2, 3, 4, 5)
    }
    assert statuses[3]["state"] == "Approved"
    assert {statuses[n]["state"] for n in (2, 4, 5)} == {"Resolved by another reviewer"}
    assert all(not row["is_pending"] and row["action_url"] is None for row in statuses.values())


def test_superseded_and_expired_plan_are_not_actionable(monkeypatch):
    now = datetime.now(UTC)
    plan = _plan(now)
    old = _item(monkeypatch, plan=plan, user_id=2, current_sha="b" * 64, now=now)
    assert old["state"] == "Superseded"
    assert old["action_url"] is None

    expired = _item(
        monkeypatch, plan=_plan(now - timedelta(minutes=20)), user_id=2, now=now
    )
    assert expired["state"] == "Expired"
    assert expired["action_url"] is None


def test_invalid_or_missing_plan_status_cannot_generate_action(monkeypatch):
    now = datetime.now(UTC)
    no_status = _plan(now)
    no_status["status"] = "provider_transferred"
    assert _item(monkeypatch, plan=no_status, user_id=2, now=now) is None
    invalid_sha = _plan(now, sha="not-a-commit-hash")
    assert _item(monkeypatch, plan=invalid_sha, user_id=2, now=now) is None


def test_inactive_or_permissionless_user_is_not_given_inbox(monkeypatch):
    class Query:
        @staticmethod
        def filter_by(**kwargs):
            return Query()

        def first(self):
            return self.viewer

    class Viewer:
        is_active = True

        @staticmethod
        def has_permission(key):
            return key == "tenant.manage"

    Query.viewer = Viewer()
    monkeypatch.setattr(approval_inbox, "User", SimpleNamespace(query=Query()))
    assert approval_inbox.get_tenant_release_work_inbox(user_id=2) == {
        "items": [], "pending_count": 0, "total_count": 0
    }
    Query.viewer.is_active = False
    assert approval_inbox.get_tenant_release_work_inbox(user_id=2)["pending_count"] == 0


def test_work_inbox_is_bound_to_committed_evidence_and_existing_notification_deck():
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    queries = (root / "app/platform_operations/notifications/queries.py").read_text(encoding="utf-8")
    panel = (
        root / "app/templates/platform_operations/notifications/partials/_notification_deck_inbox.html"
    ).read_text(encoding="utf-8")
    modal = (root / "app/templates/kubernetes/tenant/partials/_tenant_registry.html").read_text(
        encoding="utf-8"
    )
    js = (root / "app/static/js/native_dialogs.js").read_text(encoding="utf-8")

    assert "get_tenant_release_work_inbox(user_id=user_id)" in queries
    assert "inbox_unread_count += tenant_approval_inbox" in queries
    assert "tenant_approval_inbox_items" in queries
    assert "Tenant Release approval requests" in panel
    assert "Resolved by another reviewer" in panel or "approval.state" in panel
    assert "Review Handoff in Tenant Management" in panel
    assert "data-kaori-dialog-auto-open" in modal
    assert "openSelectedDialog" in js
