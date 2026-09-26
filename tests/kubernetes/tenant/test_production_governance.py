from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.kubernetes.tenant.production_governance import evaluate_production_access


def _namespace(environment: str = 'production'):
    return SimpleNamespace(
        id=41,
        namespace='payments-prod' if environment == 'production' else 'payments-staging',
        environment=SimpleNamespace(environment=environment, tenant_id='tenant-a'),
    )


def _grant(*, profile: str, principal_type: str, namespace=None):
    namespace = namespace or _namespace()
    membership = SimpleNamespace(
        tenant_id='tenant-a',
        principal_type=principal_type,
        status='active',
        user_id=7 if principal_type == 'user' else None,
        user=SimpleNamespace(id=7, is_active=True, is_admin_level=False) if principal_type == 'user' else None,
        subject_name='alice' if principal_type == 'user' else 'kaori-deploy-payments-prod',
    )
    return SimpleNamespace(
        id=9,
        public_id='grant-9',
        tenant_id='tenant-a',
        scope_type='namespace',
        namespace=namespace,
        environment=None,
        membership=membership,
        access_profile=profile,
        access_profile_version=1,
        status='active',
    )


def _credential(kind: str, *, profile: str = 'operator', namespace=None):
    namespace = namespace or _namespace()
    owner = SimpleNamespace(id=7, is_active=True, is_admin_level=kind == 'admin_kubeconfig')
    principal = 'service_account' if kind == 'deployer_service_account' else 'user'
    grant = (
        None
        if kind == 'admin_kubeconfig'
        else _grant(profile=profile, principal_type=principal, namespace=namespace)
    )
    return SimpleNamespace(
        id=11,
        public_id='credential-11',
        tenant_id='tenant-a',
        owner_user_id=owner.id,
        owner_user=owner,
        credential_type=kind,
        access_grant=grant,
        anchor_namespace=namespace if kind == 'admin_kubeconfig' else None,
        application_name='payments-api' if kind == 'deployer_service_account' else None,
        status='active',
    )


def _exception(credential, namespace, *, status='active', hours=4):
    now = datetime.now(UTC)
    return SimpleNamespace(
        status=status,
        credential_id=credential.id,
        tenant_namespace_id=namespace.id,
        owner_user_id=credential.owner_user_id,
        valid_from=now - timedelta(minutes=1),
        valid_until=now + timedelta(hours=hours),
        review_due_at=now + timedelta(hours=hours),
    )


def test_production_deployer_is_pipeline_compliant() -> None:
    namespace = _namespace()
    decision = evaluate_production_access(
        _credential('deployer_service_account', profile='deployer', namespace=namespace),
        namespace,
        verb='patch',
    )
    assert decision.allowed is True
    assert decision.compliant is True
    assert decision.authority == 'pipeline'
    assert decision.findings == ()


def test_ordinary_human_mutation_is_denied_without_governed_exception() -> None:
    namespace = _namespace()
    decision = evaluate_production_access(
        _credential('human_service_account', profile='operator', namespace=namespace),
        namespace,
        verb='patch',
    )
    assert decision.allowed is False
    assert 'production_direct_access_denied' in decision.findings


def test_bounded_human_exception_allows_but_remains_governance_finding() -> None:
    namespace = _namespace()
    credential = _credential('human_service_account', profile='operator', namespace=namespace)
    decision = evaluate_production_access(
        credential,
        namespace,
        verb='patch',
        exception=_exception(credential, namespace),
    )
    assert decision.allowed is True
    assert decision.compliant is False
    assert decision.authority == 'exception'
    assert 'production_exception_used' in decision.findings
    assert 'production_human_mutation' in decision.findings


def test_admin_direct_mutation_is_allowed_but_not_pipeline_compliant() -> None:
    namespace = _namespace()
    decision = evaluate_production_access(
        _credential('admin_kubeconfig', namespace=namespace),
        namespace,
        verb='delete',
    )
    assert decision.allowed is True
    assert decision.compliant is False
    assert decision.authority == 'administrator'
    assert 'production_direct_access' in decision.findings


def test_non_production_access_keeps_standard_authorization_path() -> None:
    namespace = _namespace('staging')
    decision = evaluate_production_access(
        _credential('human_service_account', profile='operator', namespace=namespace),
        namespace,
        verb='patch',
    )
    assert decision.allowed is True
    assert decision.compliant is True
    assert decision.authority == 'standard'


def test_expired_exception_fails_closed() -> None:
    namespace = _namespace()
    credential = _credential('human_service_account', profile='operator', namespace=namespace)
    exception = _exception(credential, namespace, hours=-1)
    decision = evaluate_production_access(credential, namespace, verb='patch', exception=exception)
    assert decision.allowed is False
    assert 'production_direct_access_denied' in decision.findings


def test_deployer_requires_exact_namespace_scoped_deployer_contract() -> None:
    namespace = _namespace()
    credential = _credential('deployer_service_account', profile='operator', namespace=namespace)
    with pytest.raises(ValueError, match='Deployer'):
        evaluate_production_access(credential, namespace, verb='patch')
