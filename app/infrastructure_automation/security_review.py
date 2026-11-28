"""Local-only transaction boundary for candidate automation security writers.

No public route or default enablement. Official admission and independent
Access review remain separate; do not reuse this gate for worker execution.
"""

from __future__ import annotations

import os

from flask import current_app, has_app_context
from sqlalchemy import text

from app.extensions.db import db


class AutomationSecurityReviewDenied(ValueError):
    """Candidate local security write is not available."""


def local_security_review_enabled() -> bool:
    return (
        has_app_context()
        and os.getenv('APP_ENV') == 'development'
        and current_app.config.get('APP_ENV') == 'development'
        and os.getenv('KAORI_LOCAL_AUTOMATION_SECURITY_REVIEW') == '1'
    )


def begin_security_review_transaction() -> None:
    session = db.session()
    if (
        not local_security_review_enabled()
        or session.in_transaction()
        or session.new
        or session.dirty
        or session.deleted
        or db.engine.dialect.name != 'postgresql'
    ):
        raise AutomationSecurityReviewDenied('Local automation security review is unavailable.')
    if session.execute(text('SHOW transaction_isolation')).scalar_one() != 'read committed':
        raise AutomationSecurityReviewDenied('Local automation security review is unavailable.')
    session.execute(text("SET LOCAL lock_timeout = '5s'"))
    session.execute(text("SET LOCAL statement_timeout = '10s'"))
    # Serialize the rare local grant/trust activation writers. Existing
    # revocation writers coordinate through policy/assignment row locks.
    session.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': 0x4B414F5249415554})
