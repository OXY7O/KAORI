from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.tenant import (
    TenantDomainMatchMode,
    TenantDomainReservationStatus,
    TenantExposurePolicyStatus,
)

_HOST_LABEL_RE = re.compile(r'^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$')


@dataclass(frozen=True, slots=True)
class TenantPolicyDecision:
    allowed: bool
    findings: tuple[str, ...]
    reason: str


def _normalize_hostname(value: str) -> str:
    hostname = value.strip().lower().rstrip('.')
    if not hostname or len(hostname) > 253:
        raise ValueError('Hostname must contain 1–253 characters.')
    labels = hostname.split('.')
    if any(not _HOST_LABEL_RE.fullmatch(label) for label in labels):
        raise ValueError('Hostname contains an invalid DNS label.')
    return hostname


def normalize_domain_pattern(value: str, mode: str) -> str:
    selected = TenantDomainMatchMode(mode)
    raw = value.strip()
    if selected is TenantDomainMatchMode.EXACT:
        return _normalize_hostname(raw)
    if selected is TenantDomainMatchMode.WILDCARD:
        if not raw.startswith('*.'):
            raise ValueError('Wildcard hostname reservation must start with *.')
        return '*.' + _normalize_hostname(raw[2:])
    if not raw or len(raw) > 253:
        raise ValueError('Regex hostname reservation must contain 1–253 characters.')
    try:
        re.compile(raw)
    except re.error as exc:
        raise ValueError('Regex hostname reservation is invalid.') from exc
    return raw


def reservation_matches(reservation, hostname: str) -> bool:
    if reservation.status != TenantDomainReservationStatus.ACTIVE.value:
        return False
    candidate = _normalize_hostname(hostname)
    mode = TenantDomainMatchMode(reservation.match_mode)
    pattern = reservation.hostname_pattern
    if mode is TenantDomainMatchMode.EXACT:
        return candidate == pattern
    if mode is TenantDomainMatchMode.WILDCARD:
        suffix = pattern[2:]
        return candidate != suffix and candidate.endswith('.' + suffix)
    return re.fullmatch(pattern, candidate) is not None


def reservations_conflict(first, second) -> bool:
    first_mode = TenantDomainMatchMode(first.match_mode)
    second_mode = TenantDomainMatchMode(second.match_mode)

    if first_mode is TenantDomainMatchMode.EXACT:
        return reservation_matches(second, first.hostname_pattern)
    if second_mode is TenantDomainMatchMode.EXACT:
        return reservation_matches(first, second.hostname_pattern)

    if first_mode is TenantDomainMatchMode.WILDCARD and second_mode is TenantDomainMatchMode.WILDCARD:
        first_suffix = first.hostname_pattern[2:]
        second_suffix = second.hostname_pattern[2:]
        return (
            first_suffix == second_suffix
            or first_suffix.endswith('.' + second_suffix)
            or second_suffix.endswith('.' + first_suffix)
        )

    # Regex overlap is not generally decidable. Fail closed rather than allow ambiguous ownership.
    return True


def evaluate_service_exposure(policy, service_type: str) -> TenantPolicyDecision:
    if policy.status != TenantExposurePolicyStatus.ACTIVE.value:
        return TenantPolicyDecision(False, ('exposure_policy_inactive',), 'Tenant exposure policy is not active.')

    normalized = service_type.strip().lower()
    allowed = {
        'clusterip': bool(policy.allow_cluster_ip),
        'nodeport': bool(policy.allow_node_port),
        'loadbalancer': bool(policy.allow_load_balancer),
        'externalname': bool(policy.allow_external_name),
    }
    if normalized not in allowed:
        return TenantPolicyDecision(False, ('unsupported_service_type',), 'Unsupported Kubernetes Service type.')
    if allowed[normalized]:
        return TenantPolicyDecision(True, (), 'Service type is allowed by the committed Tenant exposure policy.')
    return TenantPolicyDecision(
        False,
        ('service_exposure_violation',),
        'Service type is denied by the committed Tenant exposure policy.',
    )


def evaluate_ingress_hosts(
    reservations,
    *,
    environment_id: int,
    hosts: list[str],
) -> TenantPolicyDecision:
    active = [
        item
        for item in reservations
        if item.status == TenantDomainReservationStatus.ACTIVE.value
        and item.tenant_environment_id == environment_id
    ]
    if not hosts:
        return TenantPolicyDecision(False, ('unregistered_domain',), 'Ingress requires at least one registered hostname.')

    missing = [
        _normalize_hostname(host)
        for host in hosts
        if not any(reservation_matches(reservation, host) for reservation in active)
    ]
    if missing:
        return TenantPolicyDecision(
            False,
            ('unregistered_domain',),
            'Ingress hostname is not reserved for the selected Tenant environment.',
        )
    return TenantPolicyDecision(True, (), 'All Ingress hostnames are reserved for the selected Tenant environment.')


def require_policy_enforcement_capability(*, enforcement_required: bool, admission_ready: bool) -> None:
    if enforcement_required and not admission_ready:
        raise ValueError('Required admission enforcement capability is unavailable; Tenant policy fails closed.')
