from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.kubernetes.tenant.access import membership_subject, validate_active_grant
from app.kubernetes.tenant.credential import token_ttl_seconds, validate_credential_contract


def _deployer_credential(*, profile: str = 'deployer', principal_type: str = 'service_account'):
    now = datetime.now(UTC)
    owner = SimpleNamespace(id=11, is_active=True, is_admin_level=True)
    namespace = SimpleNamespace(
        id=41,
        namespace='payments-staging',
        provisioning_status='ready',
        ownership_status='managed',
        cluster_id='cluster-a',
        environment=SimpleNamespace(id=31, tenant_id='tenant-a', environment='staging'),
    )
    membership = SimpleNamespace(
        tenant_id='tenant-a',
        principal_type=principal_type,
        user_id=None,
        group_id=None,
        status='active',
        user=None,
        group=None,
        subject_name='kaori-deploy-payments-staging-a1b2c3d4',
    )
    grant = SimpleNamespace(
        tenant_id='tenant-a',
        scope_type='namespace',
        environment=None,
        namespace=namespace,
        membership=membership,
        status='active',
        access_profile=profile,
        access_profile_version=1,
    )
    credential = SimpleNamespace(
        credential_type='deployer_service_account',
        delivery_method='cicd_kubeconfig',
        tenant_id='tenant-a',
        tenant=SimpleNamespace(provider_key='native_kubernetes', cluster_id='cluster-a'),
        owner_user_id=owner.id,
        owner_user=owner,
        access_grant=grant,
        anchor_namespace=None,
        application_name='payments-api',
        purpose='github-actions-helm',
        status='active',
        service_account_name=membership.subject_name,
        jumpserver_reference=None,
        exception_authorized_by=None,
        exception_reason=None,
        exception_valid_until=None,
        valid_from=now,
        renewal_due_at=now + timedelta(days=335),
        valid_until=now + timedelta(days=365),
    )
    return credential


def test_service_account_membership_is_a_first_class_kubernetes_subject() -> None:
    credential = _deployer_credential()
    assert membership_subject(credential.access_grant.membership) == ('ServiceAccount', credential.service_account_name)


def test_deployer_credential_requires_machine_only_deployer_grant() -> None:
    credential = _deployer_credential()
    validate_credential_contract(credential)

    credential.access_grant.access_profile = 'operator'
    with pytest.raises(ValueError, match='Deployer Access Profile'):
        validate_credential_contract(credential)


def test_human_principal_cannot_hold_machine_only_deployer_access() -> None:
    credential = _deployer_credential(principal_type='user')
    credential.access_grant.membership.user_id = credential.owner_user_id
    credential.access_grant.membership.user = credential.owner_user
    credential.access_grant.membership.subject_name = 'operator@example.test'

    with pytest.raises(ValueError, match='ServiceAccount'):
        validate_active_grant(credential.access_grant)


def test_deployer_credential_is_namespace_and_application_bound() -> None:
    credential = _deployer_credential()
    validate_credential_contract(credential)

    credential.access_grant.scope_type = 'environment'
    credential.access_grant.environment = credential.access_grant.namespace.environment
    credential.access_grant.namespace = None
    with pytest.raises(ValueError, match='namespace-scoped'):
        validate_credential_contract(credential)

    credential = _deployer_credential()
    credential.application_name = ''
    with pytest.raises(ValueError, match='application'):
        validate_credential_contract(credential)


def test_deployer_material_is_short_lived() -> None:
    credential = _deployer_credential()
    ttl = token_ttl_seconds(credential, requested_seconds=7200)
    assert 300 <= ttl <= 3600
