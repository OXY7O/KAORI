from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.storage.object_storage.inventory.presentation import _bucket_empty_state


@pytest.mark.parametrize(
    ('assets', 'observed', 'coverage', 'label', 'title'),
    [
        (0, None, 'unknown', 'Collection Pending', 'No Buckets or Containers Collected Yet'),
        (0, None, 'warning', 'Collection Pending', 'No Buckets or Containers Collected Yet'),
        (0, datetime(2026, 10, 12, tzinfo=UTC), 'normal', 'Observed Empty', 'No Buckets or Containers Observed'),
        (0, datetime(2026, 10, 12, tzinfo=UTC), 'warning', 'Partial Inventory', 'No Buckets or Containers in Collected Systems'),
        (2, datetime(2026, 10, 12, tzinfo=UTC), 'normal', 'No Matches', 'No Buckets or Containers Match These Filters'),
        (2, None, 'warning', 'No Matches', 'No Buckets or Containers Match These Filters'),
    ],
)
def test_bucket_empty_state_distinguishes_observation_from_absent_rows(
    assets: int, observed: datetime | None, coverage: str, label: str, title: str,
) -> None:
    state = _bucket_empty_state(
        assets,
        {'latest_collected_at': observed, 'coverage_tone': coverage},
    )
    assert state['label'] == label
    assert state['title'] == title
    assert state['description']
    if label == 'Observed Empty':
        assert 'successfully observed zero' in state['description']
        assert 'not a live provider check' in state['description']
