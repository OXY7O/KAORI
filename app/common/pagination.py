"""Canonical pagination normalization and presentation contracts for KAORI."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any

DEFAULT_PER_PAGE = 5
PER_PAGE_OPTIONS: tuple[int, ...] = (5, 10, 25, 50)


def positive_int(value: Any, default: int = 1) -> int:
    """Parse a positive integer without leaking request-specific behavior."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def normalize_per_page(
    value: Any,
    *,
    default: int = DEFAULT_PER_PAGE,
    allowed: tuple[int, ...] = PER_PAGE_OPTIONS,
) -> int:
    """Normalize page size to the approved KAORI choices."""
    parsed = positive_int(value, default)
    return parsed if parsed in allowed else default


@dataclass(frozen=True, slots=True)
class PaginationWindow:
    page: int
    per_page: int
    total_items: int
    total_pages: int
    offset: int
    start_item: int
    end_item: int
    has_prev: bool
    has_next: bool
    prev_page: int
    next_page: int

    def as_dict(self) -> dict[str, int | bool]:
        return asdict(self)


def build_pagination_window(
    *,
    total_items: int,
    page: Any = 1,
    per_page: Any = DEFAULT_PER_PAGE,
    allowed_per_page: tuple[int, ...] = PER_PAGE_OPTIONS,
) -> PaginationWindow:
    """Build a clamped, zero-safe pagination window."""
    normalized_total = max(int(total_items or 0), 0)
    normalized_per_page = normalize_per_page(
        per_page,
        default=allowed_per_page[0],
        allowed=allowed_per_page,
    )
    total_pages = max((normalized_total + normalized_per_page - 1) // normalized_per_page, 1)
    normalized_page = min(positive_int(page, 1), total_pages)
    offset = (normalized_page - 1) * normalized_per_page
    start_item = offset + 1 if normalized_total else 0
    end_item = min(offset + normalized_per_page, normalized_total)

    return PaginationWindow(
        page=normalized_page,
        per_page=normalized_per_page,
        total_items=normalized_total,
        total_pages=total_pages,
        offset=offset,
        start_item=start_item,
        end_item=end_item,
        has_prev=normalized_page > 1,
        has_next=normalized_page < total_pages,
        prev_page=max(normalized_page - 1, 1),
        next_page=min(normalized_page + 1, total_pages),
    )


def pagination_payload(
    window: PaginationWindow,
    *,
    allowed_per_page: tuple[int, ...] = PER_PAGE_OPTIONS,
) -> dict[str, Any]:
    """Expose one normalized window to Jinja and JSON-compatible callers."""
    return {
        **window.as_dict(),
        'allowed_per_page': list(allowed_per_page),
    }


def paginate_sequence[_ItemT](
    items: Sequence[_ItemT],
    *,
    page: Any = 1,
    per_page: Any = DEFAULT_PER_PAGE,
    allowed_per_page: tuple[int, ...] = PER_PAGE_OPTIONS,
) -> tuple[list[_ItemT], dict[str, Any]]:
    """Paginate an in-memory sequence through the canonical KAORI contract."""
    window = build_pagination_window(
        total_items=len(items),
        page=page,
        per_page=per_page,
        allowed_per_page=allowed_per_page,
    )
    end = window.offset + window.per_page
    return (
        list(items[window.offset:end]),
        pagination_payload(window, allowed_per_page=allowed_per_page),
    )


def paginate_query(
    query: Any,
    *,
    page: Any = 1,
    per_page: Any = DEFAULT_PER_PAGE,
    allowed_per_page: tuple[int, ...] = PER_PAGE_OPTIONS,
) -> tuple[list[Any], dict[str, Any]]:
    """Fetch only one SQLAlchemy query page and return canonical metadata."""
    total_items = query.order_by(None).count()
    window = build_pagination_window(
        total_items=total_items,
        page=page,
        per_page=per_page,
        allowed_per_page=allowed_per_page,
    )
    rows = query.offset(window.offset).limit(window.per_page).all()
    return (
        list(rows),
        pagination_payload(window, allowed_per_page=allowed_per_page),
    )
