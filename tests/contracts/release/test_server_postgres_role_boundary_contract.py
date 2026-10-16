"""Source-level regression for bundled server PostgreSQL role separation (#1439)."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def service_block(compose: str, name: str) -> str:
    start = compose.index(f'  {name}:\n')
    remaining = compose[start + len(f'  {name}:\n'):]
    next_service = re.search(r'(?m)^  [a-z][a-z0-9_-]*:$', remaining)
    return remaining if next_service is None else remaining[:next_service.start()]


def test_runtime_secrets_never_include_postgres_admin_or_migrator() -> None:
    compose = source('deploy/server/compose.server.yml')
    postgres = service_block(compose, 'postgres')
    provisioner = service_block(compose, 'db-provision')
    migrator = service_block(compose, 'migrate')
    assert 'KAORI_POSTGRES_ADMIN_ENV_FILE' in postgres
    assert 'KAORI_SECRETS_ENV_FILE' not in postgres
    assert 'KAORI_POSTGRES_ADMIN_ENV_FILE' in provisioner
    assert 'KAORI_POSTGRES_MIGRATION_ENV_FILE' in provisioner
    assert 'KAORI_POSTGRES_MIGRATION_ENV_FILE' in migrator
    assert 'KAORI_POSTGRES_ADMIN_ENV_FILE' not in migrator
    assert 'server_migrate_db.sh' in migrator
    assert 'POSTGRES_PASSWORD=' not in source('deploy/env/secrets.env.example')
    assert 'DATABASE_URL=postgresql://kaori_runtime:' in source('deploy/env/secrets.env.example')
    for service in (
        'web', 'worker', 'registry-security-worker', 'maintenance-worker',
        'runtime-worker', 'validation-worker', 'analytics-worker', 'reports-worker',
        'forecasting-worker', 'resolver-execution-worker',
        'resolver-maintenance-worker', 'beat',
    ):
        block = service_block(compose, service)
        assert 'KAORI_SECRETS_ENV_FILE' in block, service
        assert 'KAORI_POSTGRES_ADMIN_ENV_FILE' not in block, service
        assert 'KAORI_POSTGRES_MIGRATION_ENV_FILE' not in block, service
        assert 'WAIT_FOR_SCHEMA: "true"' in block, service


def test_first_run_only_when_verifiably_empty() -> None:
    deploy = source('deploy/server/deploy.sh')
    guard = source('scripts/server_database_boundary.py')
    migration = source('scripts/server_migrate_db.sh')
    assert 'KAORI_BUNDLED_FRESH_BOOTSTRAP' in deploy
    assert 'run --rm --pull never db-provision' in deploy
    assert 'run --rm --pull never db-bootstrap-admin' in deploy
    assert deploy.index('db-provision') < deploy.index('run --rm --pull never migrate')
    assert deploy.index('run --rm --pull never migrate') < deploy.index('db-bootstrap-admin')
    assert deploy.index('db-bootstrap-admin') < deploy.index('run --rm --pull never db-verify')
    assert deploy.index('run --rm --pull never db-verify') < deploy.index('Starting KAORI application services')
    assert 'KAORI_BUNDLED_FRESH_BOOTSTRAP' in guard
    assert 'Other PostgreSQL sessions remain' in guard
    assert 'Unexpected application schema' in guard
    assert 'Existing schema object or extension' in guard
    assert 'CREATE ROLE' in guard
    assert 'DROP ROLE' not in guard
    assert 'DROP DATABASE' not in guard
    assert 'REASSIGN OWNED' not in guard
    assert 'scripts/server_database_boundary.py migrator' in migration
    assert 'DATABASE_URL="$KAORI_DB_MIGRATION_URL" flask --app run:app db upgrade' in migration
    assert 'scripts/server_database_boundary.py grant' in migration


def test_acl_restore_and_running_services_are_guarded() -> None:
    guard = source('scripts/server_database_boundary.py')
    restore = source('deploy/server/restore.sh')
    verify = source('deploy/server/verify.sh')
    bootstrap = source('deploy/server/bootstrap-host.sh')
    wait = source('scripts/wait_for_db.py')
    assert "pg_has_role('kaori_runtime', 'kaori_migrator', 'MEMBER')" in guard
    assert 'tr_capsule_ledger_deny_truncate' in guard
    assert 'actual_heads != expected_heads' in guard
    assert 'GRANT SELECT, INSERT ON TABLE public.capsule_handoff_ledger_events' in guard
    assert 'REVOKE ALL PRIVILEGES ON TABLE public.alembic_version' in guard
    assert '--role=kaori_migrator' in restore
    assert 'server_database_boundary.py grant' in restore
    assert 'server_database_boundary.py runtime' in verify
    assert 'postgres-admin.env' in bootstrap
    assert 'postgres-migrate.env' in bootstrap
    assert "{'development', 'production'}" in wait


def test_first_run_preserves_bundled_data_volume() -> None:
    compose = source('deploy/server/compose.server.yml')
    deploy = source('deploy/server/deploy.sh')
    assert 'kaori-vps-postgres-data' in compose
    assert '/var/lib/postgresql/data' in compose
    assert 'down -v' not in deploy


def test_existing_schema_cutover_is_bounded_and_requires_proven_backup() -> None:
    deploy = source('deploy/server/deploy.sh')
    guard = source('scripts/server_database_boundary.py')
    compose = source('deploy/server/compose.server.yml')
    backup = source('deploy/server/backup.sh')
    env = source('deploy/env/deploy.env.example')
    assert 'KAORI_BUNDLED_SCHEMA_CUTOVER=false' in env
    assert 'KAORI_BUNDLED_SCHEMA_CUTOVER' in compose
    assert 'KAORI_BUNDLED_SCHEMA_CUTOVER' in guard
    assert 'pg_restore --list' in deploy
    assert 'Schema revision differs from candidate release' in deploy
    assert 'candidate_heads=' in deploy and 'existing_heads=' in deploy
    # On an existing legacy schema with cutover disabled, reject the release
    # before backing up, stopping writers, or invoking migrator-only Alembic.
    assert 'current_db_owner=' in deploy
    assert "current_db_owner\" == 'kaori_migrator'" in deploy
    assert 'Existing PostgreSQL is not owned by kaori_migrator' in deploy
    assert deploy.index('current_db_owner=') < deploy.index('candidate_heads=')
    assert deploy.index('current_db_owner=') < deploy.index('backup_path="$(bash "$SCRIPT_DIR/backup.sh")"')
    assert deploy.index('candidate_heads=') < deploy.index('stop "${application_services[@]}"')
    assert 'backup_path.roles.sql' in deploy
    assert 'backup_path.schema.sql' in deploy
    assert 'server_database_boundary.py cutover' in deploy
    assert 'stop "${application_services[@]}"' in deploy
    assert deploy.index('stop "${application_services[@]}"') < deploy.index('backup_path="$(bash "$SCRIPT_DIR/backup.sh")"')
    assert deploy.index('backup_path="$(bash "$SCRIPT_DIR/backup.sh")"') < deploy.index("server_database_boundary.py cutover")
    assert 'pg_dumpall' in backup
    assert '--globals-only' in backup
    assert 'ALTER TABLE public.{} OWNER TO kaori_migrator' in guard
    assert 'ALTER SEQUENCE public.{} OWNER TO kaori_migrator' in guard
    assert 'REASSIGN OWNED' not in guard
    assert 'DROP DATABASE' not in guard
    assert 'DROP ROLE' not in guard
    assert 'Application sessions still connected' in guard
    assert 'transaction will roll back' in guard
