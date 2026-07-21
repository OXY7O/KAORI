from pathlib import Path


def test_scope_bindings_are_independent_workspace_blocks() -> None:
    marker = '</section>\n\n        <div class="grid items-start gap-4 xl:grid-cols-12">'
    for provider in ('prometheus', 'alertmanager'):
        source = Path(f'app/templates/{provider}/partials/_detail_scope.html').read_text(encoding='utf-8')
        assert '<div class="space-y-4">' in source
        assert source.index(marker) > source.index('Scope &amp; Resolution')
        assert '<h3 class="text-sm font-semibold text-content-primary">Scope Bindings</h3>' in source
