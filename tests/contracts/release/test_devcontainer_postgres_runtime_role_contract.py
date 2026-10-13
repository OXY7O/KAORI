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


def test_devcontainer_all_runtime_services_use_canonical_non_owner_database_url() -> None:
    compose = COMPOSE.read_text()
    services = _services(compose)
    assert compose.startswith('name: kaori-dev\n')
    assert len(services) >= 14
    expected = {
        'workspace', 'inventory-worker', 'registry-security-worker',
        'maintenance-worker', 'runtime-worker', 'validation-worker',
        'analytics-worker', 'reports-worker', 'forecasting-worker',
        'resolver-execution-worker', 'resolver-maintenance-worker', 'beat',
    }
    assert expected <= services.keys()
    for service in expected:
        section = services[service]
        assert section.count('DATABASE_URL: ${DATABASE_URL:?') == 1
        assert 'KAORI_DEV_RUNTIME_DATABASE_URL' not in section
        assert 'DATABASE_URL: postgresql://${POSTGRES_USER' not in section
        if service == 'workspace':
            assert 'WAIT_FOR_DB: "false"' in section
        else:
            assert 'WAIT_FOR_SCHEMA: "true"' in section
    assert 'db' in services and 'db-bootstrap' in services


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
    assert 'KAORI_DEV_RUNTIME_DATABASE_URL' not in source
    assert 'KAORI_DB_MIGRATION_URL' in source
    assert 'DATABASE_URL="$KAORI_DB_MIGRATION_URL" flask --app run:app db upgrade' in source
    assert 'do not migrate as application runtime' in source
    assert 'Use the controlled db-bootstrap service for grants and application administrator.' in source
    assert 'flask --app run:app bootstrap-admin' not in source
    assert 'flask --app run:app seed-rbac' not in source
    assert 'if [ "${1:-}" != "--schema-only" ]; then' in source


def test_devcontainer_runbook_requires_backup_and_explicit_operator_cutover() -> None:
    example = EXAMPLE.read_text()
    guide = RUNBOOK.read_text()
    assert 'KAORI_DEV_RUNTIME_DATABASE_URL=' not in example
    assert 'DATABASE_URL=postgresql://kaori_runtime:' in example
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


def test_devcontainer_initialization_only_auto_bootstraps_virgin_schema() -> None:
    import json

    config = json.loads((ROOT / '.devcontainer/devcontainer.json').read_text())
    assert config['initializeCommand'][0:3] == ['docker', 'run', '--rm']
    assert 'KAORI_DEV_DOCKER_INIT=1' in config['initializeCommand']
    assert 'db-bootstrap' not in config['runServices']
    assert {'db', 'redis', 'workspace', 'beat', 'db-first-run'} <= set(config['runServices'])
    compose = COMPOSE.read_text()
    db_block = _services(compose)['db']
    operator_block = _services(compose)['db-bootstrap']
    first_run_block = _services(compose)['db-first-run']
    assert 'POSTGRES_PASSWORD: !reset null' not in db_block
    assert 'postgres-bootstrap.env' in db_block
    assert 'postgres-migrate.env' in db_block
    assert 'environment: !override' in db_block
    assert 'POSTGRES_PASSWORD_FILE' not in db_block
    assert '/docker-entrypoint-initdb.d/01-kaori-roles.sh:ro' in db_block
    assert 'profiles: [operator-bootstrap]' in operator_block
    assert 'postgres-migrate.env' in operator_block
    assert 'postgres-bootstrap.env' not in operator_block
    assert 'db-bootstrap' not in _services(compose)['workspace']
    assert 'restart: "no"' in first_run_block
    assert 'scripts/devcontainer/auto-bootstrap-db.sh' in first_run_block
    assert 'postgres-migrate.env' in first_run_block
    assert 'postgres-bootstrap.env' not in first_run_block
    assert 'db-first-run' not in _services(compose)['workspace']


def test_auto_bootstrap_guard_never_migrates_existing_schema() -> None:
    source = (ROOT / 'scripts/devcontainer/auto-bootstrap-db.sh').read_text()
    assert "runtime.username != 'kaori_runtime'" in source
    assert "runtime.host != 'db'" in source
    assert "runtime.database != 'kaori'" in source
    for table in ('pg_catalog.pg_class', 'pg_catalog.pg_proc',
                  'pg_catalog.pg_type', 'pg_catalog.pg_namespace',
                  'pg_catalog.pg_extension'):
        assert table in source
    assert "existing)" in source and "virgin)" in source
    assert "No automatic migration" in source
    assert "exec sh scripts/devcontainer/bootstrap-db.sh" in source
    for forbidden in ("DROP DATABASE", "TRUNCATE", "down --volumes"):
        assert forbidden not in source


def test_devcontainer_role_init_and_secret_preparation_are_non_elevated() -> None:
    init = (ROOT / '.devcontainer/postgres-init/01-kaori-roles.sh').read_text()
    prep = (ROOT / '.devcontainer/prepare-postgres-env.py').read_text()
    assert 'CREATE ROLE kaori_migrator LOGIN NOSUPERUSER' in init
    assert 'CREATE ROLE kaori_runtime LOGIN NOSUPERUSER' in init
    assert 'ALTER DATABASE kaori OWNER TO kaori_migrator' in init
    assert 'ALTER SCHEMA public OWNER TO kaori_migrator' in init
    # PostgreSQL 16 psql must consume role passwords inside its process,
    # not via -v command-line arguments discoverable from process lists.
    assert '\\getenv migrator_password KAORI_MIGRATOR_PASSWORD' in init
    assert '\\getenv runtime_password KAORI_RUNTIME_PASSWORD' in init
    assert '-v "migrator_password=' not in init
    assert '-v "runtime_password=' not in init
    assert "--set=ON_ERROR_STOP=1" in init
    assert 'PASSWORD %L' in init
    assert 'GRANT CONNECT ON DATABASE kaori TO kaori_runtime' in init
    assert 'GRANT USAGE ON SCHEMA public TO kaori_runtime' in init
    assert 'flask' not in init and 'alembic' not in init.lower()
    assert "ROOT = Path('/workspace')" in prep
    assert "SECRET_DIR = ROOT / 'secrets' / 'devcontainer'" in prep
    assert "PG_DATA = Path('/pgdata')" in prep
    assert 'os.O_EXCL' in prep
    assert "'POSTGRES_PASSWORD'" in prep
    assert "PG_DATA = Path('/pgdata')" in prep
    assert "if data_exists and not credentials_exist:" in prep
    assert 'postgres-bootstrap.env.example' in (
        ROOT / '.devcontainer/examples/postgres-bootstrap.env.example'
    ).as_posix()

    assert "drop_value(source, 'KAORI_DEV_RUNTIME_DATABASE_URL')" in prep


def test_devcontainer_operator_bootstrap_orders_schema_grants_and_app_admin() -> None:
    command = (ROOT / 'scripts/devcontainer/bootstrap-db.sh').read_text()
    grants = (ROOT / 'scripts/devcontainer/grant_postgres_runtime.sql').read_text()
    auth = (ROOT / 'app/templates/access/authentication/setup_required.html').read_text()
    assert command.index('scripts/init_db.sh --schema-only') < command.index('grant_postgres_runtime.sql')
    assert command.index('grant_postgres_runtime.sql') < command.index('flask --app run:app bootstrap-admin')
    assert 'PGPASSWORD="$migration_password"' in command
    assert 'unset migration_password KAORI_DB_MIGRATION_URL' in command
    assert "db.engine.url.username == 'kaori_runtime'" in command
    assert 'REVOKE ALL PRIVILEGES ON TABLE public.capsule_handoff_ledger_events' in grants
    assert 'REVOKE ALL PRIVILEGES ON TABLE public.alembic_version' in grants
    assert 'GRANT SELECT ON TABLE public.alembic_version TO kaori_runtime' in grants
    assert "has_table_privilege('kaori_runtime', 'public.alembic_version', 'UPDATE')" in grants
    assert "has_schema_privilege('kaori_runtime', 'public', 'CREATE')" in grants
    assert 'ALTER DEFAULT PRIVILEGES' not in grants
    assert "config.get('APP_ENV') == 'development'" in auth
    assert "config.get('DEBUG', false) and not config.get('TESTING', false)" not in auth
    assert 'docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml run --rm db-bootstrap' in auth


def test_workers_and_beat_wait_for_runtime_immutable_ledger_admission() -> None:
    waiter = (ROOT / 'scripts/wait_for_db.py').read_text()
    assert '_runtime_database_admitted(database_url)' in waiter
    assert "'kaori_migrator', 'MEMBER'" in waiter
    assert "'tr_capsule_ledger_deny_truncate'" in waiter
    assert 'WHERE is_super_admin = TRUE AND is_active = TRUE' in waiter
    assert 'AND deleted_at IS NULL' in waiter
    assert 'account_is_active = TRUE' not in waiter
    user_model = (ROOT / 'app/models/user.py').read_text()
    assert "account_is_active: Mapped[bool] = mapped_column('is_active'" in user_model
    assert "'public.capsule_handoff_ledger_events', 'UPDATE'" in waiter
    assert "NOT has_table_privilege(current_user, 'public.alembic_version', 'UPDATE')" in waiter
    assert 'if current_heads == expected_heads:' in waiter


def test_devcontainer_app_environment_template_documents_real_three_file_ownership() -> None:
    example = EXAMPLE.read_text()
    verifier = (ROOT / 'scripts/verify_environment_contract.py').read_text()
    operations = (ROOT / 'docs/operations/devcontainer-postgres-first-run.md').read_text()
    env_guide = (ROOT / 'docs/deployment/ENVIRONMENT_CONFIGURATION.md').read_text()
    host = (ROOT / '.devcontainer/prepare-postgres-env.py').read_text()

    entries = {
        line.split('=', 1)[0] for line in example.splitlines()
        if line and not line.lstrip().startswith('#') and '=' in line
    }
    assert {'APP_ENV', 'POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_PORT', 'DATABASE_URL'} <= entries
    assert 'POSTGRES_USER=postgres' in example
    assert 'DATABASE_URL=postgresql://kaori_runtime:' in example
    for elevated in (
        'POSTGRES_PASSWORD', 'KAORI_MIGRATOR_PASSWORD',
        'KAORI_RUNTIME_PASSWORD', 'KAORI_DB_MIGRATION_URL',
        'PGPASSWORD', 'POSTGRES_PASSWORD_FILE',
        'KAORI_DEV_RUNTIME_DATABASE_URL',
    ):
        assert elevated not in entries
    assert "DEVCONTAINER_BOOTSTRAP_SECRET_KEYS = {'POSTGRES_PASSWORD'}" in verifier
    assert 'leaking_bootstrap' in verifier

    assert 'secrets/devcontainer/postgres-bootstrap.env' in env_guide
    assert 'secrets/devcontainer/postgres-migrate.env' in env_guide
    assert 'postgres-bootstrap.env' in operations
    assert 'postgres-migrate.env' in operations
    assert '## Windows PowerShell: WSL/OneDrive secret permission-denied recovery' in operations
    assert '[System.IO.File]::OpenRead(' in operations
    assert 'config --quiet' in operations
    assert 'run --rm db-bootstrap sh scripts/devcontainer/bootstrap-db.sh --upgrade-only' in operations
    assert 'PASS: trusted, non-superuser migration identity admitted' in operations
    assert 'Never use `flask db upgrade` with the regular' in operations
    assert "drop_value(source, 'POSTGRES_PASSWORD')" in host
    assert "drop_value(source, 'KAORI_DEV_RUNTIME_DATABASE_URL')" in host
    assert "values.get('APP_ENV', 'development') != 'development'" in host
    assert "'KAORI_MIGRATOR_PASSWORD', 'KAORI_RUNTIME_PASSWORD'" in host
