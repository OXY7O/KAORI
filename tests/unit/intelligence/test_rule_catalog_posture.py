from __future__ import annotations

from app.intelligence.service import _apply_catalog_payload


def payload(*, available=0, reserved=0, imported=0, domains=0, filters=0):
    return {
        'filters': {'domain': 'server' if filters else '', 'provider': ''},
        'active_filter_count': filters,
        'result_context': {
            'matching_items': available + reserved + imported,
            'available_items': available,
            'reserved_items': reserved,
            'imported_items': imported,
            'matched_domains': domains,
        },
    }


def test_reserved_only_filter_has_no_active_coverage_claim() -> None:
    result = payload(reserved=2, domains=1, filters=1)
    _apply_catalog_payload(result)
    assert result['posture']['label'] == 'Reserved Plan'
    assert result['summary']['available'] == 0
    assert result['summary']['domains'] == 1
    assert result['scope_label'].startswith('Filtered ·')


def test_imported_only_and_no_match_have_distinct_posture() -> None:
    for result, expected in [
        (payload(imported=2, domains=1), 'Imported Signal'),
        (payload(), 'No Matching Rules'),
        (payload(reserved=1, imported=1), 'Catalog Only'),
        (payload(available=1, reserved=2), 'Definitions Available'),
    ]:
        _apply_catalog_payload(result)
        assert result['posture']['label'] == expected
