"""Bounded, committed-only PKI evidence workspaces; never render provider data."""

from __future__ import annotations

from typing import Any

from app.secrets_pki.certificate_delivery_read_model import build_certificate_delivery_overlap
from app.secrets_pki.pki_presentation import pki_public_readiness
from app.secrets_pki.pki_stored_presentation import stored_pki_certificate_readiness
from app.secrets_pki.pki_validity_posture import build_stored_pki_validity_posture

_WORKSPACES = {
    'certificates': {
        'title': 'Certificates',
        'description': (
            'Source-qualified stored public certificate validity and independent'
            ' consumer evidence; not CA trust or endpoint serving.'
        ),
        'icon': 'certificate',
    },
    'pki': {
        'title': 'PKI',
        'description': (
            'Approved public Vault PKI issuer and stored-certificate collection posture from committed evidence only.'
        ),
        'icon': 'shield-check',
    },
    'expiration': {
        'title': 'Expiration',
        'description': (
            'Current-generation X.509 expiry windows. No inferred credential rotation, revocation or Lease lifecycle.'
        ),
        'icon': 'calendar-clock',
    },
}


def _metric(label: str, value: int | None, description: str, icon: str) -> dict[str, Any]:
    return {'label': label, 'value': value, 'description': description, 'icon': icon}


def build_pki_evidence_workspace(
    *,
    kind: str,
    can_view_kubernetes_tls: bool = False,
) -> dict[str, Any]:
    """Return safe capability-wide counters only when each owning source qualifies."""
    if kind not in _WORKSPACES:
        raise ValueError('Unsupported Secrets & PKI workspace.')

    validity = build_stored_pki_validity_posture()
    expiry_ready = validity.get('status') == 'ready'
    metrics: list[dict[str, Any]]
    public: dict[str, Any] | None = None
    stored: dict[str, Any] | None = None
    delivery: dict[str, Any] | None = None

    if kind == 'pki':
        public = pki_public_readiness()
        stored = stored_pki_certificate_readiness()
        public_ready = public.get('state') == 'committed'
        stored_ready = stored.get('state') == 'committed'
        metrics = [
            _metric(
                'Approved PKI Mounts',
                public.get('approved_mounts') if public_ready else None,
                'Configured public issuer scope only.',
                'layers',
            ),
            _metric(
                'Committed PKI Mounts',
                public.get('committed_mounts') if public_ready else None,
                'Qualified source collection coverage.',
                'database-zap',
            ),
            _metric(
                'Observed Public Issuers',
                public.get('observed_issuers') if public_ready else None,
                'Issuer metadata, not all issued certificates.',
                'shield-check',
            ),
            _metric(
                'Stored Public Certificates',
                stored.get('observed_certificates') if stored_ready else None,
                'Opted-in stored public leaf evidence only.',
                'certificate',
            ),
        ]
    elif kind == 'certificates':
        stored = stored_pki_certificate_readiness()
        if can_view_kubernetes_tls:
            delivery = build_certificate_delivery_overlap(
                authorized_to_view_kubernetes_tls=True,
            )
        metrics = [
            _metric(
                'Stored Public Certificates',
                validity.get('observed_stored_certificates') if expiry_ready else None,
                'Qualified current-generation observations.',
                'certificate',
            ),
            _metric(
                'Within Validity',
                validity.get('within_validity_window') if expiry_ready else None,
                'Time-window validity, not CA trust.',
                'shield-check',
            ),
            _metric(
                'Expired',
                validity.get('expired') if expiry_ready else None,
                'Expired public X.509 validity windows.',
                'calendar-x',
            ),
            _metric(
                'Validity Unknown',
                validity.get('unknown') if expiry_ready else None,
                'Unknown validity remains unknown.',
                'shield-question',
            ),
        ]
    else:
        metrics = [
            _metric(
                'Expired',
                validity.get('expired') if expiry_ready else None,
                'Public stored certificates already expired.',
                'calendar-x',
            ),
            _metric(
                'Expires Within 7 Days',
                validity.get('expires_within_7d') if expiry_ready else None,
                'Current-generation 7-day window.',
                'calendar-clock',
            ),
            _metric(
                'Expires in 8–30 Days',
                validity.get('expires_8_to_30d') if expiry_ready else None,
                'Current-generation 8–30-day window.',
                'calendar-days',
            ),
            _metric(
                'Expires After 30 Days',
                validity.get('expires_after_30d') if expiry_ready else None,
                'Beyond current 30-day window.',
                'calendar-check',
            ),
        ]

    return {
        'workspace': kind,
        'title': _WORKSPACES[kind]['title'],
        'description': _WORKSPACES[kind]['description'],
        'icon': _WORKSPACES[kind]['icon'],
        'metrics': metrics,
        'validity': validity,
        'public': public,
        'stored': stored,
        'delivery': delivery,
        'can_view_kubernetes_tls': can_view_kubernetes_tls,
    }
