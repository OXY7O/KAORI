"""Read-only notification delivery statistics over the complete filtered journal."""

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.integrations.delivery.notification_channels.service import _delivery_statistics, _filter_delivery_query
from app.models.notification_channel import NotificationDelivery


@pytest.fixture
def journal() -> Iterator[Session]:
    # Minimal SQL fixture: only fields used by the actual ORM aggregate and predicates.
    engine = create_engine('sqlite+pysqlite:///:memory:')
    with engine.begin() as connection:
        connection.execute(
            text(
                'CREATE TABLE notification_channels ('
                'id INTEGER PRIMARY KEY, provider_key TEXT NOT NULL, lifecycle_state TEXT NOT NULL)'
            )
        )
        connection.execute(
            text(
                'CREATE TABLE notification_deliveries (id INTEGER PRIMARY KEY, channel_id INTEGER NOT NULL, '
                'event_key TEXT NOT NULL, domain TEXT NOT NULL, severity TEXT NOT NULL, '
                'status TEXT NOT NULL, attempt_count INTEGER NOT NULL)'
            )
        )
        connection.execute(
            text(
                "INSERT INTO notification_channels VALUES (1, 'telegram', 'active'), "
                "(2, 'telegram', 'active'), (3, 'slack', 'retired'), "
                "(4, 'discord', 'active'), (5, 'email', 'active')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO notification_deliveries VALUES "
                "(1, 1, 'a', 'kubernetes', 'warning', 'sent', 1), "
                "(2, 1, 'b', 'kubernetes', 'critical', 'failed', 2), "
                "(3, 2, 'c', 'registry', 'info', 'queued', 1), "
                "(4, 2, 'd', 'registry', 'warning', 'skipped', 0), "
                "(5, 3, 'a', 'kubernetes', 'warning', 'sent', 3), "
                "(6, 4, 'e', 'kubernetes', 'critical', 'sent', 2), "
                "(7, 4, 'f', 'registry', 'warning', 'failed', 1)"
            )
        )
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_delivery_statistics_count_records_not_attempts(journal: Session) -> None:
    query = _filter_delivery_query(journal.query(NotificationDelivery))
    assert query.with_entities(NotificationDelivery.id).limit(5).count() == 5
    assert _delivery_statistics(query) == {
        'total': 7,
        'sent': 3,
        'failed': 2,
        'queued': 1,
        'skipped': 1,
        'retried': 3,
        'active_providers': 2,
        'success_rate': 60.0,
    }
    assert query.with_entities(NotificationDelivery.id).count() == 7


@pytest.mark.parametrize(
    ('filters', 'expected'),
    (
        ({'event_key': 'a'}, (2, 2, 0, 1, 1, 100.0)),
        ({'provider': 'slack'}, (1, 1, 0, 1, 0, 100.0)),
        ({'provider': 'telegram'}, (4, 1, 1, 1, 1, 50.0)),
        ({'domain': 'kubernetes'}, (4, 3, 1, 3, 2, 75.0)),
        ({'severity': 'warning'}, (4, 2, 1, 1, 2, 66.7)),
        ({'status': 'failed'}, (2, 0, 2, 1, 2, 0.0)),
        ({'status': 'queued'}, (1, 0, 0, 0, 1, None)),
        ({'status': 'skipped'}, (1, 0, 0, 0, 1, None)),
        ({'event_key': 'missing'}, (0, 0, 0, 0, 0, None)),
        (
            {
                'event_key': 'a',
                'provider': 'telegram',
                'domain': 'kubernetes',
                'severity': 'warning',
                'status': 'sent',
            },
            (1, 1, 0, 0, 1, 100.0),
        ),
    ),
)
def test_delivery_statistics_follow_all_journal_filters(
    journal: Session,
    filters: dict[str, str],
    expected: tuple[int, int, int, int, int, float | None],
) -> None:
    query = _filter_delivery_query(journal.query(NotificationDelivery), **filters)
    stats = _delivery_statistics(query)
    keys = ('total', 'sent', 'failed', 'retried', 'active_providers', 'success_rate')
    assert tuple(stats[key] for key in keys) == expected
    assert stats['total'] == query.with_entities(NotificationDelivery.id).count()
    assert stats['total'] == sum(stats[key] for key in ('sent', 'failed', 'queued', 'skipped'))
