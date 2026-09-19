from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, NamedTuple

FOOTER_SAFE_ZONE_MM = 18.0
PAIR_PEER_UNIT_LIMIT = 9.0
PAIR_COMBINED_UNIT_LIMIT = 16.0
REFERENCE_TWO_COLUMN_MAX_ITEMS = 6
REFERENCE_TWO_COLUMN_MAX_IDENTITY_CHARS = 48


class PageChunk(NamedTuple):
    items: list[Any]
    continuation: bool


def _content_units(*, chars: int, rows: int) -> float:
    """Estimate layout density without changing canonical typography."""

    safe_chars = max(0, int(chars))
    safe_rows = max(0, int(rows))
    return (safe_chars / 80.0) + (safe_rows * 0.65)


def choose_pair_mode(
    *,
    left_chars: int,
    right_chars: int,
    left_rows: int = 0,
    right_rows: int = 0,
) -> str:
    """Return ``split`` for balanced peers or ``stack`` for dense content."""

    left_units = _content_units(chars=left_chars, rows=left_rows)
    right_units = _content_units(chars=right_chars, rows=right_rows)
    if max(left_units, right_units) > PAIR_PEER_UNIT_LIMIT:
        return 'stack'
    if left_units + right_units > PAIR_COMBINED_UNIT_LIMIT:
        return 'stack'
    return 'split'


def choose_reference_columns(
    items: Sequence[Mapping[str, Any]],
    *,
    identity_key: str = 'identity',
) -> int:
    """Use two columns only when identity rows are both short and few."""

    if len(items) > REFERENCE_TWO_COLUMN_MAX_ITEMS:
        return 1
    longest = max((len(str(item.get(identity_key) or '')) for item in items), default=0)
    return 1 if longest > REFERENCE_TWO_COLUMN_MAX_IDENTITY_CHARS else 2


def paginate_rows[T](
    rows: Sequence[T],
    *,
    first_page_capacity: int,
    continuation_capacity: int,
) -> list[PageChunk]:
    """Split dynamic register rows while preserving order and continuation state."""

    if first_page_capacity < 1 or continuation_capacity < 1:
        raise ValueError('Page capacities must be positive integers.')
    remaining = list(rows)
    chunks: list[PageChunk] = []
    capacity = first_page_capacity
    continuation = False
    while remaining:
        chunk = remaining[:capacity]
        remaining = remaining[capacity:]
        chunks.append(PageChunk(items=chunk, continuation=continuation))
        capacity = continuation_capacity
        continuation = True
    return chunks


def block_fits(
    *,
    remaining_mm: float,
    estimated_block_mm: float,
    footer_safe_zone_mm: float = FOOTER_SAFE_ZONE_MM,
) -> bool:
    """Return True only when a block leaves the canonical footer safety zone."""

    return max(0.0, estimated_block_mm) + footer_safe_zone_mm <= max(0.0, remaining_mm)
