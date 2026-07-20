import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LANDING = ROOT / 'app/templates/integrations/prometheus.html'
REGISTRY = ROOT / 'app/templates/integrations/prometheus/partials/_instance_inventory.html'
FORM = ROOT / 'app/templates/prometheus/instance_form.html'
DETAIL = ROOT / 'app/templates/prometheus/instance_detail.html'
ROUTES = ROOT / 'app/prometheus/routes.py'
FORMS = ROOT / 'app/prometheus/forms.py'
RELATED = ROOT / 'app/templates/components/related_page_card.html'
AUDIT = ROOT / 'docs/design/audits/PROMETHEUS_ALERTMANAGER_ALIGNMENT_AUDIT_2026_07.md'


def test_provider_landing_has_one_registration_action_and_registry_has_no_duplicate() -> None:
    landing = LANDING.read_text(encoding='utf-8')
    registry = REGISTRY.read_text(encoding='utf-8')
    combined = landing + registry

    assert combined.count('Register Connection') == 1
    assert combined.count("url_for('prometheus.new_instance')") == 1
    assert "url_for('prometheus.instances')" not in combined
    assert 'Manage Scope Bindings' not in registry
    assert 'Register Connection' not in registry


def test_prometheus_landing_hero_matches_compact_alertmanager_contract() -> None:
    landing = LANDING.read_text(encoding='utf-8')

    required = (
        'Connection Readiness and Bindings',
        'page_hero.context_panel_metrics_classes()',
        "page_hero.context_metric('badge-check', 'Ready'",
        "page_hero.context_metric('link-2', 'Bindings'",
        'Register Connection',
    )
    missing = [fragment for fragment in required if fragment not in landing]
    assert not missing, f'Prometheus landing hero is missing compact context elements: {missing}'
    assert 'Review validated metrics sources, query contracts' not in landing


def test_scope_coverage_uses_bind_existing_source_component() -> None:
    landing = LANDING.read_text(encoding='utf-8')
    component = (ROOT / 'app/templates/components/integration_coverage.html').read_text(encoding='utf-8')
    content = (ROOT / 'app/templates/components/integration_coverage_content.html').read_text(encoding='utf-8')

    assert 'integration_coverage.render' in landing
    assert 'Operational Scopes Without a Prometheus Source' not in landing
    for fragment in ('Integration Coverage', 'Bind operational scopes to existing {{ provider.label }} sources.'):
        assert fragment in component
    for fragment in ('Bind Source', 'Review Binding'):
        assert fragment in content


def test_registration_workspace_matches_alertmanager_information_hierarchy() -> None:
    form = FORM.read_text(encoding='utf-8')

    required = (
        'Registration Posture',
        'Pre-save Requirements',
        "page_hero.context_metric('plug-zap', 'Before Save'",
        "page_hero.context_metric('scan-search', 'After Save'",
        "'Prometheus Registration Flow'",
        "information_guide_card.render(\n                'Compatibility Detection'",
        "context_guidance_card.render(\n                    'After Registration'",
        "related_page_card.render(\n                    'Kubernetes Analytics'",
    )
    missing = [fragment for fragment in required if fragment not in form]
    assert not missing, f'Prometheus registration workspace is incomplete: {missing}'
    assert 'Connection Versus Capability' not in form


def test_compatibility_detection_values_are_clean_and_explicit() -> None:
    forms = FORMS.read_text(encoding='utf-8')

    required = (
        "('automatic', 'Automatic — Direct Prometheus')",
        "('manual', 'Manual — Prometheus-Compatible Gateway')",
        "('', 'Select Source Version')",
        "('2', 'Prometheus v2')",
        "('3', 'Prometheus v3')",
    )
    missing = [fragment for fragment in required if fragment not in forms]
    assert not missing, f'Compatibility Detection choices are incomplete: {missing}'
    assert 'Prometheus-compatible intermediary' not in forms
    assert 'Prometheus 2.x' not in forms
    assert 'Prometheus 3.x' not in forms


def test_related_analytics_card_uses_intrinsic_height() -> None:
    related = RELATED.read_text(encoding='utf-8')

    assert 'class="flex flex-col rounded-2xl' in related
    assert 'class="mt-6"' in related
    assert 'h-full' not in related
    assert 'mt-auto' not in related


def test_delete_lifecycle_url_is_defensive_and_explicitly_registered() -> None:
    routes = ROUTES.read_text(encoding='utf-8')
    detail = DETAIL.read_text(encoding='utf-8')

    required_routes = (
        'def _optional_endpoint_url(endpoint: str, **values) -> str | None:',
        'endpoint not in current_app.view_functions',
        "endpoint='delete_instance'",
        "context['delete_instance_url'] = _optional_endpoint_url(",
        "'prometheus.delete_instance'",
    )
    missing = [fragment for fragment in required_routes if fragment not in routes]
    assert not missing, f'Prometheus delete route resilience is incomplete: {missing}'
    scope = (ROOT / 'app/templates/prometheus/partials/_detail_scope.html').read_text(encoding='utf-8')
    assert "url_for('prometheus.delete_instance'" not in detail + scope
    assert 'data-delete-url="{{ delete_instance_url }}"' in scope
    assert 'Delete Unavailable' in scope


def test_all_prometheus_template_endpoints_have_declared_handlers() -> None:
    routes = ROUTES.read_text(encoding='utf-8')
    declared = set(re.findall(r'^def ([a-zA-Z_]\w*)\(', routes, flags=re.MULTILINE))
    explicit = set(re.findall(r"endpoint=['\"]([a-zA-Z_]\w*)['\"]", routes))
    declared |= explicit

    references: dict[str, set[str]] = {}
    template_paths = list((ROOT / 'app/templates/prometheus').rglob('*.html'))
    template_paths += list((ROOT / 'app/templates/integrations/prometheus').rglob('*.html'))
    template_paths.append(LANDING)
    for path in template_paths:
        source = path.read_text(encoding='utf-8')
        for endpoint in re.findall(r"url_for\(['\"]prometheus\.([a-zA-Z_]\w*)", source):
            references.setdefault(endpoint, set()).add(str(path.relative_to(ROOT)))

    missing = {endpoint: sorted(paths) for endpoint, paths in references.items() if endpoint not in declared}
    assert not missing, f'Prometheus templates reference undeclared endpoints: {missing}'


def test_alignment_audit_records_the_regression_contract() -> None:
    audit = AUDIT.read_text(encoding='utf-8')

    required = (
        'Duplicate landing actions',
        'Hero context was too verbose',
        'Compatibility Detection',
        'After Registration',
        'Related Analytics Workspace stretched vertically',
        'Delete URL could break page rendering',
        'every Prometheus template route reference maps to a declared Prometheus handler',
    )
    missing = [fragment for fragment in required if fragment not in audit]
    assert not missing, f'Prometheus alignment audit is incomplete: {missing}'
