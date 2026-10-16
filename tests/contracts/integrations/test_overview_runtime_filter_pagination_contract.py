"""Integration Overview runtime navigation retains its canonical integration type filter."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_runtime_pagination_uses_route_owned_type_query_key() -> None:
    source = (ROOT / 'app/templates/integrations/partials/_runtime_overview.html').read_text()
    block = source.split('{% set runtime_query_params = {', 1)[1].split('} %}', 1)[0]
    assert "'integration_type': selected_integration_type" in block
    assert "'provider': selected_integration_type" not in block
    assert "'health': selected_health" in block
    assert "'readiness': selected_readiness" in block
    assert "'tab': 'runtime'" in block
    assert 'provider_registry.pagination_footer(runtime_pagination,' in source


def test_runtime_route_and_shared_footer_preserve_one_canonical_filter_name() -> None:
    route = (ROOT / 'app/integrations/routes.py').read_text()
    footer = (ROOT / 'app/templates/integrations/components/_provider_registry.html').read_text()
    assert "integration_type=request.args.get('integration_type', '').strip()" in route
    assert 'for name, value in query_params.items()' in footer
    assert 'prev_url = url_for(endpoint, **prev_args)' in footer
    assert 'next_url = url_for(endpoint, **next_args)' in footer
    assert 'hx-get="{{ prev_url }}"' in footer
    assert 'hx-push-url="true"' in footer
    assert "per_page_param='per_page'" in footer
