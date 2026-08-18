from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding='utf-8')


def test_bucket_modal_uses_wide_layout_and_compact_datetime_rows():
    template = read('app/templates/storage/object_storage/inventory/buckets/partials/_table_content.html')
    assert 'max-w-[88rem]' in template
    assert 'x-teleport="body"' in template
    assert "user_datetime(date_format='day_month_numeric')" in template


def test_system_drawer_uses_wider_layout_and_endpoint_stack():
    template = read('app/templates/storage/object_storage/inventory/overview/partials/_systems_snapshot_content.html')
    assert "width='2xl'" in template
    assert "detail_row('Profile', system.compatibility_profile_label)" in template
    assert "detail_row('Endpoint', system.endpoint, break_all=true)" in template


def test_bucket_presentation_uses_short_snapshot_source_label():
    presentation = read('app/storage/object_storage/inventory/presentation.py')
    assert "'source_label': 'Committed Snapshot'" in presentation
