from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.integrations.runtime import repository

pytestmark = pytest.mark.functional


class _OrderColumn:
    def desc(self) -> _OrderColumn:
        return self


class _RuntimeObservationModel:
    observed_at = _OrderColumn()
    id = _OrderColumn()


class _RuntimeHistoryQuery:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows
        self.filters: dict[str, object] = {}
        self.offset_value = 0
        self.limit_value: int | None = None

    def filter_by(self, **filters: object) -> _RuntimeHistoryQuery:
        self.filters = filters
        return self

    def count(self) -> int:
        return len(self._rows)

    def order_by(self, *_columns: object) -> _RuntimeHistoryQuery:
        return self

    def offset(self, value: int) -> _RuntimeHistoryQuery:
        self.offset_value = value
        return self

    def limit(self, value: int) -> _RuntimeHistoryQuery:
        self.limit_value = value
        return self

    def all(self) -> list[object]:
        end = None if self.limit_value is None else self.offset_value + self.limit_value
        return self._rows[self.offset_value : end]


def test_runtime_history_returns_exact_requested_page_size(monkeypatch: pytest.MonkeyPatch) -> None:
    query = _RuntimeHistoryQuery([SimpleNamespace(id=index) for index in range(1, 8)])
    model = type(
        'RuntimeObservationModel',
        (),
        {
            'query': query,
            'observed_at': _RuntimeObservationModel.observed_at,
            'id': _RuntimeObservationModel.id,
        },
    )
    monkeypatch.setattr(repository, 'IntegrationRuntimeObservation', model)

    rows, pagination = repository.paginate_runtime_history(
        'prometheus',
        '17',
        page=1,
        per_page=5,
    )

    assert [row.id for row in rows] == [1, 2, 3, 4, 5]
    assert query.filters == {'provider': 'prometheus', 'instance_id': '17'}
    assert query.limit_value == 5
    assert pagination['end_item'] == 5
    assert pagination['has_next'] is True


def test_runtime_history_clamps_page_and_normalizes_page_size(monkeypatch: pytest.MonkeyPatch) -> None:
    query = _RuntimeHistoryQuery([SimpleNamespace(id=index) for index in range(1, 13)])
    model = type(
        'RuntimeObservationModel',
        (),
        {
            'query': query,
            'observed_at': _RuntimeObservationModel.observed_at,
            'id': _RuntimeObservationModel.id,
        },
    )
    monkeypatch.setattr(repository, 'IntegrationRuntimeObservation', model)

    rows, pagination = repository.paginate_runtime_history(
        'alertmanager',
        9,
        page=99,
        per_page=100,
    )

    assert [row.id for row in rows] == [11, 12]
    assert query.offset_value == 10
    assert query.limit_value == 5
    assert pagination['page'] == 3
    assert pagination['per_page'] == 5
    assert pagination['start_item'] == 11
    assert pagination['end_item'] == 12
    assert pagination['has_next'] is False
