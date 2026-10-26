"""Regression for PostgreSQL's 63-byte index identifier limit in Vault DDL.

The source-owned migration and ORM declaration must agree on short index names.
The actual PostgreSQL DevContainer upgrade remains a separate UAT gate.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from sqlalchemy.dialects import postgresql

from app.models.secrets_pki import SecretInventoryCollectionState
from app.models.secrets_pki_stored_certificates import PKIStoredCertificateCollectionState

ROOT = Path(__file__).resolve().parents[2]
REVISION_FILES = (
    '20261022_vault_provider.py',
    '20261022_secrets_pki_inventory.py',
    '20261022_vault_pki_evidence.py',
    '20261022_vault_stored_certificates.py',
    '20261022_tls_object_uid_evidence.py',
    '20261022_tls_controller_owner_candidates.py',
    '20261023_scope_policy_storage.py',
    '20261023_notification_channel_retire.py',
)
EXPECTED = (
    (
        SecretInventoryCollectionState,
        '20261022_secrets_pki_inventory.py',
        'ix_spki_inventory_state_instance',
    ),
    (
        PKIStoredCertificateCollectionState,
        '20261022_vault_stored_certificates.py',
        'ix_spki_stored_cert_state_instance',
    ),
)


def _migration_index_operations(path: Path) -> dict[str, set[str]]:
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    operations: dict[str, set[str]] = {'create_index': set(), 'drop_index': set()}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in operations or not node.args:
            continue
        if not isinstance(node.args[0], ast.Constant) or not isinstance(node.args[0].value, str):
            continue
        operations[node.func.attr].add(node.args[0].value)
    return operations


@pytest.mark.parametrize('name', REVISION_FILES)
def test_vault_review_migration_index_names_fit_postgres_limit(name: str) -> None:
    operations = _migration_index_operations(ROOT / 'migrations' / 'versions' / name)
    for operation, identifiers in operations.items():
        assert all(len(identifier.encode('utf-8')) <= 63 for identifier in identifiers), (
            f'{name}: {operation} contains an overlength PostgreSQL identifier'
        )


@pytest.mark.parametrize(('model', 'migration', 'name'), EXPECTED)
def test_source_owned_orm_indexes_match_upgrade_and_downgrade(
    model: type,
    migration: str,
    name: str,
) -> None:
    ops = _migration_index_operations(ROOT / 'migrations' / 'versions' / migration)
    assert name in ops['create_index'] and name in ops['drop_index']
    indexes = {index.name: index for index in model.__table__.indexes}
    assert name in indexes
    index = indexes[name]
    assert [column.name for column in index.columns] == ['integration_instance_id']
    assert len(index.name.encode('utf-8')) <= postgresql.dialect().max_identifier_length
    assert all(
        len(item.name.encode('utf-8')) <= postgresql.dialect().max_identifier_length for item in model.__table__.indexes
    )


def test_previously_failing_long_identifiers_are_not_reintroduced() -> None:
    for migration in (EXPECTED[0][1], EXPECTED[1][1]):
        ops = _migration_index_operations(ROOT / 'migrations' / 'versions' / migration)
        assert not any(len(index.encode('utf-8')) > 63 for names in ops.values() for index in names)
