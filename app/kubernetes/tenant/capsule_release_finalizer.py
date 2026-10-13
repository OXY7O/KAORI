"""Guarded Capsule Released finalizer (#1230): never a provider PATCH.

A provider-preserving canonical Release requires independently authorized
G2/G3 outcome linked to an immutable PostgreSQL START/readback attempt and
a fresh exhaustive Kubernetes read-back against the original approved source
inventory. A mutable AuditEvent status or G1 preview alone is never sufficient.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.extensions.db import db
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.adapter import runtime_adapter
from app.kubernetes.tenant.capsule_handoff_authority_inventory import observe_capsule_global_quotas
from app.kubernetes.tenant.capsule_handoff_contract import (
    _identity,
    _labels,
    _successor,
    capsule_preservation_digest,
    verify_capsule_cr_preserved,
)
from app.kubernetes.tenant.capsule_handoff_live_patch import (
    _provider_methods,
    _provider_read,
)
from app.kubernetes.tenant.capsule_handoff_related_inventory import (
    _digest,
    _get,
    classify_capsule_related_resource,
)
from app.kubernetes.tenant.capsule_handoff_worklist import build_capsule_handoff_worklist
from app.kubernetes.tenant.capsule_platform_admin_authority import (
    verify_capsule_provider_admin_authority,
    verify_capsule_related_admin_authority,
)
from app.kubernetes.tenant.capsule_successor_acceptance import require_current_capsule_acceptance
from app.kubernetes.tenant.native_platform_admin_authority import require_platform_admin_actor
from app.kubernetes.tenant.release_handoff_approval import (
    _plan_hash,
    latest_release_handoff_approval,
    latest_release_handoff_plan,
)
from app.kubernetes.tenant.release_preflight import _release_dependency_counts
from app.models import Cluster
from app.models.audit import AuditEvent
from app.models.capsule_handoff_ledger import CapsuleHandoffLedgerEvent
from app.models.tenant import (
    Tenant,
    TenantEnvironment,
    TenantLifecycleStatus,
    TenantNamespace,
    TenantNamespaceProvisioningStatus,
)

_EXECUTION_TARGET = 'kubernetes_tenant_release_capsule_handoff_execution'
_PREFLIGHT_TARGET = 'kubernetes_tenant_release_preflight'
_RELEASE_TARGET = 'kubernetes_tenant_release'
_TRANSFER = frozenset(
    {
        'candidate_kaori_metadata_handoff_review',
        'explicit_kaori_metadata_handoff_review',
    }
)


def _source_snapshot(
    *,
    tenant_id: str,
    plan: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Find source preflight from its exact original immutable plan inventory."""
    found: list[dict[str, Any]] = []
    candidates = (
        AuditEvent.query.filter_by(target_type=_PREFLIGHT_TARGET, target_id=tenant_id)
        .order_by(AuditEvent.id.desc())
        .limit(120)
        .all()
    )
    for row in candidates:
        item = row.metadata_json
        if (
            isinstance(item, dict)
            and item.get('handoff_fingerprint') == plan.get('handoff_fingerprint')
            and item.get('handoff_components') == plan.get('handoff_components')
            and item.get('live_provider_identity') == plan.get('provider_identity')
            and isinstance(item.get('capsule_related_inventory'), dict)
        ):
            found.append(item)
    if not found:
        raise ValueError('Original Capsule source provider preflight is unavailable.')
    source = found[0]
    related = source['capsule_related_inventory']
    work = build_capsule_handoff_worklist(plan=plan, related=related)
    if (
        any(
            row['decision']
            in (
                'operator_origin_investigation',
                'operator_selector_investigation',
            )
            for row in work['items']
        )
        or related.get('global_quota', {}).get('blockers')
        or related.get('rbac_lineage', {}).get('blockers')
    ):
        raise ValueError('Capsule source worklist has ambiguous provider/foreign ownership.')
    return related, work


def _committed_full_handoff(
    *,
    tenant_id: str,
    plan: dict[str, Any],
    related: dict[str, Any],
    work: dict[str, Any],
    actor_user_id: int,
) -> dict[str, Any]:
    """Reject every missing START, duplicate attempt, partial or forged receipt."""
    attempts = (
        CapsuleHandoffLedgerEvent.query.filter_by(tenant_id=tenant_id)
        .order_by(CapsuleHandoffLedgerEvent.sequence.asc())
        .limit(4)
        .all()
    )
    if len(attempts) != 2:
        raise ValueError('Capsule requires exact immutable START and terminal readback history.')
    from app.kubernetes.tenant.capsule_handoff_ledger_review import (
        inspect_capsule_ledger_rows,
    )

    checked = inspect_capsule_ledger_rows(
        plan=plan,
        related=related,
        accepted_actor_user_id=actor_user_id,
        rows=attempts,
    )
    if (
        checked.get('status') != 'readback_claim_requires_independent_provider_verification'
        or checked.get('event_count') != 2
        or checked.get('worklist_sha256') != work['inventory_sha256']
    ):
        raise ValueError('Capsule ledger event schema, chronology or readback is invalid.')
    started, terminal = attempts
    first, last = started.event_json, terminal.event_json
    if (
        not isinstance(first, dict)
        or not isinstance(last, dict)
        or started.sequence != 1
        or started.event_type != 'started'
        or terminal.sequence != 2
        or terminal.event_type != 'readback_candidate'
        or terminal.attempt_id != started.attempt_id
        or terminal.previous_event_sha256 != started.event_sha256
        or first.get('event_sha256') != started.event_sha256
        or last.get('event_sha256') != terminal.event_sha256
        or first.get('actor_user_id') != actor_user_id
        or last.get('actor_user_id') != actor_user_id
        or any(
            field not in first or first[field] != plan[field]
            for field in ('tenant_id', 'cluster_id', 'generation', 'plan_sha256', 'handoff_fingerprint')
        )
        or started.worklist_sha256 != work['inventory_sha256']
        or terminal.worklist_sha256 != work['inventory_sha256']
        or first.get('worklist_sha256') != work['inventory_sha256']
        or last.get('worklist_sha256') != work['inventory_sha256']
        or last.get('pending_count') != 0
        or last.get('ambiguous_count') != 0
        or last.get('observed_count') != last.get('expected_count')
        or last.get('transferred_count') != last.get('expected_count')
        or type(last.get('expected_count')) is not int
        or last['expected_count'] < 1
    ):
        raise ValueError('Capsule immutable provider attempt is incomplete or uncertain.')
    from app.kubernetes.tenant.capsule_handoff_attempt_state import _event_checksum

    if _event_checksum(first) != started.event_sha256 or _event_checksum(last) != terminal.event_sha256:
        raise ValueError('Capsule immutable handoff ledger checksum was changed.')
    execution_events = (
        AuditEvent.query.filter_by(target_type=_EXECUTION_TARGET, target_id=tenant_id)
        .order_by(AuditEvent.id.desc())
        .limit(3)
        .all()
    )
    # No known earlier partial/in-progress execution can be overwritten by
    # a later fabricated success in a mutable AuditEvent table.
    if len(execution_events) != 1:
        raise ValueError('Capsule execution history contains missing or replayed outcomes.')
    execution = execution_events[0].metadata_json
    if (
        not isinstance(execution, dict)
        or execution.get('status') != 'provider_handoff_verified'
        or execution.get('provider_handoff_verified') is not True
        or execution.get('whole_scope_readback_verified') is not True
        or execution.get('resource_specific_consent_verified') is not True
        or execution.get('controller_origin_verified') is not False
        or execution.get('controller_generated_rbac_preserved') is not True
        or any(row['kind'] == 'RoleBinding' and row['decision'] in _TRANSFER for row in work['items'])
        or execution.get('provider_authority_verified') is not True
        or execution.get('source_worklist_sha256') != work['inventory_sha256']
        or execution.get('plan_sha256') != plan['plan_sha256']
        or execution.get('handoff_fingerprint') != plan['handoff_fingerprint']
        or execution.get('attempt_id') != started.attempt_id
        or execution.get('start_event_sha256') != started.event_sha256
        or execution.get('readback_sha256') != last.get('readback_sha256')
        or _digest(execution.get('verified_components')) != last.get('readback_sha256')
        or execution.get('actor_user_id') != actor_user_id
        or execution.get('errors') != []
        or execution.get('auto_retry_authorized') is not False
        or not isinstance(execution.get('verified_components'), list)
        or execution.get('verified_resource_count') != work['item_count']
        or len(execution['verified_components']) != work['item_count']
    ):
        raise ValueError('Capsule executor has no canonical complete read-back proof.')
    # Ledger checksum and source are insufficient *alone*. A separate fresh
    # provider verification below must prove all exact resources unchanged.
    return execution


def _current_verified_capsule_scope(
    *,
    cluster: Cluster,
    plan: dict[str, Any],
    related: dict[str, Any],
    work: dict[str, Any],
    execution: dict[str, Any],
) -> list[dict[str, Any]]:
    """Re-read all CR/Namespace/quota/limit/RBAC/global quotas, no mutation."""
    provider = runtime_adapter.build_client(cluster)
    cr = next(i for i in plan['handoff_components'] if i['kind'] == 'CapsuleTenant')
    original_ns = {item['name']: item for item in plan['handoff_components'] if item['kind'] == 'Namespace'}
    source_items = {(item['namespace'], item['kind'], item['name']): item for item in work['items']}
    terminal_items = execution['verified_components']
    indexed = {
        (
            str(item.get('namespace') or '') if item.get('kind') not in ('CapsuleTenant', 'Namespace') else '',
            item.get('kind'),
            item.get('name'),
        ): item
        for item in terminal_items
        if isinstance(item, dict)
    }
    if len(indexed) != len(terminal_items) or set(indexed) != set(source_items):
        raise ValueError('Capsule finalizer provider read-back omits original foreign or transfer objects.')
    owner = _successor(plan['successor_owner'])
    core, rbac, custom = (
        provider.core_api(),
        provider.rbac_authorization_api(),
        provider.custom_objects_api(),
    )
    current_cr = custom.get_cluster_custom_object(
        'capsule.clastix.io',
        'v1beta2',
        'tenants',
        cr['name'],
        _request_timeout=5,
    )
    verify_capsule_cr_preserved(cr, current_cr)
    snapshots = {(row['namespace'], row['kind'], row['name']): row for row in related['resources']}
    # Require fresh independent provider authority on exact approved scope.
    related_candidates = [
        dict(item)
        for item in work['items']
        if item['kind'] in ('ResourceQuota', 'LimitRange', 'RoleBinding') and item['decision'] in _TRANSFER
    ]
    for item in related_candidates:
        item['decision'] = 'explicit_kaori_metadata_handoff_review'
    verify_capsule_related_admin_authority(
        provider=provider,
        candidates=related_candidates,
    )
    from app.kubernetes.tenant.capsule_handoff_contract import _related_provider_invariants

    verified: list[dict[str, Any]] = []
    for key, source in source_items.items():
        ns, kind, name = key
        receipt = indexed[key]
        if (
            not isinstance(receipt, dict)
            or receipt.get('kind') != kind
            or receipt.get('name') != name
            or receipt.get('uid') != source['uid']
            or not isinstance(receipt.get('resource_version'), str)
            or not receipt['resource_version']
        ):
            raise ValueError('Capsule terminal proof has a changed UID/RV or resource identity.')
        if kind == 'CapsuleTenant':
            live = current_cr
        elif kind == 'GlobalResourceQuota':
            # Verified using a complete, version-pinned GlobalResourceQuota
            # collection below. Do not count one uninspected row as preserved.
            verified.append({**receipt, 'namespace': ''})
            continue
        else:
            read, _ = _provider_methods(core=core, rbac=rbac, kind=kind)
            live = _provider_read(
                read,
                kind=kind,
                name=name,
                namespace=name if kind == 'Namespace' else ns,
            )
        current_name, uid, rv = _identity(live)
        if (current_name, uid, rv) != (name, source['uid'], receipt['resource_version']):
            raise ValueError('Capsule provider changed since terminal handoff read-back.')
        if kind == 'CapsuleTenant':
            if receipt.get('state') != 'preserved':
                raise ValueError('Capsule CR preservation was not verified.')
        elif kind == 'Namespace':
            if source['decision'] in _TRANSFER:
                if (
                    receipt.get('state') != 'provider_markers_transferred'
                    or _labels(live).get('app.kubernetes.io/managed-by') != owner
                    or any(k.startswith('kaori.io/') for k in _labels(live))
                    or _digest(capsule_preservation_digest(live)) != receipt.get('preservation_sha256')
                ):
                    raise ValueError('Capsule Namespace handoff or provider policy is not preserved.')
            elif (
                receipt.get('state') != 'preserved'
                or rv != source['resource_version']
                or _labels(live).get('app.kubernetes.io/managed-by') == 'kaori'
                or any(key.startswith('kaori.io/') for key in _labels(live))
            ):
                raise ValueError('Foreign Capsule Namespace changed or retains KAORI ownership.')
        else:
            original = snapshots[key]
            if kind == 'RoleBinding':
                policy = {
                    'roleRef': _get(live, 'role_ref') or _get(live, 'roleRef'),
                    'subjects': _get(live, 'subjects'),
                }
            else:
                policy = _get(live, 'spec')
            if policy is None or _digest(policy) != original['policy_sha256']:
                raise ValueError('Capsule quota, limits or RBAC subjects/policy changed.')
            if source['decision'] in _TRANSFER:
                if (
                    receipt.get('state') != 'provider_markers_transferred'
                    or _labels(live).get('app.kubernetes.io/managed-by') != owner
                    or any(k.startswith('kaori.io/') for k in _labels(live))
                    or receipt.get('preservation_sha256') != _digest(_related_provider_invariants(live))
                ):
                    raise ValueError('Capsule related-object ownership or preservation proof missing.')
            elif source['decision'] == 'preserve_foreign_provider_control':
                current, findings = classify_capsule_related_resource(
                    resource=live,
                    kind=kind,
                    namespace=ns,
                    tenant_id=plan['tenant_id'],
                    capsule_name=cr['name'],
                    capsule_uid=cr['uid'],
                )
                if receipt.get('state') != 'preserved' or findings or current != original:
                    raise ValueError('Foreign Capsule quota, limit or RBAC changed since source approval.')
            else:
                raise ValueError('Ambiguous Capsule related-object provider authority.')
        verified.append({**receipt, 'namespace': '' if kind in ('CapsuleTenant', 'Namespace') else ns})
    global_quota = observe_capsule_global_quotas(custom=custom, tenant_name=cr['name'])
    if global_quota.get('scope_sha256') != related['global_quota']['scope_sha256'] or global_quota.get('blockers'):
        raise ValueError('Capsule shared GlobalResourceQuota changed during Release.')
    global_rows = {row['name']: row for row in global_quota['resources']}
    for row in verified:
        if row['kind'] == 'GlobalResourceQuota':
            observed = global_rows.get(row['name'])
            if (
                not observed
                or observed.get('uid') != row['uid']
                or observed.get('resource_version') != row['resource_version']
                or row.get('state') != 'preserved'
            ):
                raise ValueError('Capsule GlobalResourceQuota inventory is stale.')
    if len(verified) != work['item_count']:
        raise ValueError('Capsule finalizer did not inspect the entire source inventory.')
    return verified


def release_verified_capsule_tenant_committed(
    *,
    tenant_id: str,
    actor_user_id: int,
    plan_sha256: str,
    approved: bool,
) -> dict[str, Any]:
    """Canonical atomic Released+capacity exclusion after definitive provider evidence."""
    if not approved:
        raise ValueError('Explicit Capsule provider-preserving Release approval is required.')
    require_platform_admin_actor(actor_user_id)
    plan = latest_release_handoff_plan(tenant_id)
    approval = latest_release_handoff_approval(tenant_id)
    if (
        not plan
        or not approval
        or plan.get('provider') != 'capsule'
        or plan.get('tenant_id') != tenant_id
        or _plan_hash(plan) != plan_sha256
        or plan.get('plan_sha256') != plan_sha256
        or approval.get('plan_sha256') != plan_sha256
        or approval.get('status') != 'acknowledged_pending_provider_handoff'
        or approval.get('approved_by') == plan.get('requested_by')
    ):
        raise ValueError('Current independently approved Capsule Release plan required.')
    accepted = require_current_capsule_acceptance(
        tenant_id=tenant_id,
        plan=plan,
        approval=approval,
    )
    if accepted.get('accepted_by') != actor_user_id:
        raise ValueError('Only the accepted X.509 Platform Admin may finalize Capsule Release.')
    tenant = Tenant.query.filter_by(id=tenant_id).with_for_update().one_or_none()
    if (
        tenant is None
        or tenant.lifecycle_status != TenantLifecycleStatus.READY.value
        or tenant.provider_key != 'capsule'
        or tenant.provider_state != 'capsule'
        or tenant.reconciliation_authority != 'capsule'
        or tenant.ownership_status != 'adopted'
        or tenant.cluster_id != plan.get('cluster_id')
        or tenant.generation != plan.get('generation')
    ):
        raise ValueError('Capsule Tenant generation changed before Release.')
    rows = (
        TenantNamespace.query.join(
            TenantEnvironment,
            TenantNamespace.tenant_environment_id == TenantEnvironment.id,
        )
        .filter(TenantEnvironment.tenant_id == tenant_id)
        .order_by(TenantNamespace.id.asc())
        .with_for_update()
        .all()
    )
    namespaces = {item['name']: item for item in plan['handoff_components'] if item['kind'] == 'Namespace'}
    if (
        not rows
        or len(rows) != len(namespaces)
        or any(
            row.namespace not in namespaces
            or row.provisioning_status != TenantNamespaceProvisioningStatus.READY.value
            or row.ownership_status != 'adopted'
            or row.cluster_id != tenant.cluster_id
            or row.provider_reference != namespaces[row.namespace]['uid']
            for row in rows
        )
    ):
        raise ValueError('Capsule Namespace lineage or original Ready inventory changed.')
    if any(type(v) is not int or v != 0 for v in _release_dependency_counts(tenant_id).values()):
        raise ValueError('Active Tenant dependencies prevent Capsule Release.')
    from app.kubernetes.tenant.capsule_handoff_start_writer import (
        _require_postgres_ledger_write_once_guards,
    )

    # G4 is categorically denied on SQLite, missing write-once triggers,
    # privileged DB roles or uncertain WAL durability.
    session = db.session()
    if session.get_bind().dialect.name != 'postgresql':
        raise ValueError('Capsule Released requires independently guarded PostgreSQL history.')
    _require_postgres_ledger_write_once_guards(session)
    source, work = _source_snapshot(tenant_id=tenant_id, plan=plan)
    execution = _committed_full_handoff(
        tenant_id=tenant_id,
        plan=plan,
        related=source,
        work=work,
        actor_user_id=actor_user_id,
    )
    if execution.get('provider_username') != accepted.get('provider_username') or execution.get(
        'provider_credential_id'
    ) != accepted.get('provider_credential_id'):
        raise ValueError('Capsule handoff executor credential differs from accepted successor.')
    cluster = db.session.get(Cluster, tenant.cluster_id)
    if cluster is None:
        raise ValueError('Canonical Capsule provider cluster is unavailable.')
    authority = verify_capsule_provider_admin_authority(
        cluster=cluster,
        components=plan['handoff_components'],
    )
    if any(
        authority.get(key) != accepted.get(key)
        for key in ('provider_username', 'provider_groups', 'provider_credential_id')
    ):
        raise ValueError('Capsule X.509 successor provider authority changed.')
    confirmed = _current_verified_capsule_scope(
        cluster=cluster,
        plan=plan,
        related=source,
        work=work,
        execution=execution,
    )
    current_ns = {row['name']: row for row in confirmed if row['kind'] == 'Namespace'}
    if len(current_ns) != len(rows):
        raise ValueError('Capsule finalizer Namespace read-back coverage is incomplete.')
    # Recheck all canonical state inside the same locked transaction; no
    # provider modification here. Capacity commitment queries automatically
    # exclude Released rows and parent Released Tenant; no double subtraction
    # or destruction of historical Resource Profile links.
    current_plan = latest_release_handoff_plan(tenant_id)
    if (
        not current_plan
        or current_plan.get('plan_sha256') != plan_sha256
        or tenant.lifecycle_status != TenantLifecycleStatus.READY.value
        or any(type(v) is not int or v != 0 for v in _release_dependency_counts(tenant_id).values())
    ):
        raise ValueError('Capsule Release authority or dependencies changed before commit.')
    now = datetime.now(UTC).isoformat()
    result = {
        'status': 'released',
        'release_mode': 'managed_handoff',
        'tenant_id': tenant_id,
        'cluster_id': tenant.cluster_id,
        'generation': tenant.generation,
        'provider': 'capsule',
        'plan_sha256': plan_sha256,
        'handoff_fingerprint': plan['handoff_fingerprint'],
        'successor_owner': plan['successor_owner'],
        'authority_mode': 'platform_admin_governed',
        'approved_by_platform_admin': actor_user_id,
        'provider_username': authority['provider_username'],
        'provider_credential_id': authority['provider_credential_id'],
        'released_at': now,
        'released_namespace_count': len(rows),
        'verified_resource_count': len(confirmed),
        'verified_components': confirmed,
        'start_event_sha256': execution['start_event_sha256'],
        'readback_sha256': execution['readback_sha256'],
        'provider_handoff_verified': True,
        'successor_consent_verified': True,
        'provider_resource_deleted': False,
        'provider_spec_modified': False,
        'foreign_rbac_modified': False,
        'secret_material_persisted': False,
    }
    for row in rows:
        record_evidence = dict(row.provisioning_evidence_json or {})
        record_evidence['release_governance'] = {
            'status': 'released',
            'release_mode': 'managed_handoff',
            'tenant_id': tenant_id,
            'generation': row.generation,
            'provider_uid': row.provider_reference,
            'provider_resource_version': current_ns[row.namespace]['resource_version'],
            'released_at': now,
            'plan_sha256': plan_sha256,
            'successor_owner': plan['successor_owner'],
            'provider_handoff_verified': True,
            'provider_preserved': True,
        }
        row.provisioning_evidence_json = record_evidence
        row.provisioning_status = TenantNamespaceProvisioningStatus.RELEASED.value
        row.provisioning_message = 'Capsule governance Released; verified provider resources preserved.'
    prior = dict(tenant.provider_evidence_json or {})
    prior['release_governance'] = result
    tenant.provider_evidence_json = prior
    tenant.lifecycle_status = TenantLifecycleStatus.RELEASED.value
    db.session.add(
        AuditEvent(
            actor_user_id=actor_user_id,
            target_type=_RELEASE_TARGET,
            target_id=tenant_id,
            action='tenant.release.capsule_verified_governance_released',
            summary='Verified Capsule handoff; canonical Tenant/Namespace Released and provider resources preserved.',
            metadata_json=result,
        )
    )
    db.session.commit()
    return result
