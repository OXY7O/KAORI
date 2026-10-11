from __future__ import annotations

from flask import url_for

from app.models.job import JobExecution
from app.models.notification import Notification
from app.models.tenant import Tenant
from app.models.tenant_audit import TenantAuditEvidence
from app.platform_operations.notifications.metadata import redact_operational_metadata


def _source_identifier(value: object) -> str | None:
    """Only bounded identifiers; never accept an arbitrary URL from metadata."""
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized or len(normalized) > 64:
        return None
    if not all(char.isascii() and (char.isalnum() or char == '-') for char in normalized):
        return None
    return normalized


def build_related_source_links(
    *, notification_id: int, can_view_jobs: bool, can_view_tenants: bool
) -> list[dict[str, str]]:
    """Return only source-permissioned links verified against committed records."""
    if not can_view_jobs and not can_view_tenants:
        return []
    notification = Notification.query.filter_by(id=notification_id).first()
    if notification is None:
        return []
    metadata = redact_operational_metadata(notification.metadata_json) or {}
    links: list[dict[str, str]] = []
    if can_view_jobs:
        job_id = _source_identifier(metadata.get('job_public_id'))
        if job_id and JobExecution.query.filter_by(public_id=job_id).first() is not None:
            links.append({
                'label': 'Job Execution',
                'note': 'Execution state is owned by Jobs; this is not another audit record.',
                'url': url_for('jobs.executions', execution_tab='registry', search=job_id),
            })
    if can_view_tenants:
        evidence_id = _source_identifier(metadata.get('tenant_audit_evidence_id'))
        if evidence_id:
            evidence = TenantAuditEvidence.query.filter_by(public_id=evidence_id).first()
            if evidence is not None and evidence.tenant_id:
                tenant = Tenant.query.filter_by(id=evidence.tenant_id).first()
                if tenant is not None:
                    links.append({
                        'label': 'Tenant Governance',
                        'note': 'Related tenant workspace; Kubernetes audit evidence remains source-owned.',
                        'url': url_for('tenant.tenant_detail', tenant_id=evidence.tenant_id),
                    })
    return links
