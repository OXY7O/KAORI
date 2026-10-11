"""Capsule-specific server-side dry-run preview, without live PATCH or Release (#1229).

No route or scheduled job exposes this draft review helper. A successful preview
DOES NOT prove quota, limitRange, RoleBinding coverage or authorize execution.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.kubernetes.tenant.allocation_observation import _CAPSULE_TENANT_LABEL_KEYS
from app.kubernetes.tenant.capsule_handoff_contract import (
    _identity, _labels, _successor, build_capsule_namespace_handoff_patch,
    capsule_preservation_digest, validate_capsule_handoff_scope,
    verify_capsule_cr_preserved, verify_capsule_namespace_preview,
)
from app.kubernetes.tenant.capsule_handoff_recovery import capture_capsule_namespace_baseline
from app.kubernetes.tenant.capsule_handoff_contract import (
    build_capsule_related_metadata_handoff_patch,
)
from app.kubernetes.tenant.capsule_handoff_related_inventory import (
    _digest, classify_capsule_related_resource,
)
from app.kubernetes.tenant.capsule_handoff_resource_admission import (
    assess_capsule_resource_handoff_scope,
)
from app.kubernetes.tenant.capsule_handoff_resource_consent import (
    inspect_capsule_resource_consent,
)
from app.kubernetes.tenant.capsule_handoff_worklist import build_capsule_handoff_worklist

_CONTENT_TYPE = 'application/json-patch+json'


def preview_capsule_namespace_handoff(
    core: Any, component: Mapping[str, Any], *, tenant_id: str,
    capsule_tenant_name: str, successor_owner: str,
) -> dict[str, Any]:
    """Bound UID/RV conditional dryRun=All; independently reread unchanged live state."""
    _successor(successor_owner)
    if component.get('kind') != 'Namespace' or component.get('namespace') != component.get('name'):
        raise ValueError('Capsule dry-run requires an approved Namespace component.')
    before = core.read_namespace(component['name'], _request_timeout=5)
    if _identity(before) != (
        component.get('name'), component.get('uid'), component.get('resource_version')
    ):
        raise ValueError('Capsule Namespace drifted from approved preflight.')
    before_digest = capsule_preservation_digest(before)
    before_labels = _labels(before)
    claims = {before_labels[k] for k in _CAPSULE_TENANT_LABEL_KEYS if k in before_labels}
    if claims != {capsule_tenant_name}:
        raise ValueError('Capsule Namespace provider label correlation is incomplete.')

    if component.get('handoff') == 'external_acceptance_required':
        patch = build_capsule_namespace_handoff_patch(
            component, before, tenant_id=tenant_id,
            capsule_tenant_name=capsule_tenant_name,
            verified_successor_owner=successor_owner,
        )
        preview = core.patch_namespace(
            name=component['name'], body=patch, dry_run='All',
            _content_type=_CONTENT_TYPE, _request_timeout=5,
        )
        verify_capsule_namespace_preview(
            before=before, preview=preview, successor_owner=successor_owner,
        )
        result = capture_capsule_namespace_baseline(
            component, before, tenant_id=tenant_id,
            capsule_tenant_name=capsule_tenant_name,
        )
    elif (
        component.get('handoff') == 'observe_only'
        and component.get('ownership') == 'external_or_unattributed'
        and not any(k in before_labels for k in ('kaori.io/tenant-id', 'app.kubernetes.io/managed-by'))
        and not any(k.startswith('kaori.io/') for k in before_labels)
    ):
        # No-op read-back of an externally owned Capsule Namespace. No patch.
        result = {
            'kind': 'Namespace', 'namespace': component['name'],
            'name': component['name'], 'uid': component['uid'],
            'resource_version': component['resource_version'],
            'operation': 'observe_capsule_namespace_without_transfer',
            'dry_run': False, 'live_provider_unchanged': True,
            'preserved': before_digest,
        }
    else:
        raise ValueError('Namespace handoff source ownership is ambiguous.')
    live = core.read_namespace(component['name'], _request_timeout=5)
    if (
        _identity(live) != _identity(before)
        or _labels(live) != before_labels
        or capsule_preservation_digest(live) != before_digest
    ):
        raise ValueError('Capsule live provider changed during dry-run preview.')
    return result


def preview_capsule_handoff_scope(
    *, custom: Any, core: Any, components: list[dict[str, Any]],
    tenant_id: str, successor_owner: str,
) -> dict[str, Any]:
    """Scope preview only, not a sufficient provider-authority/readiness proof.

    No Runtime adapter, persistence, approval or external patch in this module.
    Caller must separately authenticate the X.509 actor and verify exact plan,
    independent consent, SAR and live dependency evidence before invoking it.
    """
    cr, namespaces = validate_capsule_handoff_scope(components)
    _successor(successor_owner)
    if not tenant_id:
        raise ValueError('Capsule handoff must bind the canonical Tenant identity.')
    live_cr = custom.get_cluster_custom_object(
        'capsule.clastix.io', 'v1beta2', 'tenants', cr['name'],
        _request_timeout=5,
    )
    if not isinstance(live_cr, Mapping):
        raise ValueError('Unsupported Capsule v1beta2 CR provider response.')
    cr_observation = verify_capsule_cr_preserved(cr, live_cr)
    rows = [
        preview_capsule_namespace_handoff(
            core, component, tenant_id=tenant_id,
            capsule_tenant_name=cr['name'], successor_owner=successor_owner,
        )
        for component in namespaces
    ]
    cr_after = custom.get_cluster_custom_object(
        'capsule.clastix.io', 'v1beta2', 'tenants', cr['name'],
        _request_timeout=5,
    )
    verify_capsule_cr_preserved(cr, cr_after)
    if (
        _labels(live_cr) != _labels(cr_after)
        or len(rows) != len(namespaces)
        or not any(row['operation'] == 'capsule_metadata_only_json_patch_dry_run' for row in rows)
    ):
        raise ValueError('Capsule CR changed, preview is partial or no transfer is provable.')
    return {
        'status': 'preview_observed_coverage_incomplete',
        'capsule_cr': cr_observation, 'namespace_previews': rows,
        'namespace_count': len(rows),
        'quota_limit_rbac_inventory_verified': False,
        'dry_run_complete': False,
        'provider_mutation_performed': False,
        'provider_handoff_verified': False,
        'release_authorized': False,
        'secret_material_persisted': False,
    }


def build_capsule_scope_patch_review(
    *, plan: Mapping[str, Any], related: Mapping[str, Any],
    current_capsule_cr: Any, source_namespaces: Mapping[str, Any],
    source_related_objects: Mapping[tuple[str, str, str], Any],
    approval: Mapping[str, Any], acceptance: Mapping[str, Any],
    consent_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Prepare exact complete G2 patch SHA worklist entirely OFFLINE.

    This function does not call the provider, validate real authenticated
    human intent, persist START, or authorize dryRun=All/PATCH. Raw objects
    must come from a future independently trusted source; caller-supplied
    snapshots cannot be promoted to an execution capability.
    """
    resource_report = assess_capsule_resource_handoff_scope(
        plan=plan, related=related,
    )
    consent = inspect_capsule_resource_consent(
        plan=plan, resource_report=resource_report, approval=approval,
        acceptance=acceptance, manifest=consent_manifest,
    )
    worklist = build_capsule_handoff_worklist(plan=plan, related=related)
    cr, namespaces = validate_capsule_handoff_scope(plan['handoff_components'])
    verify_capsule_cr_preserved(cr, current_capsule_cr)
    if (
        not isinstance(source_namespaces, Mapping)
        or set(source_namespaces) != {ns['name'] for ns in namespaces}
        or not isinstance(source_related_objects, Mapping)
        or not isinstance(consent_manifest.get('transfer_targets'), list)
    ):
        raise ValueError('Capsule G2 source snapshots or consent scope are partial.')
    observed = {
        (row['namespace'], row['kind'], row['name']): row
        for row in related['resources']
    }
    if set(source_related_objects) != set(observed):
        raise ValueError('Capsule G2 requires every namespaced control including foreign objects.')
    by_target = {
        (target['namespace'], target['kind'], target['name']): target
        for target in consent_manifest['transfer_targets']
    }
    decisions = {
        (item['namespace'], item['kind'], item['name']): item
        for item in worklist['items']
    }
    candidates = {
        key for key, item in decisions.items()
        if item['decision'] in (
            'candidate_kaori_metadata_handoff_review',
            'explicit_kaori_metadata_handoff_review',
        )
    }
    if (
        not candidates or set(by_target) != candidates
        or len(by_target) != consent['resource_count']
        or any(item['decision'] in (
            'operator_origin_investigation', 'operator_selector_investigation',
        ) for item in decisions.values())
    ):
        raise ValueError('Capsule G2 contains ambiguous provider ownership or partial consent.')
    checked: list[dict[str, Any]] = []
    for ns in namespaces:
        before = source_namespaces[ns['name']]
        if _identity(before) != (ns['name'], ns['uid'], ns['resource_version']):
            raise ValueError('Capsule G2 Namespace UID/resourceVersion changed.')
        key = ('', 'Namespace', ns['name'])
        decision = decisions[key]['decision']
        if key in candidates:
            patch = build_capsule_namespace_handoff_patch(
                ns, before, tenant_id=plan['tenant_id'],
                capsule_tenant_name=cr['name'],
                verified_successor_owner=plan['successor_owner'],
            )
            baseline = capture_capsule_namespace_baseline(
                ns, before, tenant_id=plan['tenant_id'],
                capsule_tenant_name=cr['name'],
            )
            selected = set(baseline['label_keys_to_release'])
            if selected != set(by_target[key]['proposed_label_keys']):
                raise ValueError('Capsule G2 Namespace patch keys differ from consent.')
            checked.append({
                'namespace': '', 'kind': 'Namespace', 'name': ns['name'],
                'uid': ns['uid'], 'source_resource_version': ns['resource_version'],
                'operation': 'conditional_metadata_dry_run_candidate',
                'patch_sha256': _digest(patch),
                'preservation_sha256': _digest(baseline['preserved']),
            })
        else:
            labels = _labels(before)
            if (
                decision != 'preserve_existing_provider_namespace'
                or any(key.startswith('kaori.io/') for key in labels)
                or labels.get('app.kubernetes.io/managed-by') == 'kaori'
            ):
                raise ValueError('Capsule G2 cannot silently treat Namespace as provider owned.')
            checked.append({
                'namespace': '', 'kind': 'Namespace', 'name': ns['name'],
                'uid': ns['uid'], 'source_resource_version': ns['resource_version'],
                'operation': 'preserve_only',
                'preservation_sha256': _digest(capsule_preservation_digest(before)),
            })
    for key, source in sorted(observed.items()):
        kind, namespace, name = key[1], key[0], key[2]
        before = source_related_objects[key]
        projected, findings = classify_capsule_related_resource(
            resource=before, kind=kind, namespace=namespace,
            tenant_id=plan['tenant_id'], capsule_name=cr['name'],
            capsule_uid=cr['uid'],
        )
        if projected != source:
            raise ValueError('Capsule G2 original raw related object differs from complete LIST.')
        work_item = decisions[key]
        if key in candidates:
            target = by_target[key]
            patch = build_capsule_related_metadata_handoff_patch(
                record=source, before=before, kind=kind,
                namespace=namespace, tenant_id=plan['tenant_id'],
                capsule_name=cr['name'], capsule_uid=cr['uid'],
                successor_owner=plan['successor_owner'],
                approved_label_keys=target['proposed_label_keys'],
            )
            checked.append({
                'namespace': namespace, 'kind': kind, 'name': name,
                'uid': source['uid'],
                'source_resource_version': source['resource_version'],
                'operation': 'conditional_metadata_dry_run_candidate',
                'patch_sha256': _digest(patch),
                'policy_sha256': source['policy_sha256'],
            })
        elif work_item['decision'] == 'preserve_foreign_provider_control' and not findings:
            checked.append({
                'namespace': namespace, 'kind': kind, 'name': name,
                'uid': source['uid'],
                'source_resource_version': source['resource_version'],
                'operation': 'preserve_only',
                'policy_sha256': source['policy_sha256'],
                'metadata_sha256': source['metadata_sha256'],
            })
        else:
            raise ValueError('Capsule G2 noncandidate related control is ambiguous.')
    checked.sort(key=lambda item: (item['namespace'], item['kind'], item['name']))
    transfer = sum(row['operation'] == 'conditional_metadata_dry_run_candidate' for row in checked)
    if transfer != len(candidates):
        raise ValueError('Capsule G2 omitted an approved per-resource transfer.')
    return {
        'status': 'complete_offline_scope_patch_review_unadmitted',
        'tenant_id': plan['tenant_id'],
        'plan_sha256': plan['plan_sha256'],
        'handoff_fingerprint': plan['handoff_fingerprint'],
        'worklist_sha256': worklist['inventory_sha256'],
        'resource_review_sha256': resource_report['resource_review_sha256'],
        'consent_manifest_sha256': consent['resource_consent_manifest_sha256'],
        'capsule_cr_preserved_in_source': True,
        'complete_scope_count': worklist['item_count'],
        'transfer_candidate_count': transfer,
        'preserved_namespaced_count': len(checked) - transfer,
        'globally_preserved_count': (
            worklist['item_count'] - len(checked)
        ),
        'scope_items_sha256': _digest(checked),
        'scope_items': checked,
        'source_provider_authenticated': False,
        'human_consent_authenticated': False,
        'start_committed': False, 'server_dry_run_completed': False,
        'provider_execution_admitted': False,
        'provider_mutation_performed': False,
        'auto_retry_authorized': False,
        'release_authorized': False,
        'secret_material_persisted': False,
    }
