from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.kubernetes.tenant.credential import (
    effective_credential_status,
    normalize_credential_purpose,
    token_ttl_seconds,
    validate_credential_contract,
)


def _times(days: int = 365):
    now = datetime.now(UTC)
    return now, now + timedelta(days=days - 30), now + timedelta(days=days)


def _human_credential(*, status='active', delivery='jumpserver'):
    started, renewal_due, valid_until = _times()
    owner = SimpleNamespace(id=7, is_active=True, is_admin_level=False)
    membership = SimpleNamespace(
        tenant_id='tenant-a',
        principal_type='user',
        user_id=7,
        status='active',
        user=owner,
        group=None,
        subject_name='alice',
    )
    namespace = SimpleNamespace(
        id=11,
        namespace='payments-dev',
        provisioning_status='ready',
        ownership_status='managed',
        environment=SimpleNamespace(tenant_id='tenant-a'),
    )
    grant = SimpleNamespace(
        tenant_id='tenant-a',
        scope_type='namespace',
        environment=None,
        namespace=namespace,
        membership=membership,
        status='active',
        access_profile='operator',
        access_profile_version=1,
    )
    return SimpleNamespace(
        credential_type='human_service_account',
        delivery_method=delivery,
        tenant_id='tenant-a',
        tenant=SimpleNamespace(provider_key='native_kubernetes', cluster_id='cluster-a'),
        owner_user_id=7,
        owner_user=owner,
        access_grant=grant,
        anchor_namespace=None,
        purpose='interactive',
        status=status,
        jumpserver_reference='jumpserver://account/alice-payments',
        exception_authorized_by=None,
        exception_reason=None,
        exception_valid_until=None,
        valid_from=started,
        renewal_due_at=renewal_due,
        valid_until=valid_until,
    )


def test_credential_purpose_is_normalized() -> None:
    assert normalize_credential_purpose('Interactive Access') == 'interactive-access'
    with pytest.raises(ValueError):
        normalize_credential_purpose('***')


def test_default_human_credential_is_jumpserver_first_and_individually_owned() -> None:
    credential = _human_credential()
    validate_credential_contract(credential)
    assert credential.access_grant.membership.user_id == credential.owner_user_id
    assert credential.delivery_method == 'jumpserver'


def test_human_credential_rejects_deployer_machine_profile() -> None:
    credential = _human_credential()
    credential.access_grant.access_profile = 'deployer'
    with pytest.raises(ValueError, match='machine-only Deployer'):
        validate_credential_contract(credential)


def test_exceptional_kubeconfig_requires_active_admin_approval() -> None:
    credential = _human_credential(delivery='exceptional_kubeconfig')
    credential.exception_reason = 'Approved workstation troubleshooting'
    credential.exception_valid_until = datetime.now(UTC) + timedelta(hours=4)
    credential.exception_authorized_by = SimpleNamespace(is_active=True, is_admin_level=False)

    with pytest.raises(ValueError, match='administrator approval'):
        validate_credential_contract(credential)

    credential.exception_authorized_by = SimpleNamespace(is_active=True, is_admin_level=True)
    validate_credential_contract(credential)


def test_short_lived_token_never_outlives_entitlement_or_exception() -> None:
    credential = _human_credential()
    now = datetime.now(UTC)
    credential.valid_until = now + timedelta(minutes=20)
    assert token_ttl_seconds(credential, requested_seconds=3600, now=now) <= 20 * 60

    credential.delivery_method = 'exceptional_kubeconfig'
    credential.exception_authorized_by = SimpleNamespace(is_active=True, is_admin_level=True)
    credential.exception_reason = 'Approved exception'
    credential.exception_valid_until = now + timedelta(minutes=10)
    assert token_ttl_seconds(credential, requested_seconds=3600, now=now) <= 10 * 60


def test_expired_and_suspended_credentials_cannot_issue_material() -> None:
    credential = _human_credential()
    now = datetime.now(UTC)
    credential.valid_until = now - timedelta(seconds=1)
    assert effective_credential_status(credential, now=now) == 'expired'
    with pytest.raises(ValueError, match='not active'):
        token_ttl_seconds(credential, now=now)

    credential = _human_credential(status='suspended')
    with pytest.raises(ValueError, match='not active'):
        token_ttl_seconds(credential)


def test_revoked_credential_can_still_validate_for_provider_cleanup_after_grant_revocation() -> None:
    credential = _human_credential(status='revoked')
    credential.access_grant.status = 'revoked'
    credential.access_grant.membership.status = 'revoked'
    credential.owner_user.is_active = False
    validate_credential_contract(credential)
