"""Readiness gate for operator-attested Internal PKI committed evidence schema."""

from __future__ import annotations

from dataclasses import dataclass

from flask import current_app
from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db

INTERNAL_PKI_REVISION = '20261112_internal_pki'
_REQUIRED_TABLES = frozenset({'internal_pki_evidence_batches', 'internal_pki_certificate_inventory'})


@dataclass(frozen=True, slots=True)
class InternalPKISchemaReadiness:
    ready: bool
    database_reachable: bool
    missing_tables: tuple[str, ...] = ()
    required_revision: str = INTERNAL_PKI_REVISION


def check_internal_pki_schema_readiness() -> InternalPKISchemaReadiness:
    """Inspect schema only; never treat a migration gap as zero collected certs."""
    try:
        available = set(inspect(db.engine).get_table_names())
    except SQLAlchemyError:
        current_app.logger.warning('Internal PKI database schema inspection failed.')
        return InternalPKISchemaReadiness(ready=False, database_reachable=False)
    missing = tuple(sorted(_REQUIRED_TABLES - available))
    return InternalPKISchemaReadiness(
        ready=not missing,
        database_reachable=True,
        missing_tables=missing,
    )
