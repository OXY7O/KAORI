"""Opt-in internal Vault provider AlertCase admission using existing KAORI lifecycle.

Not wired to HTTP, Celery, dashboards, routing or notifications. The
read-only candidate planner and source identity remain authoritative.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.access.scope_policy import evaluate_exact_vault_instance_case_scope
from app.extensions.db import db
from app.intelligence.alert_intelligence.vault_provider_plan import (
    _CASE_KEY_RE,
    _MAX_CASES,
    _PROFILE,
    build_vault_provider_case_plan,
)
from app.intelligence.alert_signals.vault_source import (
    SIGNAL_KEY,
    _persisted_utc,
    _utc,
    _validated_binding,
)
from app.models.alert_ops import AlertCase, AlertCaseEvent
from app.models.alert_signal import AlertSignalSnapshot
from app.models.audit import AuditEvent
from app.models.integration import IntegrationBinding
from app.models.user import User

_ENABLE_ENV = 'KAORI_VAULT_PROVIDER_CASE_ADMISSION_ENABLED'
_MAX_CREATE = 10
_MAX_PLAN = 2 * _MAX_CASES
_REQUIRED_PERMISSIONS = (
    'intelligence.decisions.create',
    'intelligence.view',
    'secrets_pki.sync',
    'secrets_pki.view',
)


def _result(status: str, *, created: int = 0, refreshed: int = 0) -> dict[str, int | str]:
    return {'status': status, 'created': created, 'refreshed': refreshed}


def _actor_authorized(actor_id: int) -> bool:
    if type(actor_id) is not int or actor_id < 1:
        return False
    actor = db.session.get(User, actor_id)
    # Global Super Admin permissions are NOT source-scoped authority.
    # Require an explicit active Role with every normalized capability.
    return bool(
        actor is not None
        and actor.is_active
        and actor.role_record is not None
        and actor.role_record.is_active
        and set(_REQUIRED_PERMISSIONS).issubset(actor.role_record.permission_keys())
    )


def _event(case: AlertCase, *, event_type: str, actor_id: int, summary: str) -> None:
    event = AlertCaseEvent()
    event.case_id = case.id
    event.event_type = event_type
    event.actor_user_id = actor_id
    event.summary = summary
    event.metadata_json = {'source_type': 'provider_alert', 'domain': 'secrets_pki'}
    db.session.add(event)


def _audit(case: AlertCase, *, actor_id: int, action: str) -> None:
    audit = AuditEvent()
    audit.actor_user_id = actor_id
    audit.target_type = 'alert_case'
    audit.target_id = case.public_id
    audit.action = action
    audit.summary = 'A qualified Vault Alert Source case was admitted or refreshed.'
    audit.metadata_json = {
        'case_id': case.public_id,
        'source_type': 'provider_alert',
        'domain': 'secrets_pki',
        'asset_key': case.asset_key,
    }
    db.session.add(audit)


def _new_case(
    *,
    case_key: str,
    severity: str,
    vault_id: str,
    binding_id: int,
    source_id: int,
    observed: datetime,
    actor_id: int,
) -> AlertCase:
    """Persist only approved opaque identity and safe ownership metadata."""
    case = AlertCase()
    case.case_key = case_key
    case.fingerprint = None
    case.source_type = 'provider_alert'
    case.source_ref = case_key
    case.rule_key = None
    case.domain = 'secrets_pki'
    case.asset_type = 'vault_instance'
    case.asset_key = vault_id
    case.asset_name = 'Vault Instance'
    case.alert_name = 'Vault Alertmanager source condition'
    case.summary = 'A qualified Vault source observation reported a firing alert.'
    case.severity = severity
    case.source_state = 'firing'
    case.source_state_changed_at = observed
    case.workflow_state = 'open'
    case.routing_state = 'suppressed'
    case.routing_override_reason = 'policy_ineligible'
    case.routing_override_note = None
    case.routing_override_at = observed
    case.routing_override_by_user_id = None
    case.first_seen_at = observed
    case.last_seen_at = observed
    case.labels_json = {}
    case.evidence_json = {
        'correlation_profile': _PROFILE,
        'source_binding_id': binding_id,
        'source_integration_id': source_id,
    }
    db.session.add(case)
    db.session.flush()
    _event(
        case,
        event_type='provider_alert_admitted',
        actor_id=actor_id,
        summary='Vault alert admitted from fresh, qualified committed source evidence.',
    )
    _audit(case, actor_id=actor_id, action='vault_provider_alert_admitted')
    return case


def _qualified_case_candidates(plan: dict[str, object]) -> list[dict[str, Any]] | None:
    """Allow only bounded, suppressed-route committed planner candidates."""
    candidates = plan.get('candidates')
    if (
        plan.get('status') != 'qualified'
        or not isinstance(candidates, list)
        or not 1 <= len(candidates) <= _MAX_PLAN
        or any(
            not isinstance(candidate, dict) or candidate.get('proposed_routing_state') != 'suppressed'
            for candidate in candidates
        )
    ):
        return None
    return candidates


def _eligible_case_identity(case_key: object, severity: object) -> bool:
    return not (
        not isinstance(case_key, str)
        or _CASE_KEY_RE.fullmatch(case_key) is None
        or not isinstance(severity, str)
        or severity not in {'critical', 'warning', 'info'}
    )


def _eligible_existing_provider_case(case: AlertCase | None, *, case_key: str, vault_id: str) -> bool:
    """Only a matching suppressed firing case may be refreshed."""
    return not (
        case is None
        or case.case_key != case_key
        or case.domain != 'secrets_pki'
        or case.asset_key != vault_id
        or case.source_type != 'provider_alert'
        or case.source_state != 'firing'
        or case.workflow_state == 'closed'
        or case.routing_state != 'suppressed'
    )


def _apply_qualified_case_candidates(
    candidates: list[dict[str, Any]],
    *,
    binding: IntegrationBinding,
    source_id: int,
    observed: datetime,
    actor_user_id: int,
) -> tuple[int, int] | None:
    """Apply only qualified candidates within the original caller-owned transaction."""
    changed_create = 0
    changed_refresh = 0
    for candidate in candidates:
        action = candidate['action']
        if action not in {'create_candidate', 'refresh_candidate'}:
            continue
        case_key = candidate.get('case_key')
        severity = candidate.get('severity')
        if not _eligible_case_identity(case_key, severity):
            return None
        # Runtime-validated as strings by the canonical identity qualification.
        case_key = cast(str, case_key)
        severity = cast(str, severity)
        if action == 'create_candidate':
            if candidate.get('existing_case_id') is not None:
                return None
            _new_case(
                case_key=case_key,
                severity=severity,
                vault_id=binding.asset_key,
                binding_id=binding.id,
                source_id=source_id,
                observed=observed,
                actor_id=actor_user_id,
            )
            changed_create += 1
            continue

        existing_id = candidate.get('existing_case_id')
        if type(existing_id) is not int or existing_id < 1:
            return None
        case = db.session.get(AlertCase, existing_id)
        if case is None or not _eligible_existing_provider_case(case, case_key=case_key, vault_id=binding.asset_key):
            return None
        prior = _persisted_utc(case.last_seen_at)
        if prior is not None and observed <= prior:
            continue  # Same generation is idempotent; never duplicate events.
        if case.severity != severity:
            case.previous_severity = case.severity
            case.severity = severity
            case.severity_changed_at = observed
        case.last_seen_at = observed
        _event(
            case,
            event_type='provider_alert_observed',
            actor_id=actor_user_id,
            summary='Vault source condition remains firing in fresh committed evidence.',
        )
        _audit(case, actor_id=actor_user_id, action='vault_provider_alert_observed')
        changed_refresh += 1

    return changed_create, changed_refresh


def admit_vault_provider_cases(
    *,
    binding_id: int,
    actor_user_id: int,
    now: datetime | None = None,
) -> dict[str, int | str]:
    """Explicit, opt-in standalone transaction; never provider-origin recovery.

    IMPORTANT: this internal command intentionally has no production caller.
    Approval to invoke must follow #724 resource-level review and UAT.
    A binding row lock serializes same-source admission on PostgreSQL;
    the existing AlertCase model is reused, never duplicated.
    """
    if os.getenv(_ENABLE_ENV) != 'true':
        return _result('disabled')
    instant = _utc(now or datetime.now(UTC))
    if instant is None or type(binding_id) is not int or binding_id < 1:
        return _result('blocked')
    try:
        if not _actor_authorized(actor_user_id):
            db.session.rollback()
            return _result('forbidden')
        binding = db.session.execute(
            select(IntegrationBinding).where(IntegrationBinding.id == binding_id).with_for_update()
        ).scalar_one_or_none()
        if binding is None:
            db.session.rollback()
            return _result('unavailable')
        eligible = _validated_binding(binding_id, now=instant)
        if eligible is None:
            db.session.rollback()
            return _result('unavailable')
        binding, source = eligible
        # Scope is a separate mandatory, row-locked authorization decision.
        # Neither global RBAC, Super Admin nor a Vault mount grant admits
        # writes to a different Vault instance.
        scope = evaluate_exact_vault_instance_case_scope(
            actor_user_id=actor_user_id,
            instance_id=int(binding.asset_key),
            now=instant,
        )
        if not scope.allowed:
            db.session.rollback()
            return _result('forbidden')
        # Lock the exact source generation while the planner and case writes
        # operate. A concurrent producer updating the snapshot must wait.
        snapshot = db.session.execute(
            select(AlertSignalSnapshot)
            .where(
                AlertSignalSnapshot.domain == 'secrets_pki',
                AlertSignalSnapshot.asset_key == binding.asset_key,
                AlertSignalSnapshot.signal_key == SIGNAL_KEY,
            )
            .with_for_update()
        ).scalar_one_or_none()
        observed = _persisted_utc(snapshot.generated_at) if snapshot is not None else None
        if observed is None or observed > instant:
            db.session.rollback()
            return _result('unavailable')
        plan = build_vault_provider_case_plan(binding_id=binding_id, now=instant)
        candidates = _qualified_case_candidates(plan)
        if candidates is None:
            db.session.rollback()
            return _result('unavailable')

        to_create = [row for row in candidates if row.get('action') == 'create_candidate']
        if len(to_create) > _MAX_CREATE:
            db.session.rollback()
            return _result('capacity_blocked')
        changed = _apply_qualified_case_candidates(
            candidates,
            binding=binding,
            source_id=source.id,
            observed=observed,
            actor_user_id=actor_user_id,
        )
        if changed is None:
            db.session.rollback()
            return _result('blocked')
        changed_create, changed_refresh = changed

        if changed_create or changed_refresh:
            db.session.commit()
        else:
            db.session.rollback()
        return _result(
            'committed' if changed_create or changed_refresh else 'unchanged',
            created=changed_create,
            refreshed=changed_refresh,
        )
    except SQLAlchemyError:
        db.session.rollback()
        return _result('unavailable')
