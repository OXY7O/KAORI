"""Exact runtime activation request, not activation or permission (#5466).

An independent source/EE/target admission must consume a future reviewed
contract. This request cannot enable a connection or dispatch a worker.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

from app.access.scope_policy import lock_explicit_permissions
from app.extensions.db import db
from app.infrastructure_automation.credential_scope_target import CREDENTIAL_USE_PERMISSION
from app.infrastructure_automation.kubernetes.source_policy import SOURCE_CANDIDATE_SHA
from app.infrastructure_automation.remote_preflight_source import REMOTE_CANDIDATE_SHA
from app.infrastructure_automation.remote_preflight_target import (
    SourceOnlyActivationIntent,
    review_source_only_activation_intent,
)
from app.infrastructure_automation.remote_job_review import review_enabled
from app.infrastructure_automation.security_review import begin_security_review_transaction
from app.models.audit import AuditEvent
from app.platform_operations.jobs.fingerprint import payload_fingerprint

_TARGET = 'automation_remote_activation_request'
_ACTION = 'automation.remote.activation_requested'
_STATUS = 'pending_independent_admission'
_PERMISSIONS = {'integrations.manage', 'inventory.view', 'jobs.execute', 'secrets_pki.view', CREDENTIAL_USE_PERMISSION}
_HEX = re.compile(r'[a-f0-9]{64}')
_EE = re.compile(r'sha256:[a-f0-9]{64}')
_MAX_VALIDITY = timedelta(minutes=15)


class RemoteActivationRequestDenied(ValueError):
    """Sanitized denial of invalid or stale activation request."""


def _deny() -> RemoteActivationRequestDenied:
    return RemoteActivationRequestDenied('Remote activation request is unavailable or unqualified.')


def _actor(value: object) -> bool:
    return type(value) is int and value > 0


def _time(value: object) -> datetime | None:
    if not isinstance(value, str) or len(value) > 40:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.utcoffset() == timedelta(0) and parsed.isoformat() == value else None


def _latest_request(connection_id: int) -> AuditEvent | None:
    return (
        AuditEvent.query.filter_by(target_type=_TARGET, target_id=str(connection_id))
        .order_by(AuditEvent.id.desc())
        .populate_existing()
        .with_for_update()
        .first()
    )


def _selector(intent: SourceOnlyActivationIntent) -> dict[str, Any]:
    if (
        type(intent) is not SourceOnlyActivationIntent
        or not _actor(intent.connection_id)
        or not _actor(intent.actor_id)
        or intent.source_sha != SOURCE_CANDIDATE_SHA
        or not isinstance(intent.ee_digest, str)
        or _EE.fullmatch(intent.ee_digest) is None
        or intent.execution_authorized is not False
        or not isinstance(intent.expires_at, datetime)
        or intent.expires_at.utcoffset() is None
        or any(
            not isinstance(value, str) or _HEX.fullmatch(value) is None
            for value in (intent.inventory_fingerprint, intent.host_registry_fingerprint, intent.access_fingerprint)
        )
    ):
        raise _deny()
    return {
        'connection_id': intent.connection_id,
        'requested_by': intent.actor_id,
        'profile_sha': intent.source_sha,
        'remote_candidate_sha': REMOTE_CANDIDATE_SHA,
        'execution_environment_digest': intent.ee_digest,
        'inventory_fingerprint': intent.inventory_fingerprint,
        'host_registry_fingerprint': intent.host_registry_fingerprint,
        'access_fingerprint': intent.access_fingerprint,
    }


def _record(
    intent: SourceOnlyActivationIntent, *, issued_at: datetime, expires_at: datetime
) -> dict[str, Any]:
    selector = _selector(intent)
    if not issued_at < expires_at <= min(intent.expires_at, issued_at + _MAX_VALIDITY):
        raise _deny()
    record = {
        'schema_version': 1,
        'status': _STATUS,
        **selector,
        'issued_at': issued_at.astimezone(UTC).isoformat(),
        'expires_at': expires_at.astimezone(UTC).isoformat(),
        'runtime_activation_authorized': False,
        'execution_authorized': False,
        'mutation_authorized': False,
    }
    return {**record, 'request_fingerprint': payload_fingerprint(record)}


def _current_intent(*, connection_id: int, actor_id: int, now: datetime) -> SourceOnlyActivationIntent:
    intent = review_source_only_activation_intent(connection_id=connection_id, actor_id=actor_id, now=now)
    if (
        intent is None or intent.connection_id != connection_id
        or intent.actor_id != actor_id or intent.expires_at <= now
    ):
        raise _deny()
    _selector(intent)
    return intent


def request_remote_runtime_activation(*, connection_id: int, actor_id: int) -> dict[str, Any]:
    """Persist a bounded request under an explicitly authenticated internal caller.

    Local review only. No public route, CLI impersonation, connection update,
    runtime approval, provider access, or dispatch. Audit commit is mandatory.
    """
    committed = False
    try:
        if not review_enabled() or not _actor(connection_id) or not _actor(actor_id):
            raise _deny()
        begin_security_review_transaction()
        if not lock_explicit_permissions(actor_id, _PERMISSIONS):
            raise _deny()
        now = datetime.now(UTC)
        intent = _current_intent(connection_id=connection_id, actor_id=actor_id, now=now)
        previous = _latest_request(connection_id)
        if previous is not None:
            existing = previous.metadata_json
            if (
                previous.action != _ACTION
                or not isinstance(existing, dict)
                or existing.get('status') != _STATUS
            ):
                raise _deny()
            previous_expiry = _time(existing.get('expires_at'))
            if previous_expiry is None or now < previous_expiry:
                raise _deny()
        fresh_now = datetime.now(UTC)
        fresh = _current_intent(connection_id=connection_id, actor_id=actor_id, now=fresh_now)
        if _selector(fresh) != _selector(intent):
            raise _deny()
        expiry = min(intent.expires_at, fresh.expires_at, fresh_now + _MAX_VALIDITY)
        record = _record(fresh, issued_at=fresh_now, expires_at=expiry)
        db.session.add(AuditEvent(
            actor_user_id=actor_id,
            target_type=_TARGET,
            target_id=str(connection_id),
            action=_ACTION,
            summary='Runtime activation requested; independent admission remains pending.',
            metadata_json=record,
        ))
        db.session.commit()
        committed = True
        return record
    finally:
        if not committed:
            db.session.rollback()


def review_current_activation_request(
    *, connection_id: int, actor_id: int, now: datetime
) -> dict[str, Any] | None:
    """Read exact current request in caller-owned locked transaction; never a permit."""
    if (
        not review_enabled() or not _actor(connection_id) or not _actor(actor_id)
        or not isinstance(now, datetime) or now.utcoffset() is None
        or not lock_explicit_permissions(actor_id, _PERMISSIONS)
    ):
        return None
    try:
        intent = _current_intent(connection_id=connection_id, actor_id=actor_id, now=now)
        row = _latest_request(connection_id)
        if row is None or row.action != _ACTION or row.actor_user_id != actor_id:
            return None
        record = row.metadata_json
        if not isinstance(record, dict):
            return None
        issued, expiry = (_time(record.get(key)) for key in ('issued_at', 'expires_at'))
        if issued is None or expiry is None or not issued <= now < expiry:
            return None
        expected = _record(intent, issued_at=issued, expires_at=expiry)
        if payload_fingerprint(record) != payload_fingerprint(expected):
            return None
        return dict(expected)
    except RemoteActivationRequestDenied:
        return None
