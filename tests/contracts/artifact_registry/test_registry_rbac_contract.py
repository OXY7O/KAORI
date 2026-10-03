from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]


def _rbac() -> dict:
    return yaml.safe_load(
        (ROOT / 'app/definitions/catalogs/access/rbac/access.yaml').read_text(encoding='utf-8')
    )


def test_artifact_registry_permissions_and_dependencies_are_canonical() -> None:
    document = _rbac()
    modules = {item['key']: item for item in document['control_modules']}
    permissions = {item['key']: item for item in document['permissions']}
    dependencies = document['permission_dependencies']

    assert modules['artifact_registry']['label'] == 'Artifact Registry'
    assert permissions['artifact_registry.view']['module'] == 'artifact_registry'
    assert permissions['artifact_registry.view']['action'] == 'view'
    assert permissions['artifact_registry.sync']['module'] == 'artifact_registry'
    assert permissions['artifact_registry.sync']['action'] == 'sync'
    assert dependencies['artifact_registry.sync'] == ['artifact_registry.view', 'jobs.execute']


def test_artifact_registry_default_role_assignments_follow_read_write_boundary() -> None:
    roles = {
        item['key']: set(item.get('permissions') or ())
        for item in _rbac()['system_roles']
    }

    for role in ('viewer', 'operator', 'editor', 'admin', 'auditor'):
        assert 'artifact_registry.view' in roles[role]

    assert 'artifact_registry.sync' not in roles['viewer']
    assert 'artifact_registry.sync' not in roles['auditor']
    for role in ('operator', 'editor', 'admin'):
        assert 'artifact_registry.sync' in roles[role]
