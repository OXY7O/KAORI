from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_object_storage_overview_drawer_uses_balanced_width():
    template = read("app/templates/object_storage_inventory/overview/partials/_systems_snapshot_content.html")
    assert "width='2xl'" in template
    assert "width='3xl'" not in template


def test_provider_context_keeps_endpoint_inline():
    template = read("app/templates/object_storage_inventory/overview/partials/_systems_snapshot_content.html")
    assert "detail_row('Endpoint', system.endpoint, break_all=true)" in template
    assert "stacked_detail_row('Endpoint'" not in template
    assert "detail_row('Region', system.region)" in template
    assert "detail_row('Addressing', system.addressing_style)" in template
    assert "detail_row('Profile', system.compatibility_profile_label)" in template
