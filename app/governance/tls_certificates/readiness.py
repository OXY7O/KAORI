from __future__ import annotations

from dataclasses import dataclass

from flask import current_app
from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db

TLS_EVIDENCE_REVISION = '20260731_tls_evidence'
_REQUIRED_TABLES = frozenset(
    {
        'tls_certificate_inventory',
        'tls_certificate_collection_states',
    }
)
_REQUIRED_INVENTORY_COLUMNS = frozenset(
    {
        'coverage_state',
        'declared_host_count',
        'covered_host_count',
        'uncovered_hosts',
    }
)


@dataclass(frozen=True, slots=True)
class TLSGovernanceSchemaReadiness:
    ready: bool
    database_reachable: bool
    missing_tables: tuple[str, ...] = ()
    missing_columns: tuple[str, ...] = ()
    detail: str | None = None
    required_revision: str = TLS_EVIDENCE_REVISION

    def as_dict(self) -> dict[str, object]:
        return {
            'ready': self.ready,
            'database_reachable': self.database_reachable,
            'missing_tables': self.missing_tables,
            'missing_columns': self.missing_columns,
            'detail': self.detail,
            'required_revision': self.required_revision,
        }


def check_tls_governance_schema_readiness() -> TLSGovernanceSchemaReadiness:
    """Inspect TLS governance schema without querying the evolving ORM model.

    The readiness check prevents an outdated database from turning the TLS
    inventory and rotation pages into an UndefinedColumn 500 response.
    """

    try:
        inspector = inspect(db.engine)
        available_tables = set(inspector.get_table_names())
    except SQLAlchemyError as exc:
        current_app.logger.warning('TLS governance database readiness check failed: %s', exc)
        return TLSGovernanceSchemaReadiness(
            ready=False,
            database_reachable=False,
            detail='KAORI could not inspect the PostgreSQL schema.',
        )

    missing_tables = tuple(sorted(_REQUIRED_TABLES - available_tables))
    missing_columns: tuple[str, ...] = ()
    if 'tls_certificate_inventory' in available_tables:
        try:
            available_columns = {
                str(column['name'])
                for column in inspector.get_columns('tls_certificate_inventory')
            }
        except SQLAlchemyError as exc:
            current_app.logger.warning('TLS inventory column readiness check failed: %s', exc)
            return TLSGovernanceSchemaReadiness(
                ready=False,
                database_reachable=True,
                detail='KAORI could not inspect the TLS certificate inventory columns.',
            )
        missing_columns = tuple(sorted(_REQUIRED_INVENTORY_COLUMNS - available_columns))

    if missing_tables or missing_columns:
        current_app.logger.warning(
            'TLS governance schema requires revision %s; missing tables=%s missing columns=%s',
            TLS_EVIDENCE_REVISION,
            ','.join(missing_tables) or 'none',
            ','.join(missing_columns) or 'none',
        )
        return TLSGovernanceSchemaReadiness(
            ready=False,
            database_reachable=True,
            missing_tables=missing_tables,
            missing_columns=missing_columns,
            detail='The database is reachable, but the TLS governance schema is behind the application revision.',
        )

    return TLSGovernanceSchemaReadiness(ready=True, database_reachable=True)
