"""Bounded, inert-by-default Notification Delivery identity reconciliation.

This is an internal building block for #2868, not a scheduled task or HTTP
endpoint. Only an explicitly invoked apply=True operation writes the ledger.
No dispatch, retry, channel lifecycle or hot cleanup reads this ledger yet.

After a full backfill, dual-write and concurrency fencing still must be
admitted separately. A completed page is NOT a completed global migration.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, tuple_
from sqlalchemy.dialects.postgresql import insert

from app.extensions.db import db
from app.models.notification_channel import NotificationDelivery, NotificationDeliveryIdentity

MAX_BACKFILL_BATCH_SIZE = 1000


@dataclass(frozen=True, slots=True)
class DeliveryIdentityBackfillPage:
    high_watermark: int
    last_scanned_id: int
    scanned: int
    missing: int
    already_present: int
    conflicts: int
    inserted: int
    has_more: bool
    applied: bool


def snapshot_delivery_identity_high_watermark() -> int:
    """Capture a bounded source ID fence. Not proof that live writes stopped."""
    return int(db.session.query(func.max(NotificationDelivery.id)).scalar() or 0)


def _normalized_time(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def reconcile_delivery_identity_batch(
    *,
    high_watermark: int,
    after_id: int = 0,
    batch_size: int = 250,
    apply: bool = False,
) -> DeliveryIdentityBackfillPage:
    """Preview or explicitly commit one reconciled ID page.

    Caller owns a stable, captured high-watermark and the durable cursor/job
    state. This helper does not schedule itself, claim migration completion,
    or enable journal deletion. PostgreSQL-only apply uses unique-index
    conflict protection and verifies the resulting source identity.
    """
    if not 1 <= batch_size <= MAX_BACKFILL_BATCH_SIZE:
        raise ValueError('Backfill batch must contain between 1 and 1000 records.')
    if after_id < 0 or high_watermark < 0 or after_id > high_watermark:
        raise ValueError('Backfill cursor must be inside the captured source fence.')
    if apply and (db.session.new or db.session.dirty or db.session.deleted):
        raise RuntimeError('Identity backfill requires a clean isolated database session.')
    if apply and db.session.bind is not None and db.session.bind.dialect.name != 'postgresql':
        raise RuntimeError('Identity backfill mutations require PostgreSQL.')

    rows = (
        db.session.query(
            NotificationDelivery.id,
            NotificationDelivery.channel_id,
            NotificationDelivery.event_key,
            NotificationDelivery.created_at,
        )
        .filter(
            NotificationDelivery.id > after_id,
            NotificationDelivery.id <= high_watermark,
        )
        .order_by(NotificationDelivery.id.asc())
        .limit(batch_size + 1)
        .all()
    )
    page_rows = rows[:batch_size]
    has_more = len(rows) > batch_size
    cursor = int(page_rows[-1].id) if page_rows else after_id
    if not page_rows:
        return DeliveryIdentityBackfillPage(
            high_watermark, cursor, 0, 0, 0, 0, 0, False, apply,
        )

    keys = [(row.channel_id, row.event_key) for row in page_rows]
    saved = (
        db.session.query(NotificationDeliveryIdentity)
        .filter(
            tuple_(
                NotificationDeliveryIdentity.channel_id,
                NotificationDeliveryIdentity.event_key,
            ).in_(keys)
        )
        .all()
    )
    existing = {(item.channel_id, item.event_key): item for item in saved}
    missing_rows = []
    conflicts = 0
    for row in page_rows:
        key = (row.channel_id, row.event_key)
        identity = existing.get(key)
        if identity is None:
            missing_rows.append(row)
            continue
        if (
            identity.source_delivery_id != row.id
            or _normalized_time(identity.first_seen_at) != _normalized_time(row.created_at)
        ):
            conflicts += 1

    if apply and conflicts:
        raise RuntimeError('Delivery identity/source mismatch; abort the entire backfill page.')

    inserted = 0
    if apply and missing_rows:
        values = [
            {
                'channel_id': row.channel_id,
                'event_key': row.event_key,
                'source_delivery_id': row.id,
                'first_seen_at': row.created_at,
            }
            for row in missing_rows
        ]
        try:
            statement = insert(NotificationDeliveryIdentity).values(values)
            db.session.execute(
                statement.on_conflict_do_nothing(
                    index_elements=('channel_id', 'event_key'),
                ),
            )
            # Recheck every key after concurrent duplicate reservations.
            persisted = (
                db.session.query(NotificationDeliveryIdentity)
                .filter(
                    tuple_(
                        NotificationDeliveryIdentity.channel_id,
                        NotificationDeliveryIdentity.event_key,
                    ).in_(keys)
                )
                .all()
            )
            actual = {(item.channel_id, item.event_key): item for item in persisted}
            for row in page_rows:
                identity = actual.get((row.channel_id, row.event_key))
                if identity is None or identity.source_delivery_id != row.id or (
                    _normalized_time(identity.first_seen_at) != _normalized_time(row.created_at)
                ):
                    raise RuntimeError('Concurrent identity conflict; rolling back backfill page.')
            db.session.commit()
            inserted = len(missing_rows)
        except Exception:
            db.session.rollback()
            raise

    return DeliveryIdentityBackfillPage(
        high_watermark=high_watermark,
        last_scanned_id=cursor,
        scanned=len(page_rows),
        missing=len(missing_rows),
        already_present=len(page_rows) - len(missing_rows),
        conflicts=conflicts,
        inserted=inserted,
        has_more=has_more,
        applied=apply,
    )
