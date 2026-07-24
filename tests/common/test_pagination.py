from __future__ import annotations

import pytest

from app.common.pagination import (
    PER_PAGE_OPTIONS,
    build_pagination_window,
    normalize_per_page,
    paginate_query,
    paginate_sequence,
    positive_int,
)

pytestmark = pytest.mark.functional


def test_positive_int_rejects_invalid_zero_and_negative_values() -> None:
    assert positive_int('3', 1) == 3
    assert positive_int(None, 1) == 1
    assert positive_int('invalid', 1) == 1
    assert positive_int(0, 1) == 1
    assert positive_int(-3, 1) == 1


def test_per_page_is_limited_to_kaori_options() -> None:
    assert PER_PAGE_OPTIONS == (5, 10, 25, 50)
    assert normalize_per_page('10') == 10
    assert normalize_per_page('100') == 5
    assert normalize_per_page('invalid') == 5


def test_empty_pagination_window_is_zero_safe() -> None:
    window = build_pagination_window(total_items=0, page=99, per_page=10)

    assert window.page == 1
    assert window.total_pages == 1
    assert window.offset == 0
    assert window.start_item == 0
    assert window.end_item == 0
    assert window.has_prev is False
    assert window.has_next is False


def test_pagination_window_clamps_page_and_calculates_boundaries() -> None:
    window = build_pagination_window(total_items=12, page=99, per_page=5)

    assert window.page == 3
    assert window.total_pages == 3
    assert window.offset == 10
    assert window.start_item == 11
    assert window.end_item == 12
    assert window.has_prev is True
    assert window.has_next is False
    assert window.prev_page == 2
    assert window.next_page == 3


class _QueryStub:
    def __init__(self, rows: list[int]) -> None:
        self.rows = rows
        self.offset_value = 0
        self.limit_value = len(rows)

    def order_by(self, *_args):
        return self

    def count(self) -> int:
        return len(self.rows)

    def offset(self, value: int):
        self.offset_value = value
        return self

    def limit(self, value: int):
        self.limit_value = value
        return self

    def all(self) -> list[int]:
        end = self.offset_value + self.limit_value
        return self.rows[self.offset_value:end]


def test_paginate_sequence_uses_the_canonical_payload() -> None:
    rows, pagination = paginate_sequence(list(range(13)), page=99, per_page=7)

    assert rows == [10, 11, 12]
    assert pagination['page'] == 3
    assert pagination['per_page'] == 5
    assert pagination['offset'] == 10
    assert pagination['total_items'] == 13
    assert pagination['allowed_per_page'] == [5, 10, 25, 50]


def test_paginate_query_fetches_only_the_requested_page() -> None:
    query = _QueryStub(list(range(18)))

    rows, pagination = paginate_query(query, page=2, per_page=5)

    assert rows == [5, 6, 7, 8, 9]
    assert query.offset_value == 5
    assert query.limit_value == 5
    assert pagination['page'] == 2
    assert pagination['total_items'] == 18
    assert pagination['start_item'] == 6
    assert pagination['end_item'] == 10
