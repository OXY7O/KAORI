"""Governed Release handoff request and independent approval evidence.

This is an explicit *pre-execution* checkpoint, not an external-owner
transfer or permission to set a Tenant Released. Provider remains authoritative.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Any

from app.extensions.db import db
from app.kubernetes.tenant.release_handoff_inventory import handoff_fingerprint
from app.kubernetes.tenant.release_preflight import (
    review_tenant_release_preflight_committed,
)
from app.models.audit import AuditEvent
from app.models.tenant import Tenant, TenantLifecycleStatus

_PLAN_TARGET = 'kubernetes_tenant_release_handoff_plan'
_APPROVAL_TARGET = 'kubernetes_tenant_release_handoff_approval'
_MAX_AGE_SECONDS = 900
_SAFE_REFERENCE = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.@:/-]{2,119}\Z')
_EXPECTED_HANDOFF_PREFIXES = (
    'Adoption performed KAORI-owned provider mutations.',
    'Capsule allocation was modified by KAORI;',
)
_EXPECTED_HANDOFF_FRAGMENTS = (
    'has KAORI-managed allocation; explicit provider handoff is required.',
    'has KAORI-mutated Namespace provider controls; independently approved external handoff is required.',
    'KAORI-linked allocation ownership requires independently approved external handoff',
)
_REQUIRED_DEPENDENCIES = frozenset({
    'credentials', 'Access Grants', 'Memberships', 'enabled Groups',
    'managed resources', 'advanced capabilities', 'domain reservations',
    'exposure policies',
})
_PLAN_HASH_FIELDS = (
    'tenant_id', 'cluster_id', 'generation', 'provider', 'handoff_fingerprint',
    'provider_identity', 'successor_owner', 'change_reference',
    'requested_by', 'requested_at',
)


def _plan_hash(contract: dict[str, Any]) -> str:
    payload = {key: contract.get(key) for key in _PLAN_HASH_FIELDS}
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()
    ).hexdigest()


def _valid_reference(value: str, *, name: str) -> str:
    normalized = (value or '').strip()
    if not _SAFE_REFERENCE.fullmatch(normalized):
        raise ValueError(f'{name} requires a non-secret 3–120 character reference.')
    return normalized


def _checked_recently(checked_at: object) -> bool:
    try:
        timestamp = datetime.fromisoformat(str(checked_at or ''))
    except ValueError:
        return False
    if timestamp.tzinfo is None:
        return False
    age = (datetime.now(UTC) - timestamp).total_seconds()
    return 0 <= age <= _MAX_AGE_SECONDS


def _complete_provider_snapshot(evidence: dict[str, Any]) -> None:
    identities = evidence.get('live_provider_identity')
    components = evidence.get('handoff_components')
    if (
        evidence.get('status') not in {'blocked', 'handoff_review_required'}
        or not _checked_recently(evidence.get('checked_at'))
        or not isinstance(identities, list) or not identities
        or not isinstance(components, list) or not components
        or not evidence.get('handoff_fingerprint')
    ):
        raise ValueError('Refresh a complete Release preflight before preparing handoff.')
    if not all(
        isinstance(item, dict)
        and all(item.get(field) for field in ('kind', 'name', 'uid', 'resource_version'))
        for item in identities + components
    ):
        raise ValueError('Provider handoff identity evidence is incomplete.')
    if handoff_fingerprint(components) != evidence['handoff_fingerprint']:
        raise ValueError('Committed provider handoff fingerprint does not match its components.')
    # A Kubernetes resource is unique by scope/kind/name. A duplicated or
    # conflicting committed inventory cannot define one exact transfer target,
    # even when a hash was recomputed over the ambiguous list.
    identity_keys = [(item['kind'], item['name']) for item in identities]
    component_keys = [
        (item.get('namespace') or '', item['kind'], item['name'])
        for item in components
    ]
    if (
        len(identity_keys) != len(set(identity_keys))
        or len(component_keys) != len(set(component_keys))
    ):
        raise ValueError('Provider handoff inventory has duplicated or ambiguous resource identity.')
    namespace_identities = {
        (row['name'], row['uid']) for row in identities if row['kind'] == 'Namespace'
    }
    namespace_components = {
        (row['name'], row['uid']) for row in components if row['kind'] == 'Namespace'
    }
    if namespace_components != namespace_identities:
        raise ValueError('Native/Capsule Namespace handoff coverage is incomplete.')


def _can_confirm_plan(snapshot: dict[str, Any]) -> None:
    _complete_provider_snapshot(snapshot)
    counts = snapshot.get('dependency_counts')
    if (
        not isinstance(counts, dict)
        or not _REQUIRED_DEPENDENCIES.issubset(counts)
        or any(type(v) is not int or v != 0 for v in counts.values())
    ):
        raise ValueError('Clear and verify every active Tenant dependency before handoff approval.')
    components = snapshot['handoff_components']
    if any(row.get('handoff') == 'owner_review_required' for row in components):
        raise ValueError('Conflicting provider ownership markers require external review.')
    if any(row.get('handoff') not in {'external_acceptance_required', 'observe_only'} for row in components):
        raise ValueError('Unsupported or missing ownership handoff classification.')
    if snapshot.get('handoff_required_count') != sum(
        row['handoff'] == 'external_acceptance_required' for row in components
    ):
        raise ValueError('Committed handoff count is inconsistent with provider evidence.')
    if not any(row.get('handoff') == 'external_acceptance_required' for row in components):
        raise ValueError('No verified KAORI-linked resource requires external handoff.')
    blockers = snapshot.get('blockers') or []
    if not isinstance(blockers, list) or any(not isinstance(x, str) for x in blockers):
        raise ValueError('Release blocker evidence is incomplete.')
    unexpected = [
        row for row in blockers
        if not row.startswith(_EXPECTED_HANDOFF_PREFIXES)
        and not any(fragment in row for fragment in _EXPECTED_HANDOFF_FRAGMENTS)
    ]
    if unexpected:
        raise ValueError('Unresolved provider, identity or governance blockers prevent approval.')


def _latest_event(*, tenant_id: str, target_type: str) -> dict[str, Any] | None:
    row = (
        AuditEvent.query.filter_by(target_type=target_type, target_id=tenant_id)
        .order_by(AuditEvent.id.desc()).first()
    )
    return dict(row.metadata_json or {}) if row else None


def latest_release_handoff_plan(tenant_id: str) -> dict[str, Any] | None:
    return _latest_event(tenant_id=tenant_id, target_type=_PLAN_TARGET)


def latest_release_handoff_approval(tenant_id: str) -> dict[str, Any] | None:
    return _latest_event(tenant_id=tenant_id, target_type=_APPROVAL_TARGET)


def handoff_plan_preparation_state(
    plan: dict[str, Any] | None, approval: dict[str, Any] | None,
) -> str:
    """Single-plan policy shared by backend and read-only Registry presentation.

    An acknowledged plan remains authoritative until an explicit governed
    successor/handoff restart exists; an expired *unacknowledged* plan can be
    replaced by a fresh request. Unknown states are blocked, not ignored.
    """
    if plan is None:
        return 'available'
    sha = plan.get('plan_sha256')
    if (
        sha and approval and approval.get('plan_sha256') == sha
        and approval.get('status') == 'acknowledged_pending_provider_handoff'
    ):
        return 'acknowledged'
    if plan.get('status') != 'pending_independent_approval':
        return 'blocked'
    # Treat malformed/future timestamps as inconsistent committed evidence,
    # not as an expired request that any operator may replace.
    try:
        requested_at = datetime.fromisoformat(str(plan.get('requested_at') or ''))
    except ValueError:
        return 'blocked'
    if requested_at.tzinfo is None or requested_at > datetime.now(UTC):
        return 'blocked'
    return 'pending' if _checked_recently(plan.get('requested_at')) else 'expired'


def _require_no_active_handoff_plan(*, tenant_id: str, actor_user_id: int) -> None:
    plan = latest_release_handoff_plan(tenant_id)
    state = handoff_plan_preparation_state(
        plan, latest_release_handoff_approval(tenant_id),
    )
    if state == 'expired' and str(plan.get('requested_by')) != str(actor_user_id):
        raise ValueError(
            'Only the original requester may renew an expired handoff plan. '
            'A change of requester requires an explicitly governed reassignment.'
        )
    if state == 'pending':
        raise ValueError(
            'A current handoff plan is awaiting independent approval. '
            'Review the existing plan; preparing another would replace the request.'
        )
    if state == 'acknowledged':
        raise ValueError(
            'The current handoff plan was independently acknowledged and awaits '
            'external provider handoff. A new plan requires a separate governed restart.'
        )
    if state == 'blocked':
        raise ValueError('Handoff plan state is not eligible for replacement.')


def prepare_release_handoff_plan_committed(
    *, tenant_id: str, actor_user_id: int, successor_owner: str, change_reference: str
) -> dict[str, Any]:
    """Record a non-secret proposed successor; make no changes to Kubernetes."""
    successor = _valid_reference(successor_owner, name='Successor owner')
    reference = _valid_reference(change_reference, name='Change record')
    tenant = db.session.get(Tenant, tenant_id)
    if (
        tenant is None or tenant.ownership_status != 'adopted'
        or tenant.lifecycle_status != TenantLifecycleStatus.READY.value
    ):
        raise ValueError('Only Ready externally adopted Tenants can prepare a Release handoff.')
    snapshot = review_tenant_release_preflight_committed(
        tenant_id=tenant_id, actor_user_id=actor_user_id
    )
    _complete_provider_snapshot(snapshot)
    # Live review commits its AuditEvent, so take the row lock *after* review.
    locked = Tenant.query.filter_by(id=tenant_id).with_for_update().one_or_none()
    if (
        locked is None or locked.lifecycle_status != TenantLifecycleStatus.READY.value
        or locked.ownership_status != 'adopted'
    ):
        raise ValueError('Tenant authority changed while preparing handoff.')
    # The Tenant row lock serializes concurrent preparations/acknowledgments:
    # evaluate *committed* plan/approval after locking and before writing.
    _require_no_active_handoff_plan(tenant_id=tenant_id, actor_user_id=actor_user_id)
    planned_at = datetime.now(UTC).isoformat()
    contract = {
        'tenant_id': tenant_id,
        'cluster_id': snapshot['cluster_id'],
        'generation': snapshot['generation'],
        'provider': snapshot['provider'],
        'handoff_fingerprint': snapshot['handoff_fingerprint'],
        'provider_identity': snapshot['live_provider_identity'],
        'successor_owner': successor,
        'change_reference': reference,
        'requested_by': actor_user_id,
        'requested_at': planned_at,
    }
    plan_hash = _plan_hash(contract)
    evidence = {
        **contract,
        'plan_sha256': plan_hash,
        'status': 'pending_independent_approval',
        'handoff_components': snapshot['handoff_components'],
        'dependency_counts': snapshot['dependency_counts'],
        'blockers': snapshot['blockers'],
        'provider_mutation_performed': False,
        'provider_handoff_verified': False,
        'release_authorized': False,
    }
    db.session.add(AuditEvent(
        actor_user_id=actor_user_id,
        target_type=_PLAN_TARGET, target_id=tenant_id,
        action='tenant.release.handoff_plan_prepared',
        summary='Prepared successor handoff plan; provider and governance unchanged.',
        metadata_json=evidence,
    ))
    db.session.commit()
    return evidence


def approve_release_handoff_plan_committed(
    *, tenant_id: str, actor_user_id: int, plan_sha256: str, approved: bool
) -> dict[str, Any]:
    """Second operator acknowledges a current plan; does NOT execute handoff."""
    if not approved:
        raise ValueError('Explicit second-operator handoff acknowledgement is required.')
    plan = latest_release_handoff_plan(tenant_id)
    if not plan or plan.get('status') != 'pending_independent_approval':
        raise ValueError('Prepare a Release handoff plan before acknowledgement.')
    if (
        plan.get('tenant_id') != tenant_id
        or plan_sha256 != plan.get('plan_sha256')
        or len(plan_sha256) != 64
        or _plan_hash(plan) != plan_sha256
    ):
        raise ValueError('Handoff plan changed; review the latest evidence.')
    if actor_user_id == plan.get('requested_by'):
        raise ValueError('Handoff requires an independent approver, not the requesting operator.')
    if not _checked_recently(plan.get('requested_at')):
        raise ValueError('Handoff approval window expired; prepare a new plan.')
    # Provider review commits the preflight AuditEvent. Acquire the row lock
    # afterwards and recheck both plan identity and prior approval under lock.
    fresh = review_tenant_release_preflight_committed(
        tenant_id=tenant_id, actor_user_id=actor_user_id
    )
    _can_confirm_plan(fresh)
    tenant = Tenant.query.filter_by(id=tenant_id).with_for_update().one_or_none()
    if (
        tenant is None or tenant.lifecycle_status != TenantLifecycleStatus.READY.value
        or tenant.ownership_status != 'adopted'
    ):
        raise ValueError('Tenant authority changed during handoff review.')
    current = latest_release_handoff_plan(tenant_id)
    if not current or current.get('plan_sha256') != plan_sha256:
        raise ValueError('Another handoff plan replaced this approval request.')
    existing = latest_release_handoff_approval(tenant_id)
    if existing and existing.get('plan_sha256') == plan_sha256:
        raise ValueError('This handoff plan has already been acknowledged.')
    if (
        fresh.get('tenant_id') != tenant_id
        or fresh.get('cluster_id') != plan['cluster_id']
        or fresh.get('generation') != plan['generation']
        or fresh.get('provider') != plan['provider']
        or fresh.get('handoff_fingerprint') != plan['handoff_fingerprint']
        or fresh.get('live_provider_identity') != plan['provider_identity']
    ):
        raise ValueError('Provider or governance evidence changed; prepare a new plan.')
    accepted = {
        'tenant_id': tenant_id,
        'plan_sha256': plan_sha256,
        'requested_by': plan['requested_by'],
        'approved_by': actor_user_id,
        'successor_owner': plan['successor_owner'],
        'change_reference': plan['change_reference'],
        'handoff_fingerprint': fresh['handoff_fingerprint'],
        'approved_at': datetime.now(UTC).isoformat(),
        'status': 'acknowledged_pending_provider_handoff',
        'provider_mutation_performed': False,
        'provider_handoff_verified': False,
        'release_authorized': False,
    }
    db.session.add(AuditEvent(
        actor_user_id=actor_user_id,
        target_type=_APPROVAL_TARGET, target_id=tenant_id,
        action='tenant.release.handoff_acknowledged',
        summary='Independent handoff acknowledgement; external provider ownership not yet transferred.',
        metadata_json=accepted,
    ))
    db.session.commit()
    return accepted
