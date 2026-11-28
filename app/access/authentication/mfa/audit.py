"""Secret-free committed evidence for MFA and authentication policy mutations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from flask import has_request_context, request, session

from app.access.authentication.results import ExternalCredentialProof
from app.models.notification import Notification
from app.models.user import User
from app.platform_operations.notifications.actors import (
    actor_snapshot_for_user,
    system_actor_snapshot,
    unauthenticated_actor_snapshot,
)
from app.platform_operations.notifications.event_catalog import event_category_key

MfaSecurityAction = Literal[
    'mfa_enrollment_started',
    'mfa_enrollment_confirmed',
    'mfa_enrollment_cancelled',
    'mfa_replacement_started',
    'mfa_replacement_confirmed',
    'mfa_replacement_cancelled',
    'mfa_challenge_verified',
    'mfa_challenge_rejected',
    'mfa_recovery_regenerated',
    'mfa_policy_changed',
    'mfa_policy_unchanged',
    'bot_policy_changed',
    'bot_provider_verified',
    'session_policy_changed',
    'session_policy_unchanged',
]


def stage_authentication_security_event(
    user: User,
    *,
    action: MfaSecurityAction,
    authenticated: bool,
    success: bool,
    previous_mode: str | None = None,
    next_mode: str | None = None,
    previous_policy: dict[str, int | bool] | None = None,
    next_policy: dict[str, int | bool] | None = None,
    primary_assurance: Literal['local_current_password', 'ldap_linked_user_bind'] | None = None,
    external_proof: ExternalCredentialProof | None = None,
) -> Notification:
    """Return an audit-only event; caller owns the transaction and commit.

    The event includes no OTP, recovery code, encrypted seed, CAPTCHA token or
    provider secret. Primary-only pending login never claims a verified actor.
    """
    actor = actor_snapshot_for_user(user) if authenticated else unauthenticated_actor_snapshot()
    now = datetime.now(UTC)
    event = Notification()
    event.user_id = user.id
    event.event_type = 'authentication'
    event.category_key = event_category_key('authentication')
    event.actor_key = actor.key
    event.actor_label = actor.label
    event.actor_snapshot_json = actor.as_json()
    event.status = 'success' if success else 'warning'
    event.title = action.replace('_', ' ').title().replace('Mfa ', 'MFA ')
    event.message = 'Authentication security control state recorded.'
    event.detail = 'KAORI committed a security control transition without factor or credential values.'
    event.metadata_json = {
        'audit_schema': 'authentication.security.v1',
        'access_action': action,
        'result': 'success' if success else 'rejected',
        'target_user_id': user.id,
        'previous_policy_mode': previous_mode,
        'new_policy_mode': next_mode,
        'request_method': request.method if has_request_context() else None,
        'request_path': request.path[:200] if has_request_context() else None,
        'session_reference': session.get('auth_session_ref') if authenticated and has_request_context() else None,
        'trigger_type': 'web' if has_request_context() else 'cli',
    }
    if primary_assurance is not None:
        event.metadata_json['primary_assurance'] = primary_assurance
    if external_proof is not None:
        event.metadata_json['provider_id'] = external_proof.provider_id
        event.metadata_json['provider_revision'] = external_proof.revision
        event.metadata_json['provider_link_id'] = external_proof.link_id
    if previous_policy is not None and next_policy is not None:
        event.metadata_json['previous_policy'] = previous_policy
        event.metadata_json['new_policy'] = next_policy
    event.deck_visible = False
    event.read_at = now
    event.created_at = now
    return event


def stage_pending_mfa_cleanup_event(
    *, user_id: int, factor_id: int, kind: Literal['enrollment', 'replacement'], reason: str, now: datetime
) -> Notification:
    """System-owned, audit-only evidence; no HTTP context or credential material."""
    actor = system_actor_snapshot()
    event = Notification()
    event.user_id = user_id
    event.event_type = 'authentication'
    event.category_key = event_category_key('authentication')
    event.actor_key = actor.key
    event.actor_label = actor.label
    event.actor_snapshot_json = actor.as_json()
    event.status = 'success'
    event.title = 'Pending MFA Material Removed'
    event.message = 'KAORI removed invalid pending MFA material.'
    event.detail = 'Active authenticator, recovery codes and session generation were preserved.'
    event.metadata_json = {
        'audit_schema': 'authentication.security.v1',
        'access_action': 'mfa_pending_material_cleanup',
        'result': 'success',
        'target_user_id': user_id,
        'factor_id': factor_id,
        'pending_kind': kind,
        'reason': reason,
        'trigger_type': 'cli',
    }
    event.deck_visible = False
    event.read_at = now
    event.created_at = now
    return event
