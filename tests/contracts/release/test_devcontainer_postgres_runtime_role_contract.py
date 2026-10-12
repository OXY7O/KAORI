"""#1405 DevContainer PostgreSQL least-privilege runtime source contracts.

Source-only regression (not executed while CI/CD remains HOLD).
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
COMPOSE = ROOT / '.devcontainer' / 'compose.devcontainer.yml'
PROVISION = ROOT / 'scripts' / 'devcontainer' / 'provision_postgres_runtime_role.sql'
INIT_DB = ROOT / 'scripts' / 'init_db.sh'
EXAMPLE = ROOT / '.env.example'
RUNBOOK = ROOT / 'docs' / 'operations' / 'devcontainer-postgres-runtime-role.md'


def _services(compose: str) -> dict[str, str]:
    import re

    values: dict[str, str] = {}
    for section in re.split(r'(?=^  [a-z0-9-]+:\n)', compose, flags=re.MULTILINE):
        matched = re.match(r'^  ([a-z0-9-]+):\n', section)
        if matched:
            values[matched.group(1)] = section
    return values


def test_devcontainer_workspace_and_each_worker_use_single_optional_runtime_url() -> None:
    compose = COMPOSE.read_text()
    services = _services(compose)
    assert compose.startswith('name: kaori-dev\n')
    assert len(services) >= 12
    expected = {
        'workspace', 'inventory-worker', 'registry-security-worker',
        'maintenance-worker', 'runtime-worker', 'validation-worker',
        'analytics-worker', 'reports-worker', 'forecasting-worker',
        'resolver-execution-worker', 'resolver-maintenance-worker', 'beat',
    }
    assert expected <= services.keys()
    for service in expected:
        section = services[service]
        assert section.count('KAORI_DEV_RUNTIME_DATABASE_URL:-postgresql://') == 1
        assert 'DATABASE_URL: postgresql://${POSTGRES_USER' not in section
        if service == 'workspace':
            assert 'WAIT_FOR_DB: "false"' in section
        else:
            assert 'WAIT_FOR_SCHEMA: "true"' in section
    assert 'db' not in services  # infra DB is supplied by canonical compose.yml


def test_devcontainer_role_provisioning_is_transactional_and_not_data_destructive() -> None:
    sql = PROVISION.read_text()
    assert 'BEGIN;' in sql and 'COMMIT;' in sql
    assert "current_database() <> 'kaori'" in sql
    assert "application_name" in sql
    assert "kaori-devcontainer-role-provision" in sql
    assert 'CREATE ROLE kaori_runtime' in sql
    assert 'NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE' in sql
    assert 'GRANT SELECT, INSERT, UPDATE, DELETE' in sql
    assert 'ON ALL TABLES IN SCHEMA public' in sql
    assert 'ON ALL SEQUENCES IN SCHEMA public' in sql
    assert 'REVOKE ALL PRIVILEGES' in sql
    assert 'ON TABLE public.capsule_handoff_ledger_events TO kaori_runtime' in sql
    assert 'GRANT SELECT, INSERT' in sql
    for denied in ('UPDATE', 'DELETE', 'TRUNCATE'):
        assert (
            "has_table_privilege('kaori_runtime', "
            "'public.capsule_handoff_ledger_events', "
            f"'{denied}')"
        ) in sql
    assert "has_schema_privilege('kaori_runtime', 'public', 'CREATE')" in sql
    assert 'ALTER DEFAULT PRIVILEGES' not in '\n'.join(
        line for line in sql.splitlines() if not line.lstrip().startswith('--')
    )
    for statement in ('DROP DATABASE', 'DROP TABLE', 'TRUNCATE TABLE', 'DELETE FROM'):
        assert statement not in '\n'.join(
            line for line in sql.splitlines() if not line.lstrip().startswith('--')
        )


def test_postgresql_provisioning_role_record_does_not_shadow_current_role() -> None:
    sql = PROVISION.read_text()
    assert 'v_role_flags record;' in sql
    assert sql.count('INTO v_role_flags FROM pg_roles') == 2
    assert 'current_role record;' not in sql
    assert 'current_role.' not in sql


def test_post_cutover_initialization_requires_ephemeral_owner_database_url() -> None:
    source = INIT_DB.read_text()
    assert 'KAORI_DEV_RUNTIME_DATABASE_URL' in source
    assert 'KAORI_DB_MIGRATION_URL' in source
    assert 'DATABASE_URL="$KAORI_DB_MIGRATION_URL" flask --app run:app db upgrade' in source
    assert 'Do not run database migrations with kaori_runtime' in source
    assert 'DATABASE_URL="$KAORI_DB_MIGRATION_URL" flask --app run:app seed-rbac' in source


def test_devcontainer_runbook_requires_backup_and_explicit_operator_cutover() -> None:
    example = EXAMPLE.read_text()
    guide = RUNBOOK.read_text()
    assert 'KAORI_DEV_RUNTIME_DATABASE_URL=' in example
    assert 'KAORI_DB_MIGRATION_URL' in example
    assert 'pg_dump' in guide and 'pg_restore --list' in guide
    assert r'\password kaori_runtime' in guide
    assert 'ALTER ROLE kaori_runtime LOGIN;' in guide
    assert 'postgresql://kaori_runtime:' in guide
    assert 'no blanket ALTER DEFAULT PRIVILEGES' in guide
    assert 'read-only' in guide
    assert 'down --volumes' in guide
    assert 'compromised' in guide.lower()
    assert 'No migration, provisioning SQL or runtime cutover was executed' in guide
