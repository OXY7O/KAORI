from __future__ import annotations

from dataclasses import dataclass

from flask import current_app
from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db

_REQUIRED_AUTH_TABLES = frozenset(
    {
        'users',
        'roles',
        'permissions',
        'identity_providers',
        'external_identity_links',
        'notifications',
    }
)


@dataclass(frozen=True, slots=True)
class AuthenticationDatabaseReadiness:
    ready: bool
    database_reachable: bool
    missing_tables: tuple[str, ...] = ()
    detail: str | None = None

    @property
    def setup_required(self) -> bool:
        return self.database_reachable and not self.ready


def check_authentication_database_readiness() -> AuthenticationDatabaseReadiness:
    """Check only the schema required to render and process KAORI authentication.

    This intentionally uses SQLAlchemy inspection rather than querying an ORM model so
    a fresh, empty database can be detected without raising an UndefinedTable error.
    """

    try:
        available_tables = set(inspect(db.engine).get_table_names())
    except SQLAlchemyError as exc:
        current_app.logger.warning('Authentication database readiness check failed: %s', exc)
        return AuthenticationDatabaseReadiness(
            ready=False,
            database_reachable=False,
            detail='KAORI could not connect to PostgreSQL.',
        )

    missing_tables = tuple(sorted(_REQUIRED_AUTH_TABLES - available_tables))
    if missing_tables:
        current_app.logger.info(
            'KAORI authentication schema is not initialized; missing tables: %s',
            ', '.join(missing_tables),
        )
        return AuthenticationDatabaseReadiness(
            ready=False,
            database_reachable=True,
            missing_tables=missing_tables,
            detail='The KAORI database is reachable but its schema has not been initialized.',
        )

    return AuthenticationDatabaseReadiness(ready=True, database_reachable=True)
