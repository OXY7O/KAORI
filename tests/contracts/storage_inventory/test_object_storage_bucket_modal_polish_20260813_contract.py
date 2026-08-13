from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding='utf-8')


def test_bucket_detail_modal_uses_wide_responsive_surface_without_nested_key_value_grids() -> None:
    template = read('app/templates/object_storage_inventory/buckets/partials/_table_content.html')
    assert 'max-w-[88rem]' in template
    assert "side_drawer.section('Asset Context'" in template
    assert "side_drawer.section('Provider Context'" in template
    assert template.count('<div class="space-y-3">') >= 4
    assert 'grid gap-x-6 gap-y-3 sm:grid-cols-2' not in template


def test_provider_configuration_uses_compact_evidence_tiles() -> None:
    template = read('app/templates/object_storage_inventory/buckets/partials/_table_content.html')
    assert 'sm:grid-cols-2 xl:grid-cols-4' in template
    assert 'rounded-lg border border-outline-subtle bg-surface-elevated' in template
    assert "detail_row('API Endpoint', asset.endpoint, break_all=true)" in template


def test_bucket_modal_adds_kaori_operational_reading_with_semantic_guidance() -> None:
    template = read('app/templates/object_storage_inventory/buckets/partials/_table_content.html')

    assert 'Operational Reading' in template
    assert 'bg-kaori-mist/40' in template
    assert 'operational_callout.render(quota_reading_title' in template
    assert 'operational_callout.render(usage_reading_title' in template
    assert 'operational_callout.render(protection_reading_title' in template
    assert "variant='semantic'" in template
    assert 'Quota Evidence Missing' in template
    assert 'Usage Collection Disabled' in template
    assert 'Protection Review Recommended' in template
