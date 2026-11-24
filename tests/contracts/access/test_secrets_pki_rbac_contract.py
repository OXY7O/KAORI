"""Canonical Secrets & PKI capability access without plaintext or admin escalation."""

from app.access.rbac.defaults import (
    DEFAULT_PERMISSION_DEPENDENCIES,
    DEFAULT_PERMISSIONS,
    DEFAULT_ROLE_PERMISSIONS,
    PERMISSION_MATRIX_DESCRIPTIONS,
    PERMISSION_MODULE_LABELS,
)
from app.platform_operations.jobs.registry import get_job_definition


def test_secrets_pki_is_a_registered_capability_module():
    assert PERMISSION_MODULE_LABELS['secrets_pki'] == 'Secrets & PKI'
    permissions = {name: module for name, module, _action, _description in DEFAULT_PERMISSIONS}
    assert permissions['secrets_pki.view'] == 'secrets_pki'
    assert permissions['secrets_pki.sync'] == 'secrets_pki'
    assert 'reveal' not in permissions
    assert 'plaintext' not in permissions
    assert 'Secret' in PERMISSION_MATRIX_DESCRIPTIONS['secrets_pki.view']


def test_operational_sync_has_safe_read_and_canonical_execution_dependencies():
    assert DEFAULT_PERMISSION_DEPENDENCIES['secrets_pki.sync'] == {
        'secrets_pki.view',
        'jobs.execute',
    }
    job = get_job_definition('secrets_pki.inventory.sync')
    assert job.configure_permission == 'integrations.manage'
    assert job.execute_permission == 'jobs.execute'
    assert job.domain_execute_permission == 'secrets_pki.sync'
    assert job.default_enabled is False


def test_protected_roles_expose_metadata_read_without_auto_granting_plaintext():
    for role in ('viewer', 'operator', 'editor', 'admin', 'auditor'):
        grants = DEFAULT_ROLE_PERMISSIONS[role]
        assert 'secrets_pki.view' in grants
        assert 'secrets_pki.reveal' not in grants

    for role in ('operator', 'editor', 'admin'):
        assert 'secrets_pki.sync' in DEFAULT_ROLE_PERMISSIONS[role]
    for role in ('viewer', 'auditor'):
        assert 'secrets_pki.sync' not in DEFAULT_ROLE_PERMISSIONS[role]


def test_metadata_permission_cannot_configure_provider_by_itself():
    assert 'integrations.manage' not in DEFAULT_PERMISSION_DEPENDENCIES.get('secrets_pki.view', set())
    assert 'integrations.manage' not in DEFAULT_PERMISSION_DEPENDENCIES['secrets_pki.sync']
    assert 'integrations.manage' not in DEFAULT_ROLE_PERMISSIONS['operator']


def test_automation_credential_use_is_explicit_and_has_no_default_grant():
    key = 'secrets_pki.use_automation_credential'
    permissions = {name: (module, action) for name, module, action, _description in DEFAULT_PERMISSIONS}
    assert permissions[key] == ('secrets_pki', 'use_automation_credential')
    assert DEFAULT_PERMISSION_DEPENDENCIES[key] == {'secrets_pki.view', 'inventory.view', 'jobs.execute'}
    assert all(key not in grants for grants in DEFAULT_ROLE_PERMISSIONS.values())
    assert all(key not in dependencies for dependencies in DEFAULT_PERMISSION_DEPENDENCIES.values())
