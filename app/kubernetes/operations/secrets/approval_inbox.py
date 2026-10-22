"""Read-only Work Inbox projection for eligible Protected Secret Reveal approvers.

Committed SecretRevealRequest state is authoritative. This is not an approval,
a recipient assignment, or evidence of Secret value access. Eligibility is
checked against the viewer's *current* active role for every read.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from flask import url_for

from app.models.secret_reveal import SecretRevealRequest
from app.models.user import User

_DISPLAY_LIMIT = 8


def get_secret_reveal_approval_work_inbox(*, user_id: int) -> dict[str, Any]:
    """Return currently actionable independent approvals for this viewer."""
    empty: dict[str, Any] = {'items': [], 'pending_count': 0, 'total_count': 0}
    viewer = User.query.filter_by(id=user_id).first()
    if (
        viewer is None
        or not viewer.is_active
        or not viewer.account_is_active
        or viewer.deleted_at is not None
        or not viewer.has_permission('kubernetes_secrets.approve_reveal')
    ):
        return empty

    # Filter current, unexpired, independently approvable requests *before*
    # calculating the count. No Kubernetes/provider calls or Secret payloads.
    pending_query = SecretRevealRequest.query.filter(
        SecretRevealRequest.status == 'pending',
        SecretRevealRequest.policy == 'approval_required',
        SecretRevealRequest.expires_at > datetime.now(UTC),
        SecretRevealRequest.requester_user_id != user_id,
    )
    pending_count = pending_query.count()
    requests = (
        pending_query.order_by(
            SecretRevealRequest.requested_at.desc(),
            SecretRevealRequest.id.desc(),
        )
        .limit(_DISPLAY_LIMIT)
        .all()
    )
    items = [
        {
            'request_id': record.id,
            'secret_name': record.secret_name,
            'namespace': record.namespace,
            'cluster_name': record.cluster.name,
            'requester_label': record.requester.display_label,
            'ticket_reference': record.ticket_reference,
            'requested_at': record.requested_at,
            'state': 'Pending',
            'is_pending': True,
            'action_url': url_for(
                'kubernetes_operations.reveal_secret',
                reveal_view='approvals',
                pending_search=record.ticket_reference,
            ),
        }
        for record in requests
    ]
    return {'items': items, 'pending_count': pending_count, 'total_count': pending_count}
