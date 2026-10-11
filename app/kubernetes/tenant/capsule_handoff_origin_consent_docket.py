"""Source-only correlation of Capsule collector MAC and independent resource consent.

The output is a reviewer docket, NEVER authority to execute dry-run/PATCH,
retry, SQL START, provider handoff, or Released. All external trust roots,
apiserver audit integrity, collector replay protection, authenticated
controller lineage, and committed consent remain separately blocking.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.kubernetes.tenant.capsule_handoff_collector_receipt import (
    inspect_capsule_collector_receipt,
)
from app.kubernetes.tenant.capsule_handoff_consent_identity import (
    inspect_capsule_consent_session_attestations,
)
from app.kubernetes.tenant.capsule_handoff_controller_audit_claims import (
    correlate_capsule_controller_audit_claims,
)
from app.kubernetes.tenant.capsule_handoff_resource_admission import (
    assess_capsule_resource_handoff_scope,
)
from app.kubernetes.tenant.capsule_handoff_resource_consent import (
    inspect_capsule_resource_consent,
)
from app.kubernetes.tenant.capsule_handoff_related_inventory import _digest


def review_capsule_origin_consent_docket(
    *, plan: Mapping[str, Any], related: Mapping[str, Any],
    approval: Mapping[str, Any], acceptance: Mapping[str, Any],
    claims: list[Mapping[str, Any]], collector_receipt: Mapping[str, Any],
    consent_manifest: Mapping[str, Any],
    trusted_collector_id: str, trusted_key_id: str,
    trusted_hmac_key: bytes | None,
    identity_attestations: list[Mapping[str, Any]] | None = None,
    expected_identity_issuer_id: str | None = None,
    expected_identity_key_id: str | None = None,
) -> dict[str, Any]:
    """Require full candidate audit/consent coverage with no authority flags."""
    base = assess_capsule_resource_handoff_scope(plan=plan, related=related)
    audit = correlate_capsule_controller_audit_claims(
        tenant_id=base['tenant_id'], cluster_id=base['cluster_id'],
        resources=base['resources'], claims=claims,
    )
    if (
        base['source_candidate_count'] < 1
        or audit['claim_count'] != base['source_candidate_count']
    ):
        raise ValueError('Capsule controller audit claim coverage misses KAORI handoff candidates.')
    collector = inspect_capsule_collector_receipt(
        resource_report=base, claims=claims, receipt=collector_receipt,
        trusted_collector_id=trusted_collector_id,
        trusted_key_id=trusted_key_id, trusted_hmac_key=trusted_hmac_key,
    )
    consent = inspect_capsule_resource_consent(
        plan=plan, resource_report=base, approval=approval,
        acceptance=acceptance, manifest=consent_manifest,
    )
    if (
        consent['resource_count'] != audit['claim_count']
        or consent['worklist_sha256'] != collector['worklist_sha256']
        or consent['resource_review_sha256'] != collector['resource_review_sha256']
    ):
        raise ValueError('Capsule consent, controller claim and collector scope differ.')
    identity = None
    if identity_attestations is not None:
        identity = inspect_capsule_consent_session_attestations(
            plan=plan, resource_report=base, approval=approval,
            acceptance=acceptance, manifest=consent_manifest,
            attestations=identity_attestations,
            expected_issuer_id=expected_identity_issuer_id,
            expected_key_id=expected_identity_key_id,
        )
        if identity['consent_manifest_sha256'] != consent['resource_consent_manifest_sha256']:
            raise ValueError('Capsule human attestation changed the consent manifest scope.')
    elif expected_identity_issuer_id is not None or expected_identity_key_id is not None:
        raise ValueError('Capsule identity issuer cannot be supplied without human attestations.')
    return {
        'status': 'collector_receipt_and_resource_consent_correlated_unadmitted',
        'tenant_id': base['tenant_id'],
        'cluster_id': base['cluster_id'],
        'plan_sha256': base['plan_sha256'],
        'worklist_sha256': base['worklist_sha256'],
        'resource_review_sha256': base['resource_review_sha256'],
        'candidate_count': base['source_candidate_count'],
        'audit_claim_count': audit['claim_count'],
        'consent_target_count': consent['resource_count'],
        'identity_attestation_count': 0 if identity is None else identity['attestation_count'],
        'identity_attestations_sha256': (
            None if identity is None else identity['session_attestation_digest_sha256']
        ),
        'human_identity_claims_bound_not_authenticated': identity is not None,
        'collector_receipt_sha256': collector['collector_receipt_sha256'],
        'resource_consent_manifest_sha256': consent['resource_consent_manifest_sha256'],
        'review_docket_sha256': _digest({
            'resource_review_sha256': base['resource_review_sha256'],
            'collector_receipt_sha256': collector['collector_receipt_sha256'],
            'consent_sha256': consent['resource_consent_manifest_sha256'],
            'identity_attestations_sha256': (
                None if identity is None else identity['session_attestation_digest_sha256']
            ),
        }),
        'collector_mac_verified': collector['collector_mac_verified'],
        'collector_key_source_independently_attested': False,
        'apiserver_audit_integrity_verified': False,
        'audit_batch_replay_prevention_verified': False,
        'controller_origin_attested': False,
        'independent_consent_record_committed': False,
        'idp_session_origin_authenticated': False,
        'mfa_challenge_verified': False,
        'human_consent_authenticated': False,
        'current_provider_uid_rv_readback_verified': False,
        'resource_specific_handoff_admitted': False,
        'dry_run_admitted': False, 'provider_execution_admitted': False,
        'provider_mutation_performed': False, 'provider_handoff_verified': False,
        'auto_retry_authorized': False, 'resume_authorized': False,
        'release_authorized': False, 'secret_material_persisted': False,
    }
