"""Committed Source Control overview keeps optional collection evidence explicit."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.source_control import presentation


class _Query:
    def __init__(self, rows: list[tuple[object, object, object | None]]) -> None:
        self._rows = rows

    def join(self, *_args: object) -> _Query:
        return self

    def outerjoin(self, *_args: object) -> _Query:
        return self

    def filter(self, *_args: object) -> _Query:
        return self

    def order_by(self, *_args: object) -> _Query:
        return self

    def limit(self, *_args: object) -> _Query:
        return self

    def all(self) -> list[tuple[object, object, object | None]]:
        return self._rows


@pytest.mark.parametrize('generation', [None, 0, 2])
def test_source_control_overview_reports_committed_only_when_generation_exists(
    monkeypatch: pytest.MonkeyPatch, generation: int | None
) -> None:
    seen_at = datetime(2026, 10, 27, tzinfo=UTC)
    collection = (
        SimpleNamespace(
            committed_generation=generation,
            observed_count=0,
            coverage='complete',
            repository_scope='selected',
            status='success',
            last_committed_at=seen_at,
        )
        if generation is not None
        else None
    )
    rows = [(SimpleNamespace(id=17), SimpleNamespace(id=21), collection)]
    query = _Query(rows)
    monkeypatch.setattr(
        presentation,
        'db',
        SimpleNamespace(session=SimpleNamespace(query=lambda *_args: query)),
    )

    overview = presentation.build_source_control_overview()
    installation = overview['installations'][0]
    committed = generation is not None and generation > 0

    assert overview['installation_count'] == 1
    assert overview['committed_count'] == int(committed)
    assert overview['uncollected_count'] == int(not committed)
    assert installation['committed'] is committed
    assert installation['observed_count'] == (0 if committed else None)
    assert installation['coverage'] == ('complete' if committed else 'unknown')
    assert installation['selection_scope'] == ('selected' if committed else 'unknown')
    assert installation['last_committed_at'] == (seen_at if committed else None)
    assert installation['collection_status'] == ('not_collected' if collection is None else 'success')
    assert overview['latest_committed_at'] == (seen_at if committed else None)
