"""Read-only Tenant Release handoff Work Inbox projection.

Plan and approval AuditEvents are the sole decision authority. Multiple eligible
viewers see the same committed request; inbox presentation creates no votes,
permissions or provider writes. This never selects a named approver.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from flask import url_for

from app.kubernetes.tenant.release_handoff_approval import (
    _APPROVAL_TARGET,
    _MAX_AGE_SECONDS,
    _PLAN_TARGET,
)
from app.models.audit import AuditEvent
from app.models.tenant import Tenant, TenantLifecycleStatus
from app.models.user import User

_HISTORY_LIMIT = 200
_DISPLAY_LIMIT = 8


def _plan_is_current(requested_at: object, now: datetime) -> bool:
    try:
        timestamp = datetime.fromisoformat(str(requested_at or ""))
    except (TypeError, ValueError):
        return False
    if timestamp.tzinfo is None:
        return False
    age = (now - timestamp.astimezone(UTC)).total_seconds()
    return 0 <= age <= _MAX_AGE_SECONDS


def _present_handoff_request(
    *,
    plan: dict[str, Any],
    tenant: Tenant,
    current_sha: str,
    approvals: dict[str, dict[str, Any]],
    user_id: int,
    now: datetime,
) -> dict[str, Any] | None:
    """Project one decision status from committed evidence (never infer approval)."""
    sha = str(plan.get("plan_sha256") or "")
    if len(sha) != 64 or str(plan.get("requested_by") or "") == str(user_id):
        return None
    if plan.get("status") != "pending_independent_approval":
        return None
    evidence = approvals.get(sha)
    if sha != current_sha:
        state = "Superseded"
    elif evidence and evidence.get("status") == "acknowledged_pending_provider_handoff":
        state = (
            "Approved"
            if str(evidence.get("approved_by") or "") == str(user_id)
            else "Resolved by another reviewer"
        )
    elif not _plan_is_current(plan.get("requested_at"), now):
        state = "Expired"
    else:
        state = "Pending"

    return {
        "tenant_name": tenant.name,
        "tenant_id": str(tenant.id),
        "plan_sha256": sha,
        "state": state,
        "is_pending": state == "Pending",
        "requested_at": plan.get("requested_at"),
        "change_reference": str(plan.get("change_reference") or ""),
        "action_url": (
            url_for(
                "tenant.tenant_detail",
                tenant_id=tenant.id,
                tenant_detail_section="release",
                _anchor="tenant-release-governance",
            )
            if state == "Pending" else None
        ),
    }


def get_tenant_release_work_inbox(*, user_id: int) -> dict[str, Any]:
    """Return current and recent approval requests for this eligible viewer.

    Work Inbox is a committed-state read model. Eligibility is evaluated using
    the *current* active role for every request; no cached recipient ACL.
    """
    viewer = User.query.filter_by(id=user_id).first()
    if (
        viewer is None or not viewer.is_active
        or not viewer.has_permission("tenant.manage")
        or not viewer.has_permission("integrations.manage")
    ):
        return {"items": [], "pending_count": 0, "total_count": 0}

    plans = (
        AuditEvent.query.filter_by(target_type=_PLAN_TARGET)
        .order_by(AuditEvent.id.desc())
        .limit(_HISTORY_LIMIT)
        .all()
    )
    ids = {str(row.target_id) for row in plans}
    if not ids:
        return {"items": [], "pending_count": 0, "total_count": 0}

    tenants = {
        str(tenant.id): tenant
        for tenant in Tenant.query.filter(Tenant.id.in_(ids)).all()
        if tenant.ownership_status == "adopted"
        and tenant.lifecycle_status == TenantLifecycleStatus.READY.value
    }
    approvals = (
        AuditEvent.query.filter_by(target_type=_APPROVAL_TARGET)
        .filter(AuditEvent.target_id.in_(ids))
        .order_by(AuditEvent.id.desc())
        .limit(_HISTORY_LIMIT)
        .all()
    )
    approvals_by_sha: dict[str, dict[str, Any]] = {}
    for row in approvals:
        evidence = dict(row.metadata_json or {})
        sha = str(evidence.get("plan_sha256") or "")
        if sha and sha not in approvals_by_sha:
            approvals_by_sha[sha] = evidence

    now = datetime.now(UTC)
    current_by_tenant: dict[str, str] = {}
    presented: list[dict[str, Any]] = []
    for row in plans:
        tenant_id = str(row.target_id)
        plan = dict(row.metadata_json or {})
        current_by_tenant.setdefault(tenant_id, str(plan.get("plan_sha256") or ""))
        tenant = tenants.get(tenant_id)
        if tenant is None:
            continue
        item = _present_handoff_request(
            plan=plan,
            tenant=tenant,
            current_sha=current_by_tenant[tenant_id],
            approvals=approvals_by_sha,
            user_id=user_id,
            now=now,
        )
        if item is not None:
            presented.append(item)

    # Prioritize current work over resolved history; preserve recent event order
    # within each group (stable sort). Committed approval state remains authority.
    presented.sort(key=lambda item: not item["is_pending"])
    return {
        "items": presented[:_DISPLAY_LIMIT],
        "pending_count": sum(bool(item["is_pending"]) for item in presented),
        "total_count": len(presented),
    }
