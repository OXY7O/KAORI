from types import SimpleNamespace

from app.intelligence.tenant_governance_recommendations import (
    audit_rule_keys,
    capacity_rule_key,
    credential_rule_keys,
    provider_rule_key,
)


def test_credential_rule_keys_cover_renewal_and_inactive_owner() -> None:
    credential = SimpleNamespace(status='renewal_due')
    owner = SimpleNamespace(is_active=False)
    assert credential_rule_keys(credential, owner=owner) == (
        'kubernetes.tenant.credential.renewal_due',
        'kubernetes.tenant.credential.inactive_owner_active_access',
    )


def test_capacity_rule_key_preserves_canonical_capacity_state() -> None:
    assert capacity_rule_key('Near Capacity', decision='allow') == 'kubernetes.tenant.capacity.near_capacity'
    assert capacity_rule_key('Exhausted', decision='block') == 'kubernetes.tenant.capacity.exhausted'
    assert capacity_rule_key('Overcommitted', decision='block') == 'kubernetes.tenant.capacity.overcommitted'
    assert capacity_rule_key('Unknown', decision='allow') == 'kubernetes.tenant.capacity.evidence_unknown'
    assert capacity_rule_key('Healthy', decision='block') == 'kubernetes.tenant.capacity.allocation_denied'
    assert capacity_rule_key('Healthy', decision='allow') is None


def test_provider_rule_key_uses_provider_state_not_provider_name() -> None:
    assert provider_rule_key('capsule_degraded') == 'kubernetes.tenant.provider.degraded'
    assert provider_rule_key('native_recovery') == 'kubernetes.tenant.provider.native_recovery'
    assert provider_rule_key('native') is None
    assert provider_rule_key('capsule') is None


def test_audit_rule_keys_detect_revoked_use_and_production_human_mutation() -> None:
    evidence = SimpleNamespace(
        outcome='success',
        credential_status='revoked',
        identity_class='human',
        correlation_status='matched',
        verb='patch',
        resource='deployments',
    )
    assert audit_rule_keys(evidence, production=True) == (
        'kubernetes.tenant.credential.revoked_still_usable',
        'kubernetes.tenant.production.human_mutation',
        'kubernetes.tenant.production.deployment_outside_cicd',
    )


def test_unmanaged_principal_is_explicit_governance_finding() -> None:
    evidence = SimpleNamespace(
        outcome='success',
        credential_status=None,
        identity_class='unmanaged',
        correlation_status='unmanaged',
        verb='get',
        resource='pods',
    )
    assert audit_rule_keys(evidence, production=False) == ('kubernetes.tenant.access.unmanaged_principal',)
