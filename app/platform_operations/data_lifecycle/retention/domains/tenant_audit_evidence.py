from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

from flask import current_app
from sqlalchemy import func

from app.extensions.db import db
from app.models.tenant_audit import TenantAuditEvidence
from app.platform_operations.data_lifecycle.retention.policy_service import resolve_policy
from app.platform_operations.data_lifecycle.retention.types import ArchiveBoundary, PartialCleanupError, RetentionPolicy


class TenantAuditEvidenceArchiveDomain:
    name = 'tenant_audit_evidence'
    source_model = 'tenant_audit_evidence'
    schema_version = 1

    def build_policy(self) -> RetentionPolicy:
        fallback = RetentionPolicy(
            domain=self.name,
            enabled=_bool_config('TENANT_AUDIT_RETENTION_ENABLED', True),
            retention_days=_positive_int_config('TENANT_AUDIT_RETENTION_DAYS', 90),
            archive_retention_days=_positive_int_config('TENANT_AUDIT_ARCHIVE_RETENTION_DAYS', 365),
            batch_size=max(100, min(_positive_int_config('TENANT_AUDIT_RETENTION_BATCH_SIZE', 5000), 25000)),
            protect_unreviewed=False,
            protected_max_days=None,
            settings={'source_boundary': 'normalized_correlation_evidence'},
        )
        return resolve_policy(self.name, fallback)

    def inspect_boundary(self, policy: RetentionPolicy) -> ArchiveBoundary:
        now = datetime.now(UTC)
        cutoff = now - timedelta(days=policy.retention_days)
        count, maximum_id, range_start, range_end = (
            db.session.query(
                func.count(TenantAuditEvidence.id),
                func.max(TenantAuditEvidence.id),
                func.min(TenantAuditEvidence.event_at),
                func.max(TenantAuditEvidence.event_at),
            )
            .filter(TenantAuditEvidence.event_at < cutoff)
            .one()
        )
        return ArchiveBoundary(
            selected_at=now,
            cutoff_at=cutoff,
            maximum_record_id=int(maximum_id) if maximum_id is not None else None,
            record_count=int(count or 0),
            range_start=_as_utc(range_start),
            range_end=_as_utc(range_end),
            protected_record_count=0,
            protected_cutoff_at=None,
        )

    def iter_records(
        self,
        boundary: ArchiveBoundary,
        policy: RetentionPolicy,
    ) -> Iterator[dict[str, Any]]:
        if boundary.maximum_record_id is None or boundary.record_count <= 0:
            return
        last_id = 0
        while True:
            rows = (
                TenantAuditEvidence.query.filter(
                    TenantAuditEvidence.event_at < boundary.cutoff_at,
                    TenantAuditEvidence.id <= boundary.maximum_record_id,
                    TenantAuditEvidence.id > last_id,
                )
                .order_by(TenantAuditEvidence.id.asc())
                .limit(policy.batch_size)
                .all()
            )
            if not rows:
                break
            for item in rows:
                last_id = item.id
                yield self._serialize(item)
            db.session.expire_all()

    def cleanup_records(self, record_ids: Iterable[Any], policy: RetentionPolicy) -> int:
        deleted_total = 0
        batch: list[int] = []
        try:
            for record_id in record_ids:
                batch.append(int(record_id))
                if len(batch) >= policy.batch_size:
                    deleted_total += self._delete_batch(batch)
                    batch = []
            if batch:
                deleted_total += self._delete_batch(batch)
        except Exception as exc:
            db.session.rollback()
            raise PartialCleanupError(
                'Tenant audit evidence cleanup stopped after one or more committed batches.',
                deleted_total,
            ) from exc
        return deleted_total

    @staticmethod
    def _delete_batch(record_ids: list[int]) -> int:
        deleted = TenantAuditEvidence.query.filter(
            TenantAuditEvidence.id.in_(record_ids)
        ).delete(synchronize_session=False)
        db.session.commit()
        return int(deleted or 0)

    @staticmethod
    def _serialize(item: TenantAuditEvidence) -> dict[str, Any]:
        return {
            'schema_version': 1,
            'domain': 'tenant_audit_evidence',
            'source': {'model': 'tenant_audit_evidence', 'record_id': item.id},
            'evidence': {
                'public_id': item.public_id,
                'cluster_id': item.cluster_id,
                'tenant_id': item.tenant_id,
                'environment_id': item.tenant_environment_id,
                'namespace_id': item.tenant_namespace_id,
                'access_grant_id': item.access_grant_id,
                'credential_id': item.credential_id,
                'owner_user_id': item.owner_user_id,
                'source_kind': item.source_kind,
                'source_event_id': item.source_event_id,
                'idempotency_key': item.idempotency_key,
                'source_reference': item.source_reference,
                'principal_username': item.principal_username,
                'principal_groups': list(item.principal_groups_json or []),
                'principal_kind': item.principal_kind,
                'identity_class': item.identity_class,
                'correlation_status': item.correlation_status,
                'credential_status': item.credential_status,
                'credential_type': item.credential_type,
                'jumpserver_reference': item.jumpserver_reference,
                'resource_group': item.resource_group,
                'resource_version': item.resource_version,
                'resource': item.resource,
                'subresource': item.subresource,
                'resource_name': item.resource_name,
                'namespace': item.kubernetes_namespace,
                'verb': item.verb,
                'response_code': item.response_code,
                'outcome': item.outcome,
                'event_at': _isoformat(item.event_at),
                'observed_at': _isoformat(item.observed_at),
                'secret_material_persisted': False,
            },
        }


def _positive_int_config(key: str, default: int) -> int:
    try:
        return max(int(current_app.config.get(key, default)), 1)
    except (TypeError, ValueError):
        return default


def _bool_config(key: str, default: bool) -> bool:
    value = current_app.config.get(key, default)
    if isinstance(value, bool):
        return value
    return str(value or '').strip().lower() in {'1', 'true', 'yes', 'y', 'on'}


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _isoformat(value: datetime | None) -> str | None:
    normalized = _as_utc(value)
    return normalized.isoformat() if normalized is not None else None
