"""Code-path coverage summary for the central Alert Intelligence workspace (#5230).

This is an implementation matrix, not runtime readiness, provider health,
instance enumeration, or permission. The owning evaluator/adapter remains
authoritative for every actual case read, lifecycle transition and delivery.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.intelligence.alert_intelligence.provider_case_scope import registered_provider_case_adapters


@dataclass(frozen=True, slots=True)
class _CoverageSpec:
    domain: str
    domain_label: str
    provider_key: str
    provider_label: str
    case_origin: str
    limitation: str


_COVERAGE = (
    _CoverageSpec(
        'kubernetes', 'Kubernetes', 'kubernetes', 'Kubernetes', 'Recommendation',
        'Committed evaluator findings only; native provider-origin case admission is not registered.',
    ),
    _CoverageSpec(
        'object_storage', 'Object Storage', 'minio', 'MinIO', 'Recommendation',
        'Committed evaluator findings only; no MinIO-native provider-origin case admission.',
    ),
    _CoverageSpec(
        'registry', 'Artifact Registry', 'harbor', 'Harbor', 'Recommendation',
        'Committed evaluator findings only; registry routing keeps its dedicated scope guard.',
    ),
    _CoverageSpec(
        'secrets_pki', 'Secrets & PKI', 'vault', 'Vault', 'Provider alert',
        'Exact-instance scoped reads; lifecycle, recovery and outbound delivery remain separately gated.',
    ),
    _CoverageSpec(
        'secrets_pki', 'Secrets & PKI', 'openbao', 'OpenBao', 'Not admitted',
        'Inventory integration is not authorization for a Vault-compatible alert source.',
    ),
    _CoverageSpec(
        'source_control', 'Source Control', 'github', 'GitHub', 'Not admitted',
        'No approved provider-origin AlertCase adapter or source evidence contract.',
    ),
    _CoverageSpec(
        'infrastructure_automation', 'Infrastructure Automation', 'ansible', 'Ansible', 'Not admitted',
        'No approved provider-origin AlertCase adapter or source evidence contract.',
    ),
    _CoverageSpec(
        'authentication', 'Authentication', '', 'Domain-owned', 'Not admitted',
        'Committed abuse signal exists; recommendation rule, scoped case lifecycle and routing are Reserved Plan.',
    ),
)


def provider_coverage_rows() -> list[dict[str, str]]:
    """Expose a stable, non-sensitive capability inventory (not per-instance evidence).

    'Scoped read registered' means only that an adapter exists, not that its
    upstream observation, recovery, delivery, or runtime UAT was qualified.
    """
    registered = registered_provider_case_adapters()
    rows: list[dict[str, str]] = []
    for spec in _COVERAGE:
        key = (spec.domain, spec.provider_key)
        if key in registered:
            status, tone = 'Scoped read registered', 'info'
        elif spec.case_origin == 'Recommendation':
            status, tone = 'Evaluator path', 'info'
        else:
            status, tone = 'Not qualified', 'warning'
        rows.append(
            {
                'domain': spec.domain_label,
                'provider': spec.provider_label,
                'origin': spec.case_origin,
                'status': status,
                'tone': tone,
                'limitation': spec.limitation,
            }
        )
    return rows
