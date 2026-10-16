"""Bundled KAORI PostgreSQL migrator and runtime admission (Issue #1439).

First-run provisioning is permitted only for a provably empty bundled database.
No existing schema/data is reset; legacy ownership always fails closed.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import sys
from contextlib import closing
from pathlib import Path
from urllib.parse import unquote, urlsplit

import psycopg2
from alembic.config import Config
from alembic.script import ScriptDirectory
from psycopg2 import sql


# The four PostgreSQL trigger functions introduced by the admitted Capsule
# migrations at 20261013_limit_exposure. Never transfer unrelated functions.
_CAPSULE_TRIGGER_FUNCTIONS = frozenset({
    'kaori_capsule_handoff_ledger_insert_guard',
    'kaori_capsule_handoff_ledger_deny_change',
    'kaori_capsule_proof_deny_change',
    'kaori_capsule_handback_audit_deny_change',
})


def fail(message: str) -> None:
    raise RuntimeError(message)


def parsed_url(name: str, user: str) -> str:
    raw = os.getenv(name, '').strip()
    if not raw:
        fail(f'{name} is missing')
    try:
        value = urlsplit(raw)
        if value.scheme not in {'postgres', 'postgresql'}:
            fail(f'{name} is not PostgreSQL')
        if unquote(value.username or '') != user or not value.hostname:
            fail(f'{name} has wrong database identity')
        if unquote(value.path.lstrip('/')) != 'kaori':
            fail(f'{name} targets unexpected database')
        if not value.password:
            fail(f'{name} has no password')
        _ = value.port
    except ValueError:
        fail(f'{name} URL is invalid')
    return raw


def ensure_same_target(runtime_url: str, migration_url: str) -> None:
    runtime = urlsplit(runtime_url)
    migration = urlsplit(migration_url)
    if (runtime.hostname, runtime.port or 5432, runtime.path) != (
        migration.hostname, migration.port or 5432, migration.path
    ):
        fail('Runtime and migration URLs target different PostgreSQL databases')


def scalar(cursor, statement: str) -> object:
    cursor.execute(statement)
    row = cursor.fetchone()
    if row is None:
        fail('PostgreSQL admission query returned no evidence')
    return row[0]


def role_guard(cursor, expected_user: str) -> None:
    cursor.execute(
        """
        SELECT current_user, current_database(), rolsuper, rolcreatedb,
               rolcreaterole, rolreplication, rolbypassrls
          FROM pg_roles WHERE rolname = current_user
        """
    )
    row = cursor.fetchone()
    if not row or row[0] != expected_user or row[1] != 'kaori' or any(row[2:]):
        fail(f'{expected_user} is not a restricted identity on kaori')
    if scalar(cursor, 'SELECT pg_is_in_recovery()'):
        fail('Refusing role admission on a PostgreSQL recovery replica')
    if scalar(
        cursor,
        "SELECT pg_has_role('kaori_runtime', 'kaori_migrator', 'MEMBER')",
    ):
        fail('Runtime is a member of the migration owner')
    if scalar(
        cursor,
        """
        SELECT EXISTS (
          SELECT 1 FROM pg_roles r
           WHERE pg_has_role('kaori_runtime', r.oid, 'MEMBER')
             AND (r.rolsuper OR r.rolcreatedb OR r.rolcreaterole
               OR r.rolreplication OR r.rolbypassrls)
        )
        """,
    ):
        fail('Runtime is a member of an elevated PostgreSQL role')


def migrator_guard(cursor) -> None:
    role_guard(cursor, 'kaori_migrator')
    if scalar(
        cursor,
        """
        SELECT pg_get_userbyid(datdba) = 'kaori_migrator'
          FROM pg_database WHERE datname = current_database()
        """,
    ) is not True:
        fail('Database owner is not kaori_migrator; existing-state cutover required')
    if scalar(
        cursor,
        """
        SELECT pg_get_userbyid(nspowner) = 'kaori_migrator'
          FROM pg_namespace WHERE nspname = 'public'
        """,
    ) is not True:
        fail('public schema owner is not kaori_migrator')
    if scalar(cursor, "SELECT has_schema_privilege(current_user, 'public', 'CREATE')") is not True:
        fail('Migrator lacks schema DDL authority')
    if scalar(
        cursor,
        """
        SELECT COUNT(*) FROM pg_class c
         WHERE c.relnamespace = 'public'::regnamespace
           AND c.relkind IN ('r', 'p', 'v', 'm', 'S', 'f')
           AND pg_get_userbyid(c.relowner) <> 'kaori_migrator'
        """,
    ):
        fail('Some public schema relations are owned by a legacy principal')
    if scalar(
        cursor,
        """
        SELECT COUNT(*) FROM pg_proc p
         WHERE p.pronamespace = 'public'::regnamespace
           AND pg_get_userbyid(p.proowner) <> 'kaori_migrator'
        """,
    ):
        fail('Some public schema functions are owned by a legacy principal')
    if scalar(cursor, "SELECT has_schema_privilege('kaori_runtime', 'public', 'CREATE')"):
        fail('Runtime retains public schema CREATE privilege')
    if scalar(
        cursor,
        """
        SELECT has_database_privilege('kaori_runtime', current_database(), 'CREATE')
            OR has_database_privilege('kaori_runtime', current_database(), 'TEMPORARY')
        """,
    ):
        fail('Runtime has database CREATE or TEMPORARY privilege')


def runtime_guard(cursor) -> None:
    role_guard(cursor, 'kaori_runtime')
    for name in ('KAORI_DB_MIGRATION_URL', 'POSTGRES_PASSWORD', 'KAORI_MIGRATOR_PASSWORD'):
        if name in os.environ:
            fail(f'Privileged credential variable leaked to runtime: {name}')
    if scalar(
        cursor,
        """
        SELECT pg_get_userbyid(datdba) = 'kaori_runtime'
          FROM pg_database WHERE datname = current_database()
        """,
    ):
        fail('Runtime owns its database')
    if scalar(cursor, "SELECT has_schema_privilege(current_user, 'public', 'CREATE')"):
        fail('Runtime may create objects in public schema')
    if scalar(
        cursor,
        """
        SELECT has_database_privilege(current_user, current_database(), 'CREATE')
            OR has_database_privilege(current_user, current_database(), 'TEMPORARY')
        """,
    ):
        fail('Runtime retains database CREATE or TEMPORARY privilege')
    for table in (
        'alembic_version', 'audit_events', 'capsule_handoff_ledger_events',
        'capsule_handoff_audit_batches', 'capsule_handoff_resource_consent_records',
        'users',
    ):
        cursor.execute('SELECT to_regclass(%s)', (f'public.{table}',))
        if cursor.fetchone()[0] is None:
            fail(f'Required migrated object missing: {table}')
    if not scalar(
        cursor,
        """
        SELECT has_table_privilege(current_user, 'public.capsule_handoff_ledger_events', 'SELECT')
           AND has_table_privilege(current_user, 'public.capsule_handoff_ledger_events', 'INSERT')
           AND NOT has_table_privilege(current_user, 'public.capsule_handoff_ledger_events', 'UPDATE')
           AND NOT has_table_privilege(current_user, 'public.capsule_handoff_ledger_events', 'DELETE')
           AND NOT has_table_privilege(current_user, 'public.capsule_handoff_ledger_events', 'TRUNCATE')
           AND has_table_privilege(current_user, 'public.alembic_version', 'SELECT')
           AND NOT has_table_privilege(current_user, 'public.alembic_version', 'INSERT')
           AND NOT has_table_privilege(current_user, 'public.alembic_version', 'UPDATE')
           AND NOT has_table_privilege(current_user, 'public.alembic_version', 'DELETE')
           AND NOT has_table_privilege(current_user, 'public.alembic_version', 'TRUNCATE')
           AND NOT has_table_privilege(current_user, 'public.audit_events', 'TRUNCATE')
           AND has_table_privilege(current_user, 'public.capsule_handoff_audit_batches', 'INSERT')
           AND NOT has_table_privilege(current_user, 'public.capsule_handoff_audit_batches', 'UPDATE')
           AND NOT has_table_privilege(current_user, 'public.capsule_handoff_audit_batches', 'DELETE')
           AND NOT has_table_privilege(current_user, 'public.capsule_handoff_audit_batches', 'TRUNCATE')
           AND has_table_privilege(current_user, 'public.capsule_handoff_resource_consent_records', 'INSERT')
           AND NOT has_table_privilege(current_user, 'public.capsule_handoff_resource_consent_records', 'UPDATE')
           AND NOT has_table_privilege(current_user, 'public.capsule_handoff_resource_consent_records', 'DELETE')
           AND NOT has_table_privilege(current_user, 'public.capsule_handoff_resource_consent_records', 'TRUNCATE')
        """,
    ):
        fail('Runtime effective table privileges violate immutable evidence contract')
    # Check the exact release's Alembic heads, not merely table existence.
    migration_dir = Path(__file__).resolve().parents[1] / 'migrations'
    config = Config(str(migration_dir / 'alembic.ini'))
    config.set_main_option('script_location', str(migration_dir))
    expected_heads = frozenset(ScriptDirectory.from_config(config).get_heads())
    cursor.execute('SELECT version_num FROM public.alembic_version')
    actual_heads = frozenset(row[0] for row in cursor.fetchall())
    if not expected_heads or actual_heads != expected_heads:
        fail('PostgreSQL Alembic heads do not match the immutable release')

    if not scalar(
        cursor,
        """
        SELECT COUNT(*) = 4 FROM pg_trigger t
         WHERE t.tgrelid = 'public.capsule_handoff_ledger_events'::regclass
           AND t.tgname IN (
             'tr_capsule_ledger_guard_insert', 'tr_capsule_ledger_deny_update',
             'tr_capsule_ledger_deny_delete', 'tr_capsule_ledger_deny_truncate'
           )
           AND t.tgenabled IN ('O', 'A')
        """,
    ):
        fail('Immutable Capsule ledger is missing active write-once triggers')
    if not scalar(
        cursor,
        """
        SELECT current_setting('fsync') = 'on'
           AND current_setting('synchronous_commit') <> 'off'
           AND current_setting('session_replication_role') = 'origin'
        """,
    ):
        fail('PostgreSQL WAL or trigger execution is not durable')
    if not scalar(
        cursor,
        """
        SELECT EXISTS (
          SELECT 1 FROM public.users
           WHERE is_super_admin = TRUE AND is_active = TRUE AND deleted_at IS NULL
        )
        """,
    ):
        fail('First active super administrator has not been initialized')



def scram_password_verifier(password: str) -> str:
    """Send salted SCRAM verifier, never plaintext role password in DDL."""
    salt = os.urandom(16)
    iterations = 4096
    salted = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
    client_key = hmac.new(salted, b'Client Key', hashlib.sha256).digest()
    stored_key = hashlib.sha256(client_key).digest()
    server_key = hmac.new(salted, b'Server Key', hashlib.sha256).digest()
    salt_b64 = base64.b64encode(salt).decode('ascii')
    stored_b64 = base64.b64encode(stored_key).decode('ascii')
    server_b64 = base64.b64encode(server_key).decode('ascii')
    return f'SCRAM-SHA-256${iterations}:{salt_b64}${stored_b64}:{server_b64}'

def fresh_bundled_bootstrap(runtime_url: str, migration_url: str) -> None:
    """Create the two non-elevated identities only on a genuinely virgin DB."""
    admin_user = os.getenv('POSTGRES_USER', '').strip()
    admin_password = os.getenv('POSTGRES_PASSWORD', '')
    if not admin_user or not admin_password or admin_user in {'kaori_runtime', 'kaori_migrator'}:
        fail('Bundled bootstrap administrator credential is missing or unsafe')
    # This protected one-shot container is the ONLY application image container
    # allowed to receive the PostgreSQL admin credential.
    target = urlsplit(migration_url)
    if target.hostname != 'postgres' or (target.port or 5432) != 5432:
        fail('Fresh bundled bootstrap accepts only internal postgres:5432')
    if os.getenv('KAORI_BUNDLED_FRESH_BOOTSTRAP') != 'true':
        fail('Operator has not enabled the bounded, empty-database bootstrap')
    with closing(
        psycopg2.connect(
            dbname='kaori',
            user=admin_user,
            password=admin_password,
            host='postgres',
            port=5432,
            connect_timeout=5,
        )
    ) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT current_user, current_database(), r.rolsuper
                FROM pg_roles r WHERE r.rolname = current_user
                """
            )
            row = cursor.fetchone()
            if not row or row != (admin_user, 'kaori', True):
                fail('Bundled first-run provisioning requires the expected database superuser')
            if scalar(cursor, 'SELECT pg_is_in_recovery()'):
                fail('Cannot bootstrap a replica')
            # Guard arbitrary user schemas, ALL user relations and functions, and
            # unexpected extensions, not just pg_tables in public.
            if scalar(
                cursor,
                """
                SELECT COUNT(*) FROM pg_namespace n
                 WHERE n.nspname NOT IN ('public', 'information_schema')
                   AND LEFT(n.nspname, 3) <> 'pg_'
                """,
            ):
                fail('Unexpected application schema: database is not virgin')
            if scalar(
                cursor,
                """
                SELECT COUNT(*) FROM pg_class c
                 JOIN pg_namespace n ON n.oid = c.relnamespace
                 WHERE n.nspname = 'public'
                """,
            ) or scalar(
                cursor,
                """
                SELECT COUNT(*) FROM pg_proc p
                 WHERE p.pronamespace = 'public'::regnamespace
                """,
            ) or scalar(
                cursor,
                """
                SELECT COUNT(*) FROM pg_extension
                 WHERE extname <> 'plpgsql'
                """,
            ):
                fail('Existing schema object or extension: refusing first-run provisioning')
            # Active/idle clients (including web or workers) would race DDL.
            if scalar(
                cursor,
                """
                SELECT COUNT(*) FROM pg_stat_activity
                WHERE datname = current_database() AND pid <> pg_backend_pid()
                """,
            ):
                fail('Other PostgreSQL sessions remain; stop application services before bootstrap')
            cursor.execute(
                "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = current_database()"
            )
            db_owner = cursor.fetchone()[0]
            if db_owner not in {admin_user, 'kaori_migrator'}:
                fail('Unexpected database owner: cannot infer a safe cutover')
            cursor.execute(
                "SELECT rolname FROM pg_roles WHERE rolname IN ('kaori_migrator', 'kaori_runtime')"
            )
            roles = {row[0] for row in cursor.fetchall()}
            if roles:
                if roles != {'kaori_migrator', 'kaori_runtime'} or db_owner != 'kaori_migrator':
                    fail('Partial role provisioning: operator intervention required')
                # Previously provisioned, empty schema is safe to revisit.
                if scalar(
                    cursor,
                    """
                    SELECT pg_get_userbyid(nspowner) <> 'kaori_migrator'
                    FROM pg_namespace WHERE nspname = 'public'
                    """,
                ):
                    fail('Existing roles have unexpected schema ownership')
                print('PASS: empty bundled database already has separate identities')
                return
            if db_owner != admin_user:
                fail('Legacy owned database is not an uninitialized bootstrap target')
            if scalar(
                cursor,
                "SELECT pg_get_userbyid(nspowner) NOT IN (current_user, 'pg_database_owner') "
                "FROM pg_namespace WHERE nspname = 'public'",
            ):
                fail('Unexpected public schema owner')
            for role, uri in (('kaori_migrator', migration_url), ('kaori_runtime', runtime_url)):
                password = unquote(urlsplit(uri).password or '')
                if not password:
                    fail('Generated PostgreSQL role password is missing')
                cursor.execute(
                    sql.SQL(
                        'CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE '
                        'NOREPLICATION NOBYPASSRLS NOINHERIT PASSWORD {}'
                    ).format(sql.Identifier(role), sql.Literal(scram_password_verifier(password)))
                )
            cursor.execute('ALTER DATABASE kaori OWNER TO kaori_migrator')
            cursor.execute('ALTER SCHEMA public OWNER TO kaori_migrator')
            cursor.execute('REVOKE ALL ON DATABASE kaori FROM PUBLIC')
            cursor.execute('REVOKE ALL ON SCHEMA public FROM PUBLIC')
            cursor.execute('GRANT CONNECT ON DATABASE kaori TO kaori_runtime')
            cursor.execute('GRANT USAGE ON SCHEMA public TO kaori_runtime')
            conn.commit()
    print('PASS: virgin bundled database provisioned with migrator and runtime roles')



def existing_bundled_cutover(runtime_url: str, migration_url: str) -> None:
    """Single-transaction transfer of only audited public KAORI objects.

    Exact legacy owner and no concurrent sessions are mandatory. The old
    administrator remains available for recovery; no cluster-wide transfer command.
    """
    if os.getenv('KAORI_BUNDLED_SCHEMA_CUTOVER') != 'true':
        fail('Existing-schema cutover requires explicit, one-time operator opt-in')
    admin_user = os.getenv('POSTGRES_USER', '')
    admin_password = os.getenv('POSTGRES_PASSWORD', '')
    if admin_user != 'kaori' or not admin_password:
        fail('Existing-schema cutover requires the known legacy kaori administrator')
    if (urlsplit(runtime_url).hostname, urlsplit(migration_url).hostname) != ('postgres', 'postgres'):
        fail('Existing-schema cutover requires bundled postgres DNS target')
    with closing(
        psycopg2.connect(
            host='postgres', port=5432, dbname='kaori',
            user=admin_user, password=admin_password, connect_timeout=5,
        )
    ) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SET LOCAL lock_timeout = '5s'")
            cursor.execute("SET LOCAL statement_timeout = '180s'")
            cursor.execute(
                """
                SELECT current_user, current_database(), rolsuper
                FROM pg_roles WHERE rolname = current_user
                """
            )
            if cursor.fetchone() != ('kaori', 'kaori', True):
                fail('Expected legacy superuser/database is not present')
            if scalar(cursor, 'SELECT pg_is_in_recovery()'):
                fail('Cutover refused on a standby')
            if scalar(
                cursor,
                """
                SELECT count(*) FROM pg_stat_activity
                 WHERE datname = 'kaori' AND pid <> pg_backend_pid()
                """,
            ):
                fail('Application sessions still connected; stop web, workers and Beat')
            cursor.execute(
                """
                SELECT pg_get_userbyid(datdba) FROM pg_database
                WHERE datname = 'kaori'
                """
            )
            if cursor.fetchone()[0] != 'kaori':
                fail('Unexpected database owner; refusing repeat/partial cutover')
            cursor.execute(
                """
                SELECT pg_get_userbyid(nspowner) FROM pg_namespace
                WHERE nspname = 'public'
                """
            )
            if cursor.fetchone()[0] not in {'kaori', 'pg_database_owner'}:
                fail('Unexpected public schema owner')
            if scalar(
                cursor,
                """
                SELECT count(*) FROM pg_namespace
                WHERE nspname NOT IN ('public', 'information_schema')
                  AND left(nspname, 3) <> 'pg_'
                """,
            ):
                fail('Unexpected nonpublic application schemas')
            if scalar(
                cursor,
                """
                SELECT count(*) FROM pg_extension WHERE extname <> 'plpgsql'
                """,
            ):
                fail('Extension-owned objects require a separate reviewed plan')
            # These four 0-arg trigger functions were installed by the
            # already-deployed Capsule migrations. Reject every other function
            # and any unsafe owner/signature before transferring ownership.
            cursor.execute(
                """
                SELECT p.proname, pg_get_function_identity_arguments(p.oid),
                       pg_get_userbyid(p.proowner), p.prokind,
                       p.prorettype = 'pg_catalog.trigger'::regtype
                FROM pg_proc p
                WHERE p.pronamespace = 'public'::regnamespace
                ORDER BY p.oid
                """
            )
            functions = cursor.fetchall()
            if (
                {name for name, *_ in functions} != _CAPSULE_TRIGGER_FUNCTIONS
                or len(functions) != len(_CAPSULE_TRIGGER_FUNCTIONS)
                or any(
                    args or owner != 'kaori' or kind != 'f' or not is_trigger
                    for _, args, owner, kind, is_trigger in functions
                )
            ):
                fail('Unexpected public function identity or owner; no automatic function transfer')
            cursor.execute(
                """
                SELECT c.relname, c.relkind, pg_get_userbyid(c.relowner)
                FROM pg_class c
                WHERE c.relnamespace = 'public'::regnamespace
                ORDER BY c.oid
                """
            )
            objects = cursor.fetchall()
            if not objects or not any(kind == 'r' for _, kind, _ in objects):
                fail('Expected existing application tables are absent')
            if any(owner != 'kaori' or kind not in {'r', 'i', 'S'} for _, kind, owner in objects):
                fail('Unexpected object kind/owner; no automatic ownership transfer')
            cursor.execute(
                """
                SELECT rolname FROM pg_roles
                WHERE rolname IN ('kaori_migrator', 'kaori_runtime')
                """
            )
            if cursor.fetchall():
                fail('Role names already exist; existing-schema bootstrap must be virgin')
            if scalar(
                cursor,
                """
                SELECT EXISTS (
                    SELECT 1 FROM pg_roles
                    WHERE rolname = 'kaori' AND (NOT rolsuper OR NOT rolcanlogin)
                )
                """,
            ):
                fail('Legacy administrator state changed during preflight')
            for role, url in (
                ('kaori_migrator', migration_url),
                ('kaori_runtime', runtime_url),
            ):
                password = unquote(urlsplit(url).password or '')
                if not password:
                    fail('Missing restricted role password')
                cursor.execute(
                    sql.SQL(
                        'CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE '
                        'NOREPLICATION NOBYPASSRLS NOINHERIT PASSWORD {}'
                    ).format(
                        sql.Identifier(role),
                        sql.Literal(scram_password_verifier(password)),
                    )
                )
            # Indexes inherit their owning table's PostgreSQL owner. They are
            # never ALTER INDEX'ed; the complete relation inventory is verified.
            for name, kind, _ in objects:
                if kind == 'r':
                    cursor.execute(
                        sql.SQL('ALTER TABLE public.{} OWNER TO kaori_migrator').format(
                            sql.Identifier(name)
                        )
                    )
                elif kind == 'S':
                    cursor.execute(
                        sql.SQL('ALTER SEQUENCE public.{} OWNER TO kaori_migrator').format(
                            sql.Identifier(name)
                        )
                    )
            for name in sorted(_CAPSULE_TRIGGER_FUNCTIONS):
                cursor.execute(
                    sql.SQL('ALTER FUNCTION public.{}() OWNER TO kaori_migrator').format(
                        sql.Identifier(name)
                    )
                )
            cursor.execute('ALTER DATABASE kaori OWNER TO kaori_migrator')
            cursor.execute('ALTER SCHEMA public OWNER TO kaori_migrator')
            cursor.execute('REVOKE ALL ON DATABASE kaori FROM PUBLIC')
            cursor.execute('REVOKE ALL ON SCHEMA public FROM PUBLIC')
            cursor.execute('GRANT CONNECT ON DATABASE kaori TO kaori_runtime')
            cursor.execute('GRANT USAGE ON SCHEMA public TO kaori_runtime')
            if scalar(
                cursor,
                """
                SELECT count(*) FROM pg_class
                WHERE relnamespace = 'public'::regnamespace
                  AND pg_get_userbyid(relowner) <> 'kaori_migrator'
                """,
            ):
                fail('Objects retain legacy ownership; transaction will roll back')
            if scalar(
                cursor,
                """
                SELECT count(*) FROM pg_proc p
                 WHERE p.pronamespace = 'public'::regnamespace
                   AND pg_get_userbyid(p.proowner) <> 'kaori_migrator'
                """,
            ):
                fail('Capsule trigger functions retain legacy ownership; transaction will roll back')
            if scalar(
                cursor,
                """
                SELECT has_database_privilege('kaori_runtime', 'kaori', 'CREATE')
                    OR has_database_privilege('kaori_runtime', 'kaori', 'TEMPORARY')
                    OR has_schema_privilege('kaori_runtime', 'public', 'CREATE')
                """,
            ):
                fail('Runtime inherited privileges are too broad; transaction rolled back')
            conn.commit()
    print('PASS: existing KAORI schema transferred without deleting application data')



GRANT_SQL = """
GRANT CONNECT ON DATABASE kaori TO kaori_runtime;
GRANT USAGE ON SCHEMA public TO kaori_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO kaori_runtime;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO kaori_runtime;
REVOKE ALL PRIVILEGES ON TABLE public.alembic_version FROM kaori_runtime;
GRANT SELECT ON TABLE public.alembic_version TO kaori_runtime;
REVOKE ALL PRIVILEGES ON TABLE public.capsule_handoff_ledger_events FROM kaori_runtime;
GRANT SELECT, INSERT ON TABLE public.capsule_handoff_ledger_events TO kaori_runtime;
REVOKE ALL PRIVILEGES ON TABLE public.capsule_handoff_audit_batches FROM kaori_runtime;
GRANT SELECT, INSERT ON TABLE public.capsule_handoff_audit_batches TO kaori_runtime;
REVOKE ALL PRIVILEGES ON TABLE public.capsule_handoff_resource_consent_records FROM kaori_runtime;
GRANT SELECT, INSERT ON TABLE public.capsule_handoff_resource_consent_records TO kaori_runtime;
"""


def main() -> None:
    if os.getenv('APP_ENV') != 'production':
        fail('Server PostgreSQL admission requires production APP_ENV')
    mode = sys.argv[1] if len(sys.argv) == 2 else ''
    if mode not in {'bootstrap', 'cutover', 'migrator', 'grant', 'runtime'}:
        fail('Usage: server_database_boundary.py bootstrap|cutover|migrator|grant|runtime')
    runtime_url = parsed_url('DATABASE_URL', 'kaori_runtime')
    if mode == 'runtime':
        with closing(psycopg2.connect(runtime_url, connect_timeout=5)) as conn:
            with conn.cursor() as cursor:
                runtime_guard(cursor)
        print('PASS: restricted PostgreSQL runtime and immutable evidence admitted')
        return
    migration_url = parsed_url('KAORI_DB_MIGRATION_URL', 'kaori_migrator')
    ensure_same_target(runtime_url, migration_url)
    if mode == 'bootstrap':
        fresh_bundled_bootstrap(runtime_url, migration_url)
        return
    if mode == 'cutover':
        existing_bundled_cutover(runtime_url, migration_url)
        return
    with closing(psycopg2.connect(migration_url, connect_timeout=5)) as conn:
        with conn.cursor() as cursor:
            migrator_guard(cursor)
            if mode == 'grant':
                if scalar(cursor, "SELECT to_regclass('public.capsule_handoff_ledger_events')") is None:
                    fail('Immutable schema is missing; migrations must finish before grants')
                if scalar(cursor, "SELECT to_regclass('public.alembic_version')") is None:
                    fail('Alembic schema is missing; migrations must finish before grants')
                cursor.execute(GRANT_SQL)
                # Test effective privileges, including inherited and PUBLIC grants.
                cursor.execute(
                    """
                    SELECT has_schema_privilege('kaori_runtime', 'public', 'CREATE')
                        OR has_table_privilege('kaori_runtime', 'public.capsule_handoff_ledger_events', 'UPDATE')
                        OR has_table_privilege('kaori_runtime', 'public.capsule_handoff_ledger_events', 'DELETE')
                        OR has_table_privilege('kaori_runtime', 'public.capsule_handoff_ledger_events', 'TRUNCATE')
                        OR has_table_privilege('kaori_runtime', 'public.alembic_version', 'UPDATE')
                        OR has_table_privilege('kaori_runtime', 'public.capsule_handoff_audit_batches', 'UPDATE')
                        OR has_table_privilege('kaori_runtime', 'public.capsule_handoff_audit_batches', 'DELETE')
                        OR has_table_privilege('kaori_runtime', 'public.capsule_handoff_audit_batches', 'TRUNCATE')
                        OR has_table_privilege('kaori_runtime', 'public.capsule_handoff_resource_consent_records', 'UPDATE')
                        OR has_table_privilege('kaori_runtime', 'public.capsule_handoff_resource_consent_records', 'DELETE')
                        OR has_table_privilege('kaori_runtime', 'public.capsule_handoff_resource_consent_records', 'TRUNCATE')
                        OR has_table_privilege('kaori_runtime', 'public.alembic_version', 'DELETE')
                    """
                )
                if cursor.fetchone()[0]:
                    fail('Runtime inherited privilege denied; grants rolled back')
                conn.commit()
    print(f'PASS: restricted PostgreSQL {mode} admitted')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, psycopg2.Error) as exc:
        # Never echo psycopg2 connection diagnostics: they may contain connection details.
        detail = str(exc) if isinstance(exc, RuntimeError) else 'connection or SQL error'
        print(f'ABORT: PostgreSQL role admission failed ({detail})', file=sys.stderr)
        raise SystemExit(1) from None
