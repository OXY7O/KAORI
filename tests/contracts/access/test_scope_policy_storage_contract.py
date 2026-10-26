"""Storage contract for approved #724 exact scoped-access policy data model."""

from sqlalchemy import CheckConstraint, ForeignKey

from app.models.scope_access import ScopeAccessPolicy, ScopeAccessPolicyRevision


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
    } <= set(table.columns)
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
