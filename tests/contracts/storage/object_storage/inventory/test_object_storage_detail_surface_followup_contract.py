from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding='utf-8')


def test_side_drawer_supports_wider_widths():
    component = read('app/templates/components/side_drawer.html')
    assert "width == '2xl'" in component
    assert "width == '3xl'" in component
    assert 'max-w-4xl' in component
    assert 'max-w-5xl' in component


def test_overview_system_drawer_uses_wider_surface_and_full_width_endpoint():
    template = read('app/templates/storage/object_storage/inventory/overview/partials/_systems_snapshot_content.html')
    assert "width='2xl'" in template
    assert "detail_row('Endpoint', system.endpoint, break_all=true)" in template


def test_bucket_details_use_modal_not_drawer():
    template = read('app/templates/storage/object_storage/inventory/buckets/partials/_table_content.html')
    assert 'max-w-[88rem]' in template
    assert 'x-teleport="body"' in template
    assert 'openDetail' in template
    assert 'role="dialog"' in template
    assert "width='xl'" not in template


def test_bucket_snapshot_source_is_compact():
    presentation = read('app/storage/object_storage/inventory/presentation.py')
    assert "'source_label': 'Committed Snapshot'" in presentation
