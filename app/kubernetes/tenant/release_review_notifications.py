"""User-specific, non-authoritative receipts for a committed Tenant Release review.

The approval AuditEvent is authoritative. These notifications only make the
recorded outcome discoverable in the existing KAORI Notification Deck.
"""

from __future__ import annotations

from typing import Any

from flask import current_app, url_for

from app.extensions.db import db
from app.platform_operations.notifications.service import create_notification


def notify_release_handoff_review_recorded(*, tenant_id: str, approval: dict[str, Any]) -> None:
    """Notify requester and actual reviewer, not all eligible reviewers.

    The approval service already committed the first valid decision. A failed
    receipt must not roll back or misrepresent that decision. Other reviewers'
    Work Inbox resolution continues to derive from committed AuditEvents.
    """
    action_url = url_for(
        'tenant.tenant_detail',
        tenant_id=tenant_id,
        tenant_detail_section='release',
        release_step='approval',
        _anchor='tenant-release-governance',
    )
    plan_sha256 = str(approval['plan_sha256'])
    for role, user_id in (
        ('requester', int(approval['requested_by'])),
        ('reviewer', int(approval['approved_by'])),
    ):
        try:
            create_notification(
                user_id=user_id,
                event_type='kubernetes_tenant_release_handoff_review_recorded',
                status='success',
                title='Tenant Release independent review recorded',
                message=(
                    'Your Release handoff plan was independently reviewed.'
                    if role == 'requester'
                    else 'Your independent Release handoff review was recorded.'
                )
                + ' Provider transfer, verified read-back and Release remain separate.',
                action_url=action_url,
                metadata={
                    'tenant_id': tenant_id,
                    'plan_sha256': plan_sha256,
                    'operation': 'approve_release_handoff',
                    'recipient_role': role,
                    'feedback_delivery': 'activity_center',
                },
            )
        except Exception:
            # The governance decision is already committed. Isolate recipient
            # delivery failures and allow the other receipt to be attempted.
            db.session.rollback()
            current_app.logger.exception(
                'Tenant Release approval committed; %s outcome notification failed.',
                role,
            )
