"""Non-mutating Capsule collector/consent proof ledger inspection (#1229).

Reads complete Tenant-scoped committed rows and cross-checks a correlated
docket. This cannot establish schema installed, actual DB write-once
permissions, anti-replay retention, a Vault/KMS trust root or authentic
human/controller authority. There is no INSERT/COMMIT or provider call.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from app.kubernetes.tenant.capsule_handoff_related_inventory import _digest
from app.models.capsule_handoff_proof import (
    CapsuleHandoffAuditBatch,
    CapsuleHandoffResourceConsentRecord,
)


def _field(row: Any, key: str) -> Any:
    return row.get(key) if isinstance(row, Mapping) else getattr(row, key, None)


def _datetime(value: Any) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError('Capsule proof ledger timestamp is missing.')
    # Historical SQLite datetime loses tzinfo; always interpret DB values
    # as UTC for comparison, never treat that convention as evidence.
    return (value if value.tzinfo is not None else value.replace(tzinfo=UTC)).astimezone(UTC)


def inspect_capsule_proof_storage(
    *, resource_report: Mapping[str, Any],
    collector_receipt_review: Mapping[str, Any],
    consent_review: Mapping[str, Any],
    requester_user_id: int, reviewer_user_id: int,
    successor_user_id: int,
    batch_rows: list[Any], consent_rows: list[Any],
) -> dict[str, Any]:
    """Validate exact *shape* of up to one batch/consent for a Tenant plan."""
    if (
        not all(isinstance(x, Mapping) for x in (
            resource_report, collector_receipt_review, consent_review,
        ))
        or not isinstance(batch_rows, list) or not isinstance(consent_rows, list)
        or len(batch_rows) > 1 or len(consent_rows) > 1
        or any(type(x) is not int or x <= 0 for x in (
            requester_user_id, reviewer_user_id, successor_user_id,
        ))
        or len({requester_user_id, reviewer_user_id, successor_user_id}) != 3
        or collector_receipt_review.get('collector_mac_verified') is not True
        or collector_receipt_review.get('apiserver_audit_integrity_verified') is not False
        or consent_review.get('consent_source_authenticated') is not False
        or consent_review.get('independent_consent_record_committed') is not False
    ):
        raise ValueError('Capsule proof ledger scope/actors are absent or evidence is overlong.')
    plan_sha = resource_report.get('plan_sha256')
    scope_sha = resource_report.get('resource_review_sha256')
    worklist_sha = resource_report.get('worklist_sha256')
    tenant_id = resource_report.get('tenant_id')
    if (
        not all(isinstance(x, str) and x for x in (
            plan_sha, scope_sha, worklist_sha, tenant_id,
        ))
        or any(
            collector_receipt_review.get(key) != resource_report.get(key)
            for key in ('tenant_id', 'plan_sha256', 'worklist_sha256', 'resource_review_sha256')
        )
        or any(
            consent_review.get(key) != resource_report.get(key)
            for key in ('plan_sha256', 'worklist_sha256', 'resource_review_sha256')
        )
        or consent_review.get('resource_count') != resource_report.get('source_candidate_count')
    ):
        raise ValueError('Capsule collector, consent and resource review SHA do not match.')
    if consent_rows and not batch_rows:
        raise ValueError('Capsule consent proof cannot exist without its parent audit batch.')
    batch_anchor = None
    consent_anchor = None
    if batch_rows:
        batch = batch_rows[0]
        expected = {
            'tenant_id': tenant_id,
            'cluster_id': resource_report.get('cluster_id'),
            'generation': resource_report.get('generation'),
            'plan_sha256': plan_sha,
            'worklist_sha256': worklist_sha,
            'resource_review_sha256': scope_sha,
            'batch_id': collector_receipt_review.get('batch_id'),
            'claims_sha256': collector_receipt_review.get('claims_sha256'),
            'receipt_sha256': collector_receipt_review.get('collector_receipt_sha256'),
            'collector_id': collector_receipt_review.get('collector_id'),
            'key_id': collector_receipt_review.get('key_id'),
        }
        if (
            any(_field(batch, key) != val for key, val in expected.items())
            or type(_field(batch, 'id')) is not int or _field(batch, 'id') <= 0
        ):
            raise ValueError('Committed Capsule audit batch is stale, replayed or cross-plan.')
        batch_recorded = _datetime(_field(batch, 'recorded_at'))
        captured = _datetime(_field(batch, 'captured_at'))
        if captured > batch_recorded:
            raise ValueError('Capsule audit batch was recorded before its claimed capture.')
        batch_anchor = _digest({'id': _field(batch, 'id'), **expected})
    if consent_rows:
        consent = consent_rows[0]
        expected = {
            'tenant_id': tenant_id,
            'batch_id': collector_receipt_review['batch_id'],
            'plan_sha256': plan_sha,
            'worklist_sha256': worklist_sha,
            'resource_review_sha256': scope_sha,
            'consent_manifest_sha256': consent_review.get('resource_consent_manifest_sha256'),
            'resource_scope_sha256': consent_review.get('resource_scope_sha256'),
            'target_count': resource_report.get('source_candidate_count'),
            'requester_user_id': requester_user_id,
            'reviewer_user_id': reviewer_user_id,
            'successor_user_id': successor_user_id,
        }
        if (
            any(_field(consent, key) != val for key, val in expected.items())
            or type(_field(consent, 'id')) is not int or _field(consent, 'id') <= 0
        ):
            raise ValueError('Committed Capsule successor consent changed its exact source scope.')
        accepted = _datetime(_field(consent, 'accepted_at'))
        recorded = _datetime(_field(consent, 'recorded_at'))
        if accepted > recorded or recorded < batch_recorded:
            raise ValueError('Capsule consent and collector commit chronology is impossible.')
        consent_anchor = _digest({'id': _field(consent, 'id'), **expected})
    return {
        'status': (
            'one_batch_and_consent_record_correlated_unattested'
            if consent_rows else (
                'batch_without_committed_consent_requires_manual_review'
                if batch_rows else 'no_committed_proof_evidence_observed'
            )
        ),
        'tenant_id': tenant_id, 'plan_sha256': plan_sha,
        'worklist_sha256': worklist_sha,
        'resource_review_sha256': scope_sha,
        'batch_record_count': len(batch_rows),
        'consent_record_count': len(consent_rows),
        'batch_record_anchor_sha256': batch_anchor,
        'consent_record_anchor_sha256': consent_anchor,
        'historical_replay_absence_proven': False,
        'database_trigger_installation_verified': False,
        'database_write_once_guaranteed': False,
        'collector_key_trust_source_verified': False,
        'apiserver_audit_integrity_verified': False,
        'controller_origin_attested': False,
        'independent_consent_authority_verified': False,
        'resource_specific_handoff_admitted': False,
        'append_authorized': False,
        'provider_execution_admitted': False,
        'provider_handoff_verified': False,
        'auto_retry_authorized': False,
        'release_authorized': False,
    }


def read_capsule_proof_history(
    *, tenant_id: str, resource_report: Mapping[str, Any],
    collector_receipt_review: Mapping[str, Any],
    consent_review: Mapping[str, Any],
    requester_user_id: int, reviewer_user_id: int,
    successor_user_id: int,
) -> dict[str, Any]:
    """Bounded SELECT of *all* attempts for Tenant; never filter old plans away."""
    if (
        not isinstance(tenant_id, str) or not tenant_id
        or not isinstance(resource_report, Mapping)
        or resource_report.get('tenant_id') != tenant_id
    ):
        raise ValueError('Capsule proof history requires exact Tenant scope.')
    batches = (
        CapsuleHandoffAuditBatch.query.filter_by(tenant_id=tenant_id)
        .order_by(CapsuleHandoffAuditBatch.id.asc()).limit(2).all()
    )
    consents = (
        CapsuleHandoffResourceConsentRecord.query.filter_by(tenant_id=tenant_id)
        .order_by(CapsuleHandoffResourceConsentRecord.id.asc()).limit(2).all()
    )
    return inspect_capsule_proof_storage(
        resource_report=resource_report,
        collector_receipt_review=collector_receipt_review,
        consent_review=consent_review,
        requester_user_id=requester_user_id, reviewer_user_id=reviewer_user_id,
        successor_user_id=successor_user_id,
        batch_rows=batches, consent_rows=consents,
    )
