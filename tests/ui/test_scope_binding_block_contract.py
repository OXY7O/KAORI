from pathlib import Path


def test_scope_bindings_are_full_width_responsive_workspace_blocks() -> None:
    for provider in ('prometheus', 'alertmanager'):
        source = Path(f'app/templates/{provider}/partials/_detail_scope.html').read_text(encoding='utf-8')
        binding_start = source.index('<h3 class="text-base font-semibold text-content-primary">Scope Bindings</h3>')
        grid_start = source.index('<div class="grid items-start gap-4 xl:grid-cols-12">', binding_start)
        resolution_start = source.index('Effective Source Resolution', binding_start)
        binding_slice = source[binding_start:grid_start]
        assert binding_start < grid_start < resolution_start
        assert 'overflow-x-auto' not in binding_slice
        assert '<table' not in binding_slice
        assert 'lg:grid-cols-3' in binding_slice
        assert 'break-words text-sm font-medium leading-5 text-content-primary' in binding_slice
        assert 'font-mono' not in binding_slice
        assert 'Configure' in binding_slice
        assert 'Validate' in binding_slice
        assert 'Remove' in binding_slice
