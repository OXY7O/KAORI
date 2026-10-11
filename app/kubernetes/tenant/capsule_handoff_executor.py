"""One-attempt guarded Capsule provider metadata handoff (#1229).

External Capsule controller remains authoritative. Requires the current
approved plan, independently accepted human X.509 successor, explicit exact
worklist confirmation and installed PostgreSQL write-once START guards.
Never replaces/deletes objects or retries partial/unknown PATCH outcomes.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.extensions.db import db
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.adapter import runtime_adapter
from app.kubernetes.tenant.capsule_handoff_contract import (
    _identity, _labels, _related_provider_invariants,
    build_capsule_namespace_handoff_patch,
    build_capsule_related_metadata_handoff_patch,
    capsule_preservation_digest, classify_capsule_related_metadata_readback,
    verify_capsule_cr_preserved,
    verify_capsule_namespace_preview, verify_capsule_related_metadata_preview,
)
from app.kubernetes.tenant.capsule_handoff_authority_inventory import observe_capsule_global_quotas
from app.kubernetes.tenant.capsule_handoff_attempt_state import (
    _event_checksum, project_capsule_attempt_history,
)
from app.kubernetes.tenant.capsule_handoff_live_patch import (
    _provider_methods, _provider_read, _provider_patch,
    _require_source_still_unchanged,
)
from app.kubernetes.tenant.capsule_handoff_preview_service import (
    _TARGET as _PREVIEW_TARGET,
)
from app.kubernetes.tenant.capsule_handoff_recovery import (
    capture_capsule_namespace_baseline, classify_capsule_namespace_handoff,
)
from app.kubernetes.tenant.capsule_handoff_related_inventory import (
    _digest, _get, _strings, classify_capsule_related_resource,
)
from app.kubernetes.tenant.capsule_handoff_start_writer import (
    _require_postgres_ledger_write_once_guards, build_capsule_start_candidate,
)
from app.kubernetes.tenant.capsule_handoff_worklist import build_capsule_handoff_worklist
from app.kubernetes.tenant.capsule_platform_admin_authority import (
    verify_capsule_provider_admin_authority, verify_capsule_related_admin_authority,
)
from app.kubernetes.tenant.capsule_successor_acceptance import require_current_capsule_acceptance
from app.kubernetes.tenant.native_platform_admin_authority import require_platform_admin_actor
from app.kubernetes.tenant.release_handoff_approval import (
    _can_confirm_plan, _capsule_g1_only_origin_obligation, _checked_recently, _plan_hash,
    latest_release_handoff_approval, latest_release_handoff_plan,
)
from app.kubernetes.tenant.release_preflight import (
    _release_dependency_counts, review_tenant_release_preflight_committed,
)
from app.models import Cluster
from app.models.audit import AuditEvent
from app.models.capsule_handoff_ledger import CapsuleHandoffLedgerEvent
from app.models.tenant import Tenant, TenantLifecycleStatus

_TARGET = 'kubernetes_tenant_release_capsule_handoff_execution'
_LEGACY_TARGET = _TARGET
_CANDIDATE = frozenset({
    'candidate_kaori_metadata_handoff_review',
    'explicit_kaori_metadata_handoff_review',
})
_RELATED = frozenset({'ResourceQuota', 'LimitRange', 'RoleBinding'})


def _exact_current_scope(
    *, tenant_id: str, actor_user_id: int, plan_sha256: str,
    expected_worklist_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], Any, Any, dict[str, Any]]:
    """Current independently accepted provider authority and digest-bound G0."""
    require_platform_admin_actor(actor_user_id)
    plan = latest_release_handoff_plan(tenant_id)
    approval = latest_release_handoff_approval(tenant_id)
    if (
        not plan or not approval or plan.get('provider') != 'capsule'
        or plan.get('tenant_id') != tenant_id
        or plan.get('plan_sha256') != plan_sha256
        or _plan_hash(plan) != plan_sha256
        or approval.get('plan_sha256') != plan_sha256
        or approval.get('status') != 'acknowledged_pending_provider_handoff'
        or approval.get('approved_by') == plan.get('requested_by')
        or not _checked_recently(approval.get('approved_at'))
        or not _checked_recently(plan.get('requested_at'))
    ):
        raise ValueError('Approved Capsule handoff plan is missing, stale or changed.')
    acceptance = require_current_capsule_acceptance(
        tenant_id=tenant_id, plan=plan, approval=approval,
    )
    if acceptance.get('accepted_by') != actor_user_id:
        raise ValueError('Only the accepted successor X.509 Platform Admin may transfer Capsule metadata.')
    tenant = db.session.get(Tenant, tenant_id)
    if (
        tenant is None or tenant.lifecycle_status != TenantLifecycleStatus.READY.value
        or tenant.provider_key != 'capsule' or tenant.provider_state != 'capsule'
        or tenant.reconciliation_authority != 'capsule'
        or tenant.ownership_status != 'adopted'
        or tenant.cluster_id != plan.get('cluster_id')
        or tenant.generation != plan.get('generation')
        or any(type(v) is not int or v != 0
               for v in _release_dependency_counts(tenant_id).values())
    ):
        raise ValueError('Capsule Tenant generation or Release dependencies changed.')
    preflight = review_tenant_release_preflight_committed(
        tenant_id=tenant_id, actor_user_id=actor_user_id,
    )
    related = preflight.get('capsule_related_inventory')
    if (
        not isinstance(related, dict)
        or preflight.get('handoff_fingerprint') != plan.get('handoff_fingerprint')
        or preflight.get('handoff_components') != plan.get('handoff_components')
        or preflight.get('live_provider_identity') != plan.get('provider_identity')
        or preflight.get('dependency_counts') != plan.get('dependency_counts')
        or not isinstance(preflight.get('blockers'), list)
        or related.get('global_quota', {}).get('blockers')
        or related.get('rbac_lineage', {}).get('blockers')
        or not isinstance(related.get('blockers'), list)
        or any(not _capsule_g1_only_origin_obligation(preflight, warning)
               for warning in related['blockers'])
    ):
        raise ValueError('Capsule approved provider identity, RBAC or dependencies drifted.')
    # Approved G1 explicitly tolerates only canonical handoff obligations
    # (including managed allocations) while rejecting *other* blockers.
    _can_confirm_plan(preflight)
    worklist = build_capsule_handoff_worklist(plan=plan, related=related)
    if (
        worklist['inventory_sha256'] != expected_worklist_sha256
        or any(item['decision'] in ('operator_origin_investigation', 'operator_selector_investigation')
               for item in worklist['items'])
        or any(item['kind'] == 'RoleBinding' and item['decision'] in _CANDIDATE
               for item in worklist['items'])
    ):
        raise ValueError('Capsule worklist is changed, ambiguous or contains unverified KAORI RoleBinding origin.')
    # Human consent must bind the same SHA and exact item count seen via
    # actual Kubernetes server-side dryRun in the canonical UI.
    previews = (
        AuditEvent.query.filter_by(target_type=_PREVIEW_TARGET, target_id=tenant_id)
        .order_by(AuditEvent.id.desc()).limit(1).all()
    )
    preview = dict(previews[0].metadata_json or {}) if previews else {}
    if (
        preview.get('status') != 'complete_scope_server_dry_run_only'
        or preview.get('plan_sha256') != plan_sha256
        or preview.get('source_worklist_sha256') != expected_worklist_sha256
        or preview.get('transfer_items') != [
            {
                'kind': item['kind'], 'namespace': item['namespace'],
                'name': item['name'], 'uid': item['uid'],
                'resource_version': item['resource_version'],
            }
            for item in worklist['items'] if item['decision'] in _CANDIDATE
        ]
        or preview.get('unverified_kaori_rolebinding_origin') is not False
        or preview.get('actor_user_id') != actor_user_id
        or preview.get('whole_scope_source_unchanged') is not True
        or not _checked_recently(preview.get('checked_at'))
        or preview.get('provider_mutation_performed') is not False
        or preview.get('release_authorized') is not False
    ):
        raise ValueError('Current exact worklist is not separately previewed and accepted.')
    cluster = db.session.get(Cluster, tenant.cluster_id)
    if cluster is None:
        raise ValueError('Approved Capsule provider cluster is missing.')
    authority = verify_capsule_provider_admin_authority(
        cluster=cluster, components=plan['handoff_components'],
    )
    if any(
        authority.get(key) != acceptance.get(key)
        for key in ('provider_username', 'provider_groups',
                    'provider_credential_id', 'scope_count', 'scoped_resources')
    ):
        raise ValueError('Capsule successor X.509 authority changed after independent acceptance.')
    return plan, related, worklist, cluster, tenant, authority


def _read_full_source(
    *, provider: Any, plan: dict[str, Any], related: dict[str, Any],
    work: dict[str, Any],
) -> dict[tuple[str, str, str], tuple[Any, Any, list[dict[str, Any]]]]:
    """Read/preserve EVERY original object and build only CAS label patches."""
    cr = next(row for row in plan['handoff_components'] if row['kind'] == 'CapsuleTenant')
    custom, core, rbac = (
        provider.custom_objects_api(), provider.core_api(), provider.rbac_authorization_api(),
    )
    live_cr = custom.get_cluster_custom_object(
        'capsule.clastix.io', 'v1beta2', 'tenants', cr['name'], _request_timeout=5,
    )
    verify_capsule_cr_preserved(cr, live_cr)
    global_quota = observe_capsule_global_quotas(custom=custom, tenant_name=cr['name'])
    if (
        global_quota.get('scope_sha256') != related['global_quota']['scope_sha256']
        or global_quota.get('blockers')
    ):
        raise ValueError('Capsule GlobalResourceQuota changed before metadata-only handoff.')
    component = {
        row['name']: row for row in plan['handoff_components']
        if row['kind'] == 'Namespace'
    }
    observations = {
        (row['namespace'], row['kind'], row['name']): row
        for row in related['resources']
    }
    expected_global = {row['name']: row for row in global_quota['resources']}
    targets: dict[tuple[str, str, str], tuple[Any, Any, list[dict[str, Any]]]] = {}
    for item in work['items']:
        kind, name, ns = item['kind'], item['name'], item['namespace']
        key = (ns, kind, name)
        if kind == 'CapsuleTenant':
            targets[key] = (live_cr, item, [])
        elif kind == 'GlobalResourceQuota':
            quota = expected_global.get(name)
            if (
                not quota or quota['uid'] != item['uid']
                or quota['resource_version'] != item['resource_version']
                or quota['policy_sha256'] != item['policy_sha256']
            ):
                raise ValueError('Capsule GlobalResourceQuota source scope is stale.')
            targets[key] = (quota, item, [])
        else:
            read, _ = _provider_methods(core=core, rbac=rbac, kind=kind)
            before = _provider_read(
                read, kind=kind, name=name,
                namespace=name if kind == 'Namespace' else ns,
            )
            patch: list[dict[str, Any]] = []
            if kind == 'Namespace':
                if _identity(before) != (name, item['uid'], item['resource_version']):
                    raise ValueError('Capsule Namespace source UID/RV changed.')
                if item['decision'] in _CANDIDATE:
                    patch = build_capsule_namespace_handoff_patch(
                        component[name], before, tenant_id=plan['tenant_id'],
                        capsule_tenant_name=cr['name'],
                        verified_successor_owner=plan['successor_owner'],
                    )
                elif (
                    item['decision'] != 'preserve_existing_provider_namespace'
                    or _labels(before).get('app.kubernetes.io/managed-by') == 'kaori'
                    or any(x.startswith('kaori.io/') for x in _labels(before))
                ):
                    raise ValueError('Capsule foreign Namespace has unsafe ownership.')
            else:
                original = observations[key]
                live, problems = classify_capsule_related_resource(
                    resource=before, kind=kind, namespace=ns,
                    tenant_id=plan['tenant_id'],
                    capsule_name=cr['name'], capsule_uid=cr['uid'],
                )
                if live != original:
                    raise ValueError('Capsule related policy, metadata or UID/RV drifted.')
                if item['decision'] in _CANDIDATE:
                    known = (
                        f'Capsule {kind}/{ns}/{name} retains KAORI provider '
                        'controls requiring separately admitted handoff.'
                    )
                    if problems != [known] or kind == 'RoleBinding':
                        raise ValueError('Capsule related control origin is not independently safe.')
                    labels = _strings(_get(_get(before, 'metadata'), 'labels'), label='labels')
                    consented = sorted(
                        x for x in labels
                        if x == 'app.kubernetes.io/managed-by' or x.startswith('kaori.io/')
                    )
                    patch = build_capsule_related_metadata_handoff_patch(
                        record=original, before=before, kind=kind, namespace=ns,
                        tenant_id=plan['tenant_id'],
                        capsule_name=cr['name'], capsule_uid=cr['uid'],
                        successor_owner=plan['successor_owner'],
                        approved_label_keys=consented,
                    )
                elif item['decision'] != 'preserve_foreign_provider_control' or problems:
                    raise ValueError('Capsule related provider control remains ambiguous.')
            targets[key] = (before, item, patch)
    if len(targets) != work['item_count']:
        raise ValueError('Capsule original provider scope is incomplete.')
    return targets


def _write_ledger_event(
    *, plan: dict[str, Any], related: dict[str, Any],
    event: dict[str, Any], previous: dict[str, Any] | None = None,
) -> None:
    """Separate PostgreSQL transaction; START commits before first PATCH."""
    with Session(db.engine) as session, session.begin():
        if session.get_bind().dialect.name != 'postgresql':
            raise ValueError('Capsule provider transfer requires installed PostgreSQL ledger.')
        tenant = session.execute(
            select(Tenant).where(Tenant.id == plan['tenant_id']).with_for_update()
        ).scalar_one_or_none()
        if (
            tenant is None or tenant.lifecycle_status != TenantLifecycleStatus.READY.value
            or tenant.generation != plan['generation']
            or tenant.cluster_id != plan['cluster_id']
        ):
            raise ValueError('Capsule canonical Tenant changed while recording immutable attempt.')
        _require_postgres_ledger_write_once_guards(session)
        prior = session.execute(
            select(CapsuleHandoffLedgerEvent)
            .where(CapsuleHandoffLedgerEvent.tenant_id == plan['tenant_id'])
            .order_by(CapsuleHandoffLedgerEvent.sequence.asc())
        ).scalars().all()
        if previous is None:
            if prior:
                raise ValueError('Capsule transfer already attempted: no automatic retry.')
            legacy = session.execute(
                select(AuditEvent.id).where(
                    AuditEvent.target_type == _LEGACY_TARGET,
                    AuditEvent.target_id == plan['tenant_id'],
                ).limit(1)
            ).first()
            if legacy:
                raise ValueError('Capsule legacy handoff evidence exists; manual recovery required.')
        elif (
            len(prior) != 1 or prior[0].event_json != previous
            or prior[0].event_sha256 != previous['event_sha256']
            or event.get('previous_event_sha256') != previous['event_sha256']
        ):
            raise ValueError('Capsule immutable START event is missing or changed.')
        project_capsule_attempt_history(
            plan=plan, related=related,
            accepted_actor_user_id=event['actor_user_id'],
            events=([previous] if previous else []) + [event],
        )
        session.add(CapsuleHandoffLedgerEvent(
            **{field: event[field] for field in (
                'tenant_id', 'cluster_id', 'generation', 'plan_sha256',
                'handoff_fingerprint', 'worklist_sha256', 'attempt_id',
                'sequence', 'event_type', 'actor_user_id',
                'previous_event_sha256', 'event_sha256',
            )},
            event_at=datetime.fromisoformat(event['event_at']),
            event_json=event,
        ))
    # Context manager acknowledged a SQL COMMIT; a lost acknowledgment
    # raises and must NOT be automatically retried.


def _terminal(
    *, start: dict[str, Any], plan: dict[str, Any], related: dict[str, Any],
    complete: bool, items: list[dict[str, Any]], errors: list[str],
    authority: dict[str, Any],
) -> dict[str, Any]:
    count = start['expected_count']
    transferred = sum(row.get('state') == 'provider_markers_transferred' for row in items)
    pending = sum(row.get('state') == 'pending_provider_transfer' for row in items)
    if complete and (transferred != count or pending or errors):
        raise ValueError('Capsule terminal cannot claim complete handoff with pending objects.')
    readback_sha = _digest(items) if complete else None
    event = {
        **start, 'event_type': 'readback_candidate' if complete else 'partial',
        'sequence': 2, 'event_at': datetime.now(UTC).isoformat(),
        'previous_event_sha256': start['event_sha256'],
        'event_sha256': None,
        'outcome': 'readback_observed' if complete else 'unknown',
        'readback_sha256': readback_sha,
        # Unknown objects are not misrepresented as observed provider state.
        'observed_count': count if complete else transferred + pending,
        'pending_count': 0 if complete else pending,
        'transferred_count': transferred,
        'ambiguous_count': 0,
    }
    event['event_sha256'] = _event_checksum(event)
    _write_ledger_event(
        plan=plan, related=related, event=event, previous=start,
    )
    receipt = {
        'status': 'provider_handoff_verified' if complete else 'partial_handoff_recovery_required',
        'tenant_id': plan['tenant_id'], 'cluster_id': plan['cluster_id'],
        'generation': plan['generation'],
        'plan_sha256': plan['plan_sha256'],
        'handoff_fingerprint': plan['handoff_fingerprint'],
        'source_worklist_sha256': start['worklist_sha256'],
        'attempt_id': start['attempt_id'],
        'start_event_sha256': start['event_sha256'],
        'readback_sha256': readback_sha,
        'actor_user_id': start['actor_user_id'],
        'provider_username': authority['provider_username'],
        'provider_credential_id': authority['provider_credential_id'],
        'resource_specific_consent_verified': True,
        # Do not fabricate controller provenance: all RoleBindings in this
        # admitted worklist are provider/foreign and remain untouched.
        'controller_generated_rbac_preserved': complete,
        'controller_origin_verified': False,
        'provider_authority_verified': True,
        'whole_scope_readback_verified': complete,
        'verified_components': items,
        'verified_resource_count': len(items),
        'errors': errors,
        'provider_handoff_verified': complete,
        'provider_mutation_performed': bool(transferred) if complete else None,
        'auto_retry_authorized': False,
        'release_authorized': False,
        'secret_material_persisted': False,
        'checked_at': datetime.now(UTC).isoformat(),
    }
    with Session(db.engine) as session, session.begin():
        session.add(AuditEvent(
            actor_user_id=start['actor_user_id'],
            target_type=_TARGET, target_id=plan['tenant_id'],
            action=('tenant.release.capsule_provider_handoff_observed'
                    if complete else 'tenant.release.capsule_provider_recovery_required'),
            summary='Capsule exact-scope handoff observed; final Release is a separate gate.',
            metadata_json=receipt,
        ))
    return receipt


def execute_capsule_handoff_committed(
    *, tenant_id: str, actor_user_id: int, plan_sha256: str,
    worklist_sha256: str, confirmed: bool,
) -> dict[str, Any]:
    """One guarded conditional provider transfer; any uncertainty is terminal."""
    if not confirmed:
        raise ValueError('Explicit exact-resource Capsule transfer authorization required.')
    plan, related, work, cluster, tenant, authority = _exact_current_scope(
        tenant_id=tenant_id, actor_user_id=actor_user_id,
        plan_sha256=plan_sha256, expected_worklist_sha256=worklist_sha256,
    )
    provider = runtime_adapter.build_client(cluster)
    cr = next(item for item in plan['handoff_components'] if item['kind'] == 'CapsuleTenant')
    candidates = [
        {**item, 'decision': 'explicit_kaori_metadata_handoff_review'}
        for item in work['items']
        if item['kind'] in ('ResourceQuota', 'LimitRange')
        and item['decision'] in _CANDIDATE
    ]
    verify_capsule_related_admin_authority(provider=provider, candidates=candidates)
    source = _read_full_source(provider=provider, plan=plan, related=related, work=work)
    patches = [key for key, obj in source.items() if obj[2]]
    if not patches:
        raise ValueError('Capsule handoff has no KAORI metadata transfer candidates.')
    patches.sort(key=lambda key: (
        key[0] if key[0] else key[2],
        {'ResourceQuota': 0, 'LimitRange': 1, 'RoleBinding': 2, 'Namespace': 3}.get(key[1], 99),
        key[2],
    ))
    start = build_capsule_start_candidate(
        tenant_id=tenant_id, actor_user_id=actor_user_id, plan=plan,
        related=related, attempt_id=str(uuid4()), event_at=datetime.now(UTC),
    )
    if start['expected_count'] != len(patches):
        raise ValueError('Capsule START transfer count differs from complete source scope.')
    _write_ledger_event(plan=plan, related=related, event=start)
    core, rbac, custom = (
        provider.core_api(), provider.rbac_authorization_api(),
        provider.custom_objects_api(),
    )
    errors: list[str] = []
    # A crash after START has no terminal row and can *never* replay this path.
    # A provider PATCH timeout has unknown effect and stops all future writes.
    for key in patches:
        before, item, ops = source[key]
        kind, ns, name = key[1], key[0], key[2]
        try:
            read, patch = _provider_methods(core=core, rbac=rbac, kind=kind)
            dry = _provider_patch(
                patch, kind=kind, name=name, namespace=ns,
                body=ops, dry_run=True,
            )
            if kind == 'Namespace':
                verify_capsule_namespace_preview(
                    before=before, preview=dry, successor_owner=plan['successor_owner'],
                )
            else:
                record = next(x for x in related['resources']
                              if (x['namespace'], x['kind'], x['name']) == key)
                # Reconstruct the original approved label-key set, never take
                # mutation keys from a dry-run response.
                labels = _strings(_get(_get(before, 'metadata'), 'labels'), label='labels')
                approved = sorted(
                    k for k in labels if k == 'app.kubernetes.io/managed-by'
                    or k.startswith('kaori.io/')
                )
                verify_capsule_related_metadata_preview(
                    record=record, before=before, preview=dry,
                    kind=kind, namespace=ns, tenant_id=tenant_id,
                    capsule_name=cr['name'], capsule_uid=cr['uid'],
                    successor_owner=plan['successor_owner'],
                    approved_label_keys=approved,
                )
            fresh = _provider_read(
                read, kind=kind, name=name,
                namespace=name if kind == 'Namespace' else ns,
            )
            _require_source_still_unchanged(
                kind=kind, before=before, current=fresh,
                record=item if kind == 'Namespace' else record,
                tenant_id=tenant_id, capsule_name=cr['name'], capsule_uid=cr['uid'],
            )
            _provider_patch(
                patch, kind=kind, name=name, namespace=ns,
                body=ops, dry_run=False,
            )
            # No automatic retries. A lost response becomes an unknown state.
        except Exception as exc:
            errors.append(f'{kind}/{ns}/{name}: {type(exc).__name__}')
            break
    verified: list[dict[str, Any]] = []
    if not errors:
        try:
            after_cr = custom.get_cluster_custom_object(
                'capsule.clastix.io', 'v1beta2', 'tenants', cr['name'],
                _request_timeout=5,
            )
            verify_capsule_cr_preserved(cr, after_cr)
            global_after = observe_capsule_global_quotas(
                custom=custom, tenant_name=cr['name'],
            )
            if (
                global_after.get('scope_sha256') != related['global_quota']['scope_sha256']
                or global_after.get('blockers')
            ):
                raise ValueError('Capsule shared quota changed after metadata handoff.')
            observed_global = {row['name']: row for row in global_after['resources']}
            for key, (before, item, ops) in sorted(source.items()):
                kind, ns, name = key[1], key[0], key[2]
                row = {
                    'kind': kind, 'namespace': ns, 'name': name,
                    'uid': item['uid'],
                }
                if kind == 'GlobalResourceQuota':
                    current = observed_global.get(name)
                    if current != before:
                        raise ValueError('Capsule GlobalResourceQuota changed after transfer.')
                    verified.append({**row, 'resource_version': item['resource_version'],
                                     'state': 'preserved'})
                    continue
                if kind == 'CapsuleTenant':
                    verified.append({**row, 'resource_version': item['resource_version'],
                                     'state': 'preserved'})
                    continue
                read, _ = _provider_methods(core=core, rbac=rbac, kind=kind)
                live = _provider_read(
                    read, kind=kind, name=name,
                    namespace=name if kind == 'Namespace' else ns,
                )
                if _identity(live)[:2] != (name, item['uid']):
                    raise ValueError('Capsule post-handoff UID changed.')
                if kind == 'Namespace':
                    if ops:
                        baseline = capture_capsule_namespace_baseline(
                            next(c for c in plan['handoff_components']
                                 if c['kind'] == 'Namespace' and c['name'] == name),
                            before, tenant_id=tenant_id, capsule_tenant_name=cr['name'],
                        )
                        state = classify_capsule_namespace_handoff(
                            baseline=baseline, current=live,
                            tenant_id=tenant_id, successor_owner=plan['successor_owner'],
                        )['state']
                        row['preservation_sha256'] = _digest(capsule_preservation_digest(before))
                    else:
                        if (
                            _identity(live) != _identity(before)
                            or _labels(live) != _labels(before)
                            or capsule_preservation_digest(live)
                            != capsule_preservation_digest(before)
                        ):
                            raise ValueError(
                                'Foreign Capsule Namespace identity, spec or retained '
                                'provider metadata changed during handoff.'
                            )
                        state = 'preserved'
                elif ops:
                    record = next(x for x in related['resources']
                                  if (x['namespace'], x['kind'], x['name']) == key)
                    labels = _strings(_get(_get(before, 'metadata'), 'labels'), label='labels')
                    approved = sorted(
                        k for k in labels if k == 'app.kubernetes.io/managed-by'
                        or k.startswith('kaori.io/')
                    )
                    state = classify_capsule_related_metadata_readback(
                        record=record, before=before, current=live,
                        kind=kind, namespace=ns, tenant_id=tenant_id,
                        capsule_name=cr['name'], capsule_uid=cr['uid'],
                        successor_owner=plan['successor_owner'],
                        approved_label_keys=approved,
                    )['state']
                    row['preservation_sha256'] = _digest(_related_provider_invariants(before))
                else:
                    current, findings = classify_capsule_related_resource(
                        resource=live, kind=kind, namespace=ns,
                        tenant_id=tenant_id, capsule_name=cr['name'],
                        capsule_uid=cr['uid'],
                    )
                    original = next(x for x in related['resources']
                                    if (x['namespace'], x['kind'], x['name']) == key)
                    if current != original or findings:
                        raise ValueError('Foreign Capsule quota/limit/RBAC changed during handoff.')
                    state = 'preserved'
                if ops and state != 'provider_markers_transferred':
                    raise ValueError('Capsule transfer outcome remains pending or unknown.')
                verified.append({
                    **row, 'resource_version': _identity(live)[2], 'state': state,
                })
            if len(verified) != work['item_count']:
                raise ValueError('Capsule final provider read-back omitted a source object.')
        except Exception as exc:
            errors.append(f'complete_scope_readback: {type(exc).__name__}')
    complete = not errors and len(verified) == work['item_count']
    # Even a complete post-write scope is still one *candidate* for
    # independent G4 provider/readback re-verification.
    return _terminal(
        start=start, plan=plan, related=related, complete=complete,
        items=verified, errors=errors, authority=authority,
    )
