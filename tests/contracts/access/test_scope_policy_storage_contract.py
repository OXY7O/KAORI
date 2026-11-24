"""Storage contract for approved #724 exact scoped-access policy data model."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import CheckConstraint, ForeignKey, create_engine
from sqlalchemy.exc import IntegrityError

from app.models.scope_access import AutomationCredentialScopeTarget, ScopeAccessPolicy, ScopeAccessPolicyRevision


def test_policy_identity_is_exact_and_existing_authorities_are_referenced():
    table = ScopeAccessPolicy.__table__
    assert table.name == 'access_scope_policies'
    assert {
        'principal_user_id',
        'permission_key',
        'integration_instance_id',
        'scope_level',
        'provider_namespace',
        'mount',
        'current_revision',
    } <= set(table.columns.keys())
    foreign_targets = {fk.target_fullname for col in table.columns for fk in col.foreign_keys}
    assert 'users.id' in foreign_targets
    assert 'permissions.key' in foreign_targets
    assert 'integration_instances.id' in foreign_targets
    checks = {c.name: str(c.sqltext) for c in table.constraints if isinstance(c, CheckConstraint)}
    assert 'ck_access_scope_policy_exact_target' in checks
    assert "mount NOT LIKE '%*%'" in checks['ck_access_scope_policy_exact_target']
    assert "scope_level = 'instance'" in checks['ck_access_scope_policy_exact_target']
    assert "scope_level = 'vault_mount'" in checks['ck_access_scope_policy_exact_target']


def test_revisions_are_approval_gated_even_before_service_activation():
    table = ScopeAccessPolicyRevision.__table__
    checks = {c.name: str(c.sqltext) for c in table.constraints if isinstance(c, CheckConstraint)}
    assert 'ck_access_scope_revision_approved' in checks
    assert 'approved_by_user_id <> requested_by_user_id' in checks['ck_access_scope_revision_approved']
    assert 'ck_access_scope_revision_window' in checks
    assert 'ck_access_scope_revision_state' in checks
    assert 'policy_id' in table.columns
    assert table.c.policy_id.foreign_keys
    assert all(isinstance(fk, ForeignKey) for fk in table.c.policy_id.foreign_keys)
    assert not hasattr(ScopeAccessPolicy, 'secret_value')


def test_storage_contract_never_introduces_implicit_grant_or_runtime_evaluator():
    assert not hasattr(ScopeAccessPolicy, 'has_permission')
    assert not hasattr(ScopeAccessPolicy, 'evaluate')
    assert ScopeAccessPolicyRevision.__table__.c.lifecycle_status.default.arg == 'draft'


def test_credential_selector_is_bound_to_canonical_policy_and_resource_identity():
    table = AutomationCredentialScopeTarget.__table__
    assert list(table.primary_key.columns.keys()) == ['policy_id']
    assert {fk.target_fullname for column in table.columns for fk in column.foreign_keys} == {
        'access_scope_policies.id',
        'integration_instances.id',
        'automation_inventory_assignments.id',
        'automation_host_assets.id',
        'secrets_pki_secret_identities.id',
        'secrets_pki_secret_representations.id',
    }
    assert all(not column.nullable for column in table.columns)
    assert {
        'secret_version', 'host_revision', 'reference_fingerprint', 'source_revision', 'profile_key', 'operation_key'
    } <= set(table.columns.keys())
    assert not hasattr(AutomationCredentialScopeTarget, 'secret_value')


@pytest.mark.parametrize(
    ('level', 'permission', 'namespace', 'mount'),
    [
        ('vault_mount', 'secrets_pki.use_automation_credential', '', 'kv'),
        ('instance', 'secrets_pki.use_automation_credential', None, None),
        ('automation_credential', 'secrets_pki.view', '', 'kv'),
        ('automation_credential', 'secrets_pki.use_automation_credential', None, 'kv'),
        ('automation_credential', 'secrets_pki.use_automation_credential', '', '*'),
    ],
)
def test_credential_scope_cannot_inherit_metadata_scope(level, permission, namespace, mount):
    # Isolated CHECK-constraint test; no FK enforcement or runtime grants implied.
    engine = create_engine('sqlite://')
    table = ScopeAccessPolicy.__table__
    try:
        with engine.begin() as connection:
            table.create(connection)
            with pytest.raises(IntegrityError):
                connection.execute(
                    table.insert().values(
                        id='fixture-policy',
                        principal_user_id=1,
                        permission_key=permission,
                        integration_instance_id=1,
                        scope_level=level,
                        provider_namespace=namespace,
                        mount=mount,
                        current_revision=1,
                        created_at=datetime.now(UTC),
                        updated_at=datetime.now(UTC),
                    )
                )
    finally:
        engine.dispose()
