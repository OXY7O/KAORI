from __future__ import annotations

import pytest

from app.common.pagination import (
    PER_PAGE_OPTIONS,
    build_pagination_window,
    normalize_per_page,
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
