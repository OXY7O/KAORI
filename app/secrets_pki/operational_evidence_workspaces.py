"""Read-only source-qualified operational workspaces for Secrets & PKI.

No live Vault API call, Secret identity/path/values, rotation/lease
claim, unverified consumer lineage, or new provider state is materialized.
"""

from __future__ import annotations

from typing import Any

from app.secrets_pki.binding_coverage import build_vault_binding_coverage
from app.secrets_pki.certificate_delivery_read_model import build_certificate_delivery_overlap
from app.secrets_pki.kv2_version_posture import build_kv2_version_posture
from app.secrets_pki.pki_validity_posture import build_stored_pki_validity_posture
from app.secrets_pki.presentation import build_secrets_pki_operational_summary

_PAGE = {
    'leases': (
        'Leases & Renewal',
        'Known Lease observations and verified renewal are not materialized. '
        'KV v2 version metadata is shown separately and is never Lease evidence.',
        'clock-3',
    ),
    'consumers': (
        'Consumers & Dependencies',
        'Cross-domain public TLS evidence is separate from confirmed Secret '
        'consumer adoption or verified rotation cutover.',
        'waypoints',
    ),
    'governance': (
        'Secrets & PKI Governance',
        'Independent committed source coverage, telemetry binding readiness '
        'and evidence limits, without revealing scope-policy targets.',
        'shield-check',
    ),
}


def _metric(
    label: str,
    value: int | None,
    description: str,
    icon: str,
) -> dict[str, Any]:
    return {'label': label, 'value': value, 'description': description, 'icon': icon}


def build_operational_evidence_workspace(
    *,
    kind: str,
    can_view_kubernetes_tls: bool = False,
) -> dict[str, Any]:
    """Never convert unobserved or partial source evidence to a numeric zero."""
    if kind not in _PAGE:
        raise ValueError('Unknown Secrets & PKI operational workspace.')
    title, description, icon = _PAGE[kind]
    metrics: list[dict[str, Any]] = []
    source_rows: list[dict[str, str]] = []
    if kind == 'leases':
        kv2 = build_kv2_version_posture()
        ready = kv2.get('status') in {'ready', 'observed_empty'}
        metrics = [
            _metric('Known Leases', None, 'No source-qualified persisted Lease collector.', 'clock-3'),
            _metric('Renewals Verified', None, 'Not inferred from KV v2 version changes.', 'refresh-cw'),
            _metric('Revocations Verified', None, 'No provider Lease revocation proof.', 'shield-check'),
            _metric(
                'Observed KV v2 Versions',
                kv2.get('observed_versions') if ready else None,
                'Independent committed KV v2 version context only.',
                'layers',
            ),
        ]
        source_rows = [
            {
                'label': 'Known Lease Evidence',
                'status': 'Not Materialized',
                'description': 'A Lease collector and scoped committed observation are required.',
            },
            {
                'label': 'KV v2 Version Context',
                'status': str(kv2.get('label') or 'Unavailable'),
                'description': 'Version existence does not establish rotation or Lease renewal.',
            },
        ]
    elif kind == 'consumers':
        # The TLS Governance owning domain must separately authorize the
        # reader. No query runs when that permission is not granted.
        delivery = (
            build_certificate_delivery_overlap(
                authorized_to_view_kubernetes_tls=True,
            )
            if can_view_kubernetes_tls
            else None
        )
        qualified = bool(delivery is not None and delivery.get('status') in {'overlap_observed', 'no_overlap_observed'})
        metrics = [
            _metric('Confirmed Secret Consumers', None, 'No verified consumer lineage materialization.', 'users'),
            _metric('Verified Rotation Cutovers', None, 'Consumer version readback not yet committed.', 'refresh-cw'),
            _metric(
                'Observed Public TLS Overlap',
                delivery.get('overlapping_certificates') if qualified else None,
                'Only an observed public certificate match, not delivery proof.',
                'shield-check',
            ),
            _metric(
                'TLS Secrets Matched',
                delivery.get('matching_kubernetes_tls_secrets') if qualified else None,
                'Separately authorized Kubernetes TLS evidence only.',
                'waypoints',
            ),
        ]
        source_rows = [
            {
                'label': 'Secret Consumer Lineage',
                'status': 'Not Materialized',
                'description': 'Confirmed workload, CI/CD and automation links require owner evidence.',
            },
            {
                'label': 'Public Certificate Overlap',
                'status': str(delivery.get('label') or 'Additional TLS Permission Required')
                if delivery is not None
                else 'Additional TLS Permission Required',
                'description': 'Fingerprint overlap cannot prove Vault delivery or endpoint serving.',
            },
        ]
    else:
        posture = build_secrets_pki_operational_summary()
        bindings = build_vault_binding_coverage()
        validity = build_stored_pki_validity_posture()
        inventory_qualified = posture.get('state') == 'committed'
        metrics_binding = bindings.get('metrics') or {}
        alert_binding = bindings.get('alerts') or {}
        metrics = [
            _metric(
                'Committed KV v2 Mounts',
                posture.get('committed_mount_count') if inventory_qualified else None,
                'Approved and committed collection coverage only.',
                'database-zap',
            ),
            _metric(
                'Qualified Metrics Sources',
                metrics_binding.get('qualified_vault_sources')
                if metrics_binding.get('status') == 'qualified'
                else None,
                'Binding validation does not establish historical retention.',
                'chart-spline',
            ),
            _metric(
                'Qualified Alert Sources',
                alert_binding.get('qualified_vault_sources') if alert_binding.get('status') == 'qualified' else None,
                'Not current firing, delivery or resolved AlertCases.',
                'bell-ring',
            ),
            _metric(
                'Qualified Public Certificates',
                validity.get('observed_stored_certificates') if validity.get('status') == 'ready' else None,
                'Current-generation public validity; not Secret export.',
                'certificate',
            ),
        ]
        source_rows = [
            {
                'label': 'KV v2 Inventory',
                'status': str(posture.get('label') or 'Unavailable'),
                'description': 'Committed collection status independent of Vault API readiness.',
            },
            {
                'label': 'Metrics Source',
                'status': str(metrics_binding.get('label') or 'Unavailable'),
                'description': 'Binding identity validation is not MetricsConsumer history.',
            },
            {
                'label': 'Alert Source',
                'status': str(alert_binding.get('label') or 'Unavailable'),
                'description': 'AlertCase routing and notification activation remain disabled.',
            },
            {
                'label': 'Public PKI Validity',
                'status': str(validity.get('label') or 'Unavailable'),
                'description': 'Public X.509 validity does not prove CA trust or revocation.',
            },
            {
                'label': 'Resource Authorization',
                'status': 'Per-Resource Policy Required',
                'description': 'RBAC alone never admits per-Secret or Vault mount metadata reads.',
            },
        ]
    return {
        'workspace': kind,
        'title': title,
        'description': description,
        'icon': icon,
        'metrics': metrics,
        'source_rows': source_rows,
    }
