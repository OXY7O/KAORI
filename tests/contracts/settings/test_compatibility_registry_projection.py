from __future__ import annotations

from app.settings.general.compatibility_registry import PAGE_SIZE, build_compatibility_registry


def _sample(index: int, *, support: str = 'Current + Extended', profiles: int = 2) -> dict:
    return {
        'key': f'provider-{index}',
        'product': f'Provider {index}',
        'contract_profile': f'core-v{index}',
        'capability_summary': 'Provider capabilities',
        'qualified_versions': f'v{index}.0–v{index}.9',
        'support_label': support,
        'profiles': tuple(
            {
                'key': f'qualification-{number}',
                'version_constraint': f'v{index}.{number}',
                'support_level': 'Current',
                'upstream_lifecycle': 'Supported',
                'contract_profile': f'core-v{index}',
            }
            for number in range(profiles)
        ),
    }


def test_registry_product_pagination_and_selection_are_bounded() -> None:
    catalog = [_sample(index) for index in range(1, 13)]
    assert PAGE_SIZE == 5
    first = build_compatibility_registry(catalog)
    assert len(first['items']) == 5
    assert first['start'] == 1
    assert first['end'] == 5
    assert first['pages'] == 3
    assert first['selected']['key'] == 'provider-1'

    third = build_compatibility_registry(catalog, page='3', selected_key='provider-12')
    assert third['start'] == 11
    assert third['end'] == 12
    assert third['selected']['key'] == 'provider-12'
    assert len(third['items']) == 2

    clamped = build_compatibility_registry(catalog, page='999', selected_key='provider-1')
    assert clamped['page'] == 3
    assert clamped['selected']['key'] == 'provider-11'
    assert build_compatibility_registry(catalog, page='bad')['page'] == 1
    assert build_compatibility_registry(catalog, page='-5')['page'] == 1


def test_registry_search_and_support_filters_preserve_canonical_data() -> None:
    catalog = [_sample(1), _sample(2, support='Extended · Upstream Archived')]
    search = build_compatibility_registry(catalog, search=' CORE-V2 ')
    assert search['total'] == 1
    assert search['selected'] is catalog[1]
    assert search['search'] == 'CORE-V2'

    current = build_compatibility_registry(catalog, support='includes-current')
    assert current['total'] == 1
    assert current['selected'] is catalog[0]

    archived = build_compatibility_registry(catalog, support='extended-only')
    assert archived['total'] == 1
    assert archived['selected'] is catalog[1]

    empty = build_compatibility_registry(catalog, search='unknown-provider', selected_key='provider-1')
    assert empty['total'] == 0
    assert empty['selected'] is None
    assert empty['items'] == ()
    assert empty['profiles'] == ()
    assert empty['start'] == 0
    assert empty['end'] == 0
    assert build_compatibility_registry(catalog, support='invalid')['support'] == 'all'


def test_selected_product_qualification_pagination_preserves_independent_evidence() -> None:
    catalog = [_sample(1, profiles=12)]
    second = build_compatibility_registry(catalog, selected_key='provider-1', profile_page='2')
    assert second['profile_total'] == 12
    assert second['profile_pages'] == 3
    assert second['profile_start'] == 6
    assert second['profile_end'] == 10
    assert len(second['profiles']) == PAGE_SIZE
    assert second['profiles'][0]['version_constraint'] == 'v1.5'
    assert second['selected']['profiles'][0]['version_constraint'] == 'v1.0'

    last = build_compatibility_registry(catalog, profile_page='99')
    assert last['profile_page'] == 3
    assert len(last['profiles']) == 2
    assert build_compatibility_registry(catalog, profile_page='garbage')['profile_page'] == 1

    no_profiles = build_compatibility_registry([_sample(1, profiles=0)])
    assert no_profiles['profiles'] == ()
    assert no_profiles['profile_start'] == 0
    assert no_profiles['profile_end'] == 0
