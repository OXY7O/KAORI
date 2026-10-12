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


def test_devcontainer_workspace_and_each_worker_use_canonical_runtime_url() -> None:
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
        assert section.count('DATABASE_URL: ${DATABASE_URL:?') == 1
        assert 'KAORI_DEV_RUNTIME_DATABASE_URL' not in section
        assert '${POSTGRES_USER' not in section
        assert 'DATABASE_URL: postgresql://${POSTGRES_USER' not in section
        if service == 'workspace':
            assert 'WAIT_FOR_DB: "false"' in section
        else:
            assert 'WAIT_FOR_SCHEMA: "true"' in section
    assert 'db' in services  # override only the bundled DevContainer PostgreSQL authority
    assert 'KAORI_DEV_RUNTIME_DATABASE_URL' not in compose


def test_devcontainer_role_provisioning_is_transactional_and_not_data_destructive() -> None:
    sql = PROVISION.read_text()
    assert 'BEGIN;' in sql and 'COMMIT;' in sql
    assert "current_database() <> 'kaori'" in sql
    assert "application_name" in sql
    assert "kaori-devcontainer-role-provision" in sql
    assert 'CREATE ROLE' not in sql  # only empty-volume provisioning creates principals
    assert "current_user <> 'kaori_migrator'" in sql
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
    assert sql.count('INTO v_role_flags FROM pg_roles') == 1
    assert 'current_role record;' not in sql
    assert 'current_role.' not in sql


def test_post_cutover_initialization_requires_ephemeral_owner_database_url() -> None:
    source = INIT_DB.read_text()
    assert 'KAORI_DEV_RUNTIME_DATABASE_URL' not in source
    assert 'if [ -z "${KAORI_DB_MIGRATION_URL:-}" ]; then' in source
    assert 'KAORI_DB_MIGRATION_URL' in source
    assert 'migration.username == runtime.username' in source
    assert 'migration.host != runtime.host or migration.database != runtime.database' in source
    assert 'SELECT current_user, current_database()' in source
    assert 'actual_owner != expected_owner or actual_database != expected_database' in source
    assert 'PASS: explicit DevContainer PostgreSQL migration identity admitted' in source
    assert 'DATABASE_URL="$KAORI_DB_MIGRATION_URL" flask --app run:app db upgrade' in source
    assert 'Do not run database migrations with kaori_runtime' in source
    assert 'DATABASE_URL="$KAORI_DB_MIGRATION_URL" flask --app run:app seed-rbac' in source


def test_devcontainer_runbook_requires_backup_and_explicit_operator_cutover() -> None:
    example = EXAMPLE.read_text()
    guide = RUNBOOK.read_text()
    assert 'KAORI_DEV_RUNTIME_DATABASE_URL' not in example
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
    assert 'Local operator evidence' in guide


def test_fresh_bootstrap_contract_reuses_owner_only_migration_and_scoped_reset() -> None:
    guide = (ROOT / 'docs' / 'operations' / 'devcontainer-postgres-fresh-bootstrap.md').read_text()
    compose = COMPOSE.read_text()
    init = INIT_DB.read_text()
    assert 'kaori-dev' in guide
    assert 'com.docker.compose.project' in guide
    assert 'com.docker.compose.service' in guide
    assert 'kaori-dev_kaori_postgres_data' in guide
    assert 'docker volume rm "$PG_VOLUME"' in guide
    assert 'kaori_dc rm -f db' in guide
    assert 'down -v' in guide
    assert 'redis' in guide.lower() and 'DBSIZE' in guide
    assert 'KAORI_DB_MIGRATION_URL' in init
    assert 'KAORI_DB_MIGRATION_URL' in guide
    assert 'scripts.devcontainer.initialize_database' in guide
    assert 'KAORI_DEV_RUNTIME_DATABASE_URL' not in init
    assert 'KAORI_DEV_RUNTIME_DATABASE_URL' not in compose
    assert 'DATABASE_URL=postgresql://kaori_runtime:' in EXAMPLE.read_text()


def test_fresh_bootstrap_documents_existing_read_only_first_run_view() -> None:
    guide = (ROOT / 'docs' / 'operations' / 'devcontainer-postgres-fresh-bootstrap.md').read_text()
    assert 'Database Setup Required' in guide
    assert 'HTTP 503' in guide
    assert "to_regclass('public.users') IS NULL" in guide
    assert 'db-role-bootstrap' in guide
    assert 'kaori|t|t|t|t' in guide
    assert 'does not create KAORI application tables' in guide


def test_post_create_guides_transient_owner_bootstrap_for_empty_database() -> None:
    post_create = (ROOT / '.devcontainer' / 'post-create.sh').read_text()
    assert 'docs/operations/devcontainer-postgres-fresh-bootstrap.md' in post_create
    assert 'KAORI: Initialize Fresh Database' in post_create
    assert 'automatically by Compose' in post_create
    assert 'Run "bash scripts/init_db.sh --bootstrap-admin"' not in post_create


def test_devcontainer_first_open_automatically_admits_non_owner_login() -> None:
    import json

    devcontainer = json.loads((ROOT / '.devcontainer' / 'devcontainer.json').read_text())
    compose = COMPOSE.read_text()
    services = _services(compose)
    bootstrap = (ROOT / 'scripts' / 'devcontainer' / 'bootstrap_runtime_role.py').read_text()
    assert 'db-role-bootstrap' in devcontainer['runServices']
    assert 'db-role-bootstrap' in services
    assert 'scripts.devcontainer.bootstrap_runtime_role' in services['db-role-bootstrap']
    assert 'restart: "no"' in services['db-role-bootstrap']
    assert 'condition: service_healthy' in services['db-role-bootstrap']
    assert 'CREATE ROLE' in bootstrap
    assert 'KAORI_DB_MIGRATION_URL' in bootstrap
    assert 'to_regclass(\'public.alembic_version\')' in bootstrap
    assert 'is elevated or cannot log in' in bootstrap
    assert 'must have different secrets' in bootstrap
    assert 'GRANT USAGE ON SCHEMA' in bootstrap
    assert 'flask --app run:app db upgrade' not in bootstrap
    assert 'scripts.init_db' not in bootstrap

    for service in (
        'workspace', 'inventory-worker', 'registry-security-worker',
        'maintenance-worker', 'runtime-worker', 'validation-worker',
        'analytics-worker', 'reports-worker', 'forecasting-worker',
        'resolver-execution-worker', 'resolver-maintenance-worker', 'beat',
    ):
        assert 'db-role-bootstrap:' in services[service]
        assert 'condition: service_completed_successfully' in services[service]


def test_devcontainer_first_database_initialization_is_one_explicit_safe_vscode_task() -> None:
    import json

    tasks = json.loads((ROOT / '.vscode' / 'tasks.json').read_text())['tasks']
    chosen = {task['label']: task['command'] for task in tasks}
    assert chosen['KAORI: Initialize Fresh Database'] == (
        'python -m scripts.devcontainer.initialize_database --bootstrap-admin'
    )
    assert chosen['KAORI: Database Upgrade'] == 'python -m scripts.devcontainer.initialize_database'
    assert chosen['KAORI: Bootstrap Admin'] == chosen['KAORI: Initialize Fresh Database']
    assert chosen['KAORI: Seed RBAC'] == chosen['KAORI: Database Upgrade']
    initializer = (ROOT / 'scripts' / 'devcontainer' / 'initialize_database.py').read_text()
    assert "['sh', 'scripts/init_db.sh'" in initializer
    assert "'KAORI_DB_MIGRATION_URL': migration_url" in initializer
    assert "'PGAPPNAME': 'kaori-devcontainer-role-provision'" in initializer
    assert 'provision_postgres_runtime_role.sql' in initializer
    assert '_require_postgres_ledger_write_once_guards(db.session)' in initializer
    assert 'DATABASE_URL' in initializer
    assert 'flask --app run:app db upgrade' not in chosen.values()
    assert 'kaori_runtime' in initializer


def test_first_run_authentication_setup_uses_one_dev_task_without_changing_production_copy() -> None:
    setup = (ROOT / 'app' / 'templates' / 'access' / 'authentication' / 'setup_required.html').read_text()
    assert '{% if config["APP_ENV"] == "development" %}' in setup
    assert 'python -m scripts.devcontainer.initialize_database --bootstrap-admin' in setup
    assert 'python -m scripts.devcontainer.initialize_database' in setup
    assert '{% else %}' in setup
    assert 'bash scripts/init_db.sh --bootstrap-admin' in setup
    assert 'flask --app run:app db upgrade' in setup
    assert 'flask --app run:app seed-rbac' in setup

def test_three_postgresql_identities_keep_privileged_files_out_of_application_env() -> None:
    compose = COMPOSE.read_text()
    sections = _services(compose)
    example = EXAMPLE.read_text()
    bootstrap = (ROOT / 'scripts/devcontainer/bootstrap_runtime_role.py').read_text()
    initializer = (ROOT / 'scripts/devcontainer/initialize_database.py').read_text()
    assert 'POSTGRES_USER: postgres' in sections['db']
    assert 'POSTGRES_PASSWORD_FILE: /run/secrets/kaori_dev_pg_admin' in sections['db']
    assert 'environment: !override' in sections['db']
    assert 'KAORI_DB_BOOTSTRAP_PASSWORD_FILE: /run/secrets/kaori_dev_pg_admin' in sections['db-role-bootstrap']
    assert 'KAORI_DB_MIGRATOR_PASSWORD_FILE: /run/secrets/kaori_dev_pg_migrator' in sections['db-role-bootstrap']
    assert 'KAORI_DEV_DB_SECRETS_DIR:?' in compose
    for service in (
        'workspace', 'inventory-worker', 'registry-security-worker',
        'maintenance-worker', 'runtime-worker', 'validation-worker',
        'analytics-worker', 'reports-worker', 'forecasting-worker',
        'resolver-execution-worker', 'resolver-maintenance-worker', 'beat',
    ):
        section = sections[service]
        assert 'secrets:' not in section
        assert 'POSTGRES_PASSWORD' not in section
        assert 'KAORI_DB_MIGRATOR_PASSWORD_FILE' not in section
        assert 'KAORI_DB_BOOTSTRAP_PASSWORD_FILE' not in section
    assert 'KAORI_DEV_DB_SECRETS_DIR=' in example
    assert 'POSTGRES_PASSWORD=' not in example
    assert 'POSTGRES_USER=' not in example
    assert 'POSTGRES_DB=' not in example
    assert 'DATABASE_URL=postgresql://kaori_runtime:' in example
    assert "'_MIGRATOR = 'kaori_migrator'" not in bootstrap
    assert "_MIGRATOR = 'kaori_migrator'" in bootstrap
    assert "_RUNTIME = 'kaori_runtime'" in bootstrap
    assert "user='postgres'" in bootstrap
    assert "ALTER DATABASE kaori OWNER TO kaori_migrator" in bootstrap
    assert "ALTER SCHEMA public OWNER TO kaori_migrator" in bootstrap
    assert 'KAORI_DB_MIGRATION_URL' in initializer
    assert 'getpass.getpass' in initializer
    assert "user='kaori_migrator'" in initializer
    assert "['flask', '--app', 'run:app', 'bootstrap-admin']" in initializer


def test_migrator_is_non_superuser_and_app_admin_follows_grant_refresh() -> None:
    init = INIT_DB.read_text()
    initializer = (ROOT / 'scripts/devcontainer/initialize_database.py').read_text()
    sql = PROVISION.read_text()
    assert "expected_owner = 'kaori_migrator'" in init
    assert 'if any(flags)' in init
    assert 'owned != expected_owner' in init
    assert 'DATABASE_URL="$KAORI_DB_MIGRATION_URL" flask --app run:app db upgrade' in init
    assert 'DATABASE_URL="$KAORI_DB_MIGRATION_URL" flask --app run:app seed-rbac' in init
    assert 'trusted non-superuser' in sql.lower()
    assert 'REVOKE ALL PRIVILEGES' in sql
    assert "'PGPASSWORD': migrator_password" in initializer
    assert initializer.index('provision_postgres_runtime_role.sql') < initializer.index(
        "['flask', '--app', 'run:app', 'bootstrap-admin']"
    )
