from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

PAGE_SIZE = 5
SUPPORT_FILTERS = frozenset({'all', 'includes-current', 'extended-only'})


def _page_number(raw: str | None) -> int:
    try:
        return max(1, int(raw or '1'))
    except (TypeError, ValueError):
        return 1


def build_compatibility_registry(
    catalog: Sequence[Mapping[str, Any]],
    *,
    search: str | None = None,
    support: str | None = None,
    page: str | None = None,
    selected_key: str | None = None,
    profile_page: str | None = None,
) -> dict[str, Any]:
    """Bounded read-only display projection over the authoritative compatibility catalog."""
    query = (search or '').strip()[:100]
    filter_value = support if support in SUPPORT_FILTERS else 'all'
    needle = query.casefold()
    products = tuple(
        item for item in catalog
        if (not needle or any(
            needle in str(item.get(field, '')).casefold()
            for field in ('product', 'contract_profile', 'capability_summary', 'qualified_versions')
        ))
        and (
            filter_value == 'all'
            or (filter_value == 'includes-current' and 'current' in str(item['support_label']).casefold())
            or (
                filter_value == 'extended-only'
                and 'extended' in str(item['support_label']).casefold()
                and 'current' not in str(item['support_label']).casefold()
            )
        )
    )
    total = len(products)
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    current_page = min(_page_number(page), pages)
    offset = (current_page - 1) * PAGE_SIZE
    listed = products[offset : offset + PAGE_SIZE]
    selected = next((item for item in listed if item['key'] == selected_key), listed[0] if listed else None)

    qualifications = tuple(selected.get('profiles', ())) if selected else ()
    qualification_total = len(qualifications)
    qualification_pages = max(1, (qualification_total + PAGE_SIZE - 1) // PAGE_SIZE)
    current_profile_page = min(_page_number(profile_page), qualification_pages)
    profile_offset = (current_profile_page - 1) * PAGE_SIZE

    return {
        'search': query,
        'support': filter_value,
        'page': current_page,
        'pages': pages,
        'total': total,
        'start': offset + 1 if total else 0,
        'end': min(offset + PAGE_SIZE, total),
        'items': listed,
        'selected': selected,
        'profile_page': current_profile_page,
        'profile_pages': qualification_pages,
        'profile_total': qualification_total,
        'profiles': qualifications[profile_offset : profile_offset + PAGE_SIZE],
        'profile_start': profile_offset + 1 if qualification_total else 0,
        'profile_end': min(profile_offset + PAGE_SIZE, qualification_total),
        'page_size': PAGE_SIZE,
    }
