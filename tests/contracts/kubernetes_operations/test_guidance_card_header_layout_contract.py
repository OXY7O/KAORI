from pathlib import Path


def test_view_more_content_uses_grid_header_layout_for_compact_rails():
    template = Path('app/templates/components/view_more_content.html').read_text()
    assert 'grid-cols-[auto_minmax(0,1fr)_auto]' in template
    assert 'row-span-2 flex h-9 w-9' in template
    assert 'hidden sm:inline group-open:hidden' in template
    assert 'col-span-2 min-w-0 text-xs leading-5 text-content-muted sm:col-span-1' in template
