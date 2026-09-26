from types import SimpleNamespace

import pytest

from app.kubernetes.tenant.domain_exposure import (
    evaluate_ingress_hosts,
    evaluate_service_exposure,
    normalize_domain_pattern,
    require_policy_enforcement_capability,
    reservation_matches,
    reservations_conflict,
)


def _reservation(pattern: str, mode: str = 'exact', *, environment_id: int = 1, tenant_id: str = 'tenant-a'):
    return SimpleNamespace(
        hostname_pattern=pattern,
        match_mode=mode,
        status='active',
        tenant_environment_id=environment_id,
        tenant_id=tenant_id,
    )


def _policy(**overrides):
    values = {
        'allow_cluster_ip': True,
        'allow_ingress': True,
        'allow_node_port': False,
        'allow_load_balancer': False,
        'allow_external_name': False,
        'status': 'active',
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_exact_domain_never_implicitly_allows_subdomain() -> None:
    reservation = _reservation(normalize_domain_pattern('x.com', 'exact'))
    assert reservation_matches(reservation, 'x.com') is True
    assert reservation_matches(reservation, 'api.x.com') is False


def test_wildcard_is_explicit_and_does_not_match_apex() -> None:
    reservation = _reservation(normalize_domain_pattern('*.x.com', 'wildcard'), 'wildcard')
    assert reservation_matches(reservation, 'api.x.com') is True
    assert reservation_matches(reservation, 'x.com') is False


def test_cross_scope_domain_collisions_are_detected_fail_closed() -> None:
    assert reservations_conflict(_reservation('x.com'), _reservation('x.com', tenant_id='tenant-b')) is True
    assert (
        reservations_conflict(
            _reservation('*.x.com', 'wildcard'),
            _reservation('api.x.com', tenant_id='tenant-b'),
        )
        is True
    )


def test_default_exposure_profile_denies_public_service_types() -> None:
    policy = _policy()
    assert evaluate_service_exposure(policy, 'ClusterIP').allowed is True
    assert evaluate_service_exposure(policy, 'NodePort').allowed is False
    assert evaluate_service_exposure(policy, 'LoadBalancer').allowed is False
    assert evaluate_service_exposure(policy, 'ExternalName').allowed is False


def test_ingress_requires_registered_hostname_for_same_environment() -> None:
    reservations = [_reservation('api.x.com', environment_id=3)]
    allowed = evaluate_ingress_hosts(reservations, environment_id=3, hosts=['api.x.com'])
    denied = evaluate_ingress_hosts(reservations, environment_id=3, hosts=['other.x.com'])
    assert allowed.allowed is True
    assert denied.allowed is False
    assert 'unregistered_domain' in denied.findings


def test_security_sensitive_enforcement_fails_closed_when_capability_is_missing() -> None:
    with pytest.raises(ValueError, match='admission'):
        require_policy_enforcement_capability(enforcement_required=True, admission_ready=False)
