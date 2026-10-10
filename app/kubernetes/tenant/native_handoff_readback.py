"""Provider-authoritative Native handoff read-back, not successor attestation.

No Kubernetes write, grant revocation, or KAORI Released lifecycle mutation.
External administrator changes are observed but never claimed as verified
external consent without an independent trusted authority.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.extensions.db import db
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.adapter import runtime_adapter
from app.kubernetes.tenant.native_handoff_dry_run import (
    _MARKER_KEYS,
    _read_resource,
    _resource_metadata,
    _retained_provider_metadata,
    _spec,
    _stable_sha256,
)
from app.kubernetes.tenant.native_handoff_recovery import summarize_native_handoff_recovery
from app.kubernetes.tenant.release_handoff_approval import (
    _checked_recently,
    _plan_hash,
    latest_release_handoff_approval,
    latest_release_handoff_plan,
)
from app.kubernetes.tenant.release_preflight import _release_dependency_counts
from app.kubernetes.tenant.release_successor_claim import latest_release_successor_claim
from app.models import Cluster
from app.models.audit import AuditEvent
from app.models.tenant import Tenant, TenantLifecycleStatus

_TARGET = 'kubernetes_tenant_release_native_handoff_readback'
_DRY_RUN_TARGET = 'kubernetes_tenant_release_native_handoff_dry_run'


def latest_native_handoff_readback(tenant_id: str) -> dict[str, Any] | None:
    row = (
        AuditEvent.query.filter_by(target_type=_TARGET, target_id=tenant_id)
        .order_by(AuditEvent.id.desc()).first()
    )
    return dict(row.metadata_json or {}) if row else None


def _latest_native_dry_run(tenant_id: str) -> dict[str, Any] | None:
    row = (
        AuditEvent.query.filter_by(target_type=_DRY_RUN_TARGET, target_id=tenant_id)
        .order_by(AuditEvent.id.desc()).first()
    )
    return dict(row.metadata_json or {}) if row else None


def verify_external_native_component(
    *, before: dict[str, Any], current: Any, successor_owner: str,
) -> dict[str, Any]:
    """Check exact preserved spec/foreign metadata against approved preview."""
    name, uid, rv, labels = _resource_metadata(current)
    if (
        (name, uid) != (before.get('name'), before.get('uid'))
        or not rv or rv == before.get('resource_version')
    ):
        raise ValueError('Provider identity/resourceVersion did not show an accepted handoff.')
    if (
        not successor_owner or successor_owner == 'kaori'
        or labels.get('app.kubernetes.io/managed-by') != successor_owner
        or any(key in labels for key in _MARKER_KEYS if key != 'app.kubernetes.io/managed-by')
    ):
        raise ValueError('Successor provider ownership markers were not established.')
    if (
        before.get('spec_sha256') != _stable_sha256(_spec(current))
        or before.get('retained_metadata_sha256')
        != _stable_sha256(_retained_provider_metadata(current))
    ):
        raise ValueError('Provider spec or unrelated metadata changed during handoff.')
    if before.get('operation') != 'metadata_only_json_patch_dry_run':
        raise ValueError('No canonical Native dry-run component proof exists.')
    return {
        'kind': before['kind'], 'name': name, 'uid': uid,
        'resource_version': rv, 'successor_owner': successor_owner,
        'spec_preserved': True, 'foreign_metadata_preserved': True,
        'provider_mutation_performed_by_kaori': False,
    }


def observe_external_native_handoff_committed(
    *, tenant_id: str, actor_user_id: int, plan_sha256: str,
) -> dict[str, Any]:
    """Observe post-change Kubernetes objects; DO NOT authorize governance release."""
    plan = latest_release_handoff_plan(tenant_id)
    approval = latest_release_handoff_approval(tenant_id)
    claim = latest_release_successor_claim(tenant_id)
    dry_run = _latest_native_dry_run(tenant_id)
    if (
        not plan or not approval or not claim or not dry_run
        or len(plan_sha256) != 64
        or plan.get('tenant_id') != tenant_id
        or plan.get('plan_sha256') != plan_sha256
        or _plan_hash(plan) != plan_sha256
        or approval.get('plan_sha256') != plan_sha256
        or not _checked_recently(plan.get('requested_at'))
        or not _checked_recently(approval.get('approved_at'))
        or approval.get('status') != 'acknowledged_pending_provider_handoff'
        or approval.get('requested_by') != plan.get('requested_by')
        or approval.get('approved_by') == plan.get('requested_by')
        or not isinstance(approval.get('approved_by'), int)
        or approval.get('handoff_fingerprint') != plan.get('handoff_fingerprint')
        or claim.get('plan_sha256') != plan_sha256
        or not _checked_recently(claim.get('recorded_at'))
        or claim.get('status') != 'external_reference_unverified'
        or claim.get('successor_owner') != plan.get('successor_owner')
        or dry_run.get('plan_sha256') != plan_sha256
        or not _checked_recently(dry_run.get('checked_at'))
        or dry_run.get('status') != 'dry_run_passed'
        or dry_run.get('handoff_fingerprint') != plan.get('handoff_fingerprint')
        or dry_run.get('provider_mutation_performed') is not False
        or dry_run.get('release_authorized') is not False
    ):
        raise ValueError('A complete independent plan, successor reference and passed dry-run are required.')
    tenant = db.session.get(Tenant, tenant_id)
    if (
        tenant is None or tenant.provider_key != 'native_kubernetes'
        or tenant.reconciliation_authority != 'native_kubernetes'
        or tenant.provider_state != 'native' or tenant.ownership_status != 'adopted'
        or tenant.lifecycle_status != TenantLifecycleStatus.READY.value
        or tenant.cluster_id != plan.get('cluster_id')
        or tenant.generation != plan.get('generation')
    ):
        raise ValueError('Tenant authority changed after the approved Native handoff.')
    counts = _release_dependency_counts(tenant_id)
    if any(type(v) is not int or v != 0 for v in counts.values()):
        raise ValueError('Active Tenant governance dependencies block provider handoff acceptance.')
    expected = dry_run.get('previewed_components')
    if (
        not isinstance(expected, list) or not expected
        or len(expected) != dry_run.get('expected_component_count')
        or len(expected) > 100
    ):
        raise ValueError('Native dry-run component receipt is incomplete.')
    approved = plan.get('handoff_components')
    if not isinstance(approved, list):
        raise ValueError('Original handoff provider inventory is unavailable.')
    selection = {
        (item.get('namespace'), item.get('kind'), item.get('name'), item.get('uid'))
        for item in approved if isinstance(item, dict)
        and item.get('handoff') == 'external_acceptance_required'
    }
    selected = [
        (item.get('namespace'), item.get('kind'), item.get('name'), item.get('uid'))
        for item in expected if isinstance(item, dict)
    ]
    if len(selection) != len(selected) or set(selected) != selection:
        raise ValueError('Read-back target scope changed from the approved provider inventory.')
    cluster = db.session.get(Cluster, tenant.cluster_id)
    if cluster is None:
        raise ValueError('Native Kubernetes cluster is unavailable for provider read-back.')
    core = runtime_adapter.build_client(cluster).core_api()
    live_components: dict[tuple[str, str, str, str], Any] = {}
    for component in expected:
        key = (
            str(component.get('namespace') or ''), str(component['kind']),
            str(component['name']), str(component['uid']),
        )
        live_components[key] = _read_resource(core, component)
    recovery = summarize_native_handoff_recovery(
        previewed_components=expected, live_components=live_components,
        tenant_id=tenant_id, successor_owner=str(plan['successor_owner']),
    )
    # Keep the existing full-transfer proof and status unchanged. Partial or
    # unchanged marker states can be observed but never complete provider handoff.
    complete = recovery['status'] == 'provider_markers_transferred_consent_unverified'
    results: list[dict[str, Any]] = []
    if complete:
        for component in expected:
            key = (
                str(component.get('namespace') or ''), str(component['kind']),
                str(component['name']), str(component['uid']),
            )
            results.append(verify_external_native_component(
                before=component, current=live_components[key],
                successor_owner=str(plan['successor_owner']),
            ))

    receipt = {
        'tenant_id': tenant_id, 'cluster_id': tenant.cluster_id,
        'generation': tenant.generation,
        'plan_sha256': plan_sha256,
        'handoff_fingerprint': plan['handoff_fingerprint'],
        'status': (
            'provider_handoff_observed_acceptance_unverified'
            if complete else recovery['status']
        ),
        'observed_components': results if complete else recovery['components'],
        'observed_count': len(results) if complete else recovery['transferred_count'],
        'recovery': recovery,
        'observed_at': datetime.now(UTC).isoformat(),
        'external_successor_verified': False,
        'provider_handoff_observed': complete,
        'provider_mutation_performed': False,
        'provider_handoff_verified': False,
        'release_authorized': False,
        'secret_material_persisted': False,
    }
    db.session.add(AuditEvent(
        actor_user_id=actor_user_id, target_type=_TARGET, target_id=tenant_id,
        action=(
            'tenant.release.native_provider_handoff_observed'
            if complete else 'tenant.release.native_provider_handoff_recovery_observed'
        ),
        summary=(
            'Observed external provider marker transfer; acceptance unverified, Release blocked.'
            if complete else 'Observed incomplete Native handoff; recovery required, Release blocked.'
        ),
        metadata_json=receipt,
    ))
    db.session.commit()
    return receipt
