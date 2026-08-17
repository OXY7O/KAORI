from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_shared_registry_pagination_owns_full_and_partial_navigation() -> None:
    pagination = read('app/templates/integrations/components/_provider_registry.html')

    assert 'action="{{ url_for(endpoint) }}"' in pagination
    assert 'hx-get="{{ url_for(endpoint) }}"' in pagination
    assert 'hx-target="{{ target }}"' in pagination
    assert 'hx-indicator="{{ indicator }}"' in pagination
    assert 'hx-push-url="true"' in pagination
    assert 'href_endpoint=endpoint' in pagination
    assert "page_param='page'" in pagination
    assert "per_page_param='per_page'" in pagination


def test_coverage_pagination_uses_coverage_parameter_names() -> None:
    coverage = read('app/templates/components/integration_coverage_content.html')

    assert 'provider_registry.pagination_footer(' in coverage
    assert "page_param='coverage_page'" in coverage
    assert "per_page_param='coverage_per_page'" in coverage


def test_provider_routes_return_the_owning_partial_for_htmx() -> None:
    routes = read('app/integrations/routes.py')

    assert "target = request.headers.get('HX-Target')" in routes
    assert "if target == 'integration-coverage':" in routes
    assert "'integrations/partials/_coverage_card.html'" in routes
    assert "if target == 'metrics-source-coverage-content':" in routes
    assert "if target == 'metrics-source-inventory-card':" in routes
    assert "'integrations/metrics/partials/_inventory_content.html'" in routes
    assert "if target == 'alertmanager-coverage-content':" in routes
    assert "if target == 'alertmanager-inventory-card':" in routes
    assert "'integrations/alertmanager/partials/_inventory_content.html'" in routes
