"""Opt-in maintenance worker for the already-committed signed webhook inbox.

No default schedule, public callback registration or provider activation.
Maintains the existing KAORI maintenance queue and JobExecution authority.
"""

from __future__ import annotations

from celery import shared_task
from flask import current_app
from sqlalchemy.orm import Session
from typing import cast

from app.extensions.db import db
from app.integrations.source_control.source_control.providers.github.webhook_recovery import (
    recover_webhook_inbox,
)


@shared_task(
    name='app.integrations.source_control.webhook_maintenance.recover_signed_deliveries',
    acks_late=True,
    reject_on_worker_lost=True,
)
def recover_signed_deliveries() -> dict[str, int | str]:
    """Only an explicitly enabled maintenance policy may process deliveries."""
    if not current_app.config.get('SOURCE_CONTROL_WEBHOOK_CONSUMER_ENABLED', False):
        return {
            'status': 'disabled',
            'examined': 0,
            'queued': 0,
            'reconciled': 0,
            'uncertain': 0,
            'failed': 0,
        }
    return recover_webhook_inbox(cast(Session, db.session))
