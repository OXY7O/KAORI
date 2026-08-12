from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_prometheus_empty_states_match_alertmanager_binding_style() -> None:
    registry = read('app/templates/prometheus/partials/_binding_registry.html')
    scope = read('app/templates/prometheus/partials/_detail_scope.html')

    assert 'No Consumer Bindings' in registry
    assert 'Create a binding to authorize this reusable Prometheus source for one managed consumer asset.' in registry
    assert 'No consumer binding is attached to this Prometheus source yet.' not in registry

    assert 'No Source Resolution Is Available Yet' in scope
    assert 'Create a binding to evaluate metrics-source resolution and analytics eligibility.' in scope
    assert 'No Resolution Context Yet' not in scope


def test_provider_edit_heroes_share_one_kaori_contract() -> None:
    shared = read('app/templates/integrations/components/_provider_edit_hero.html')
    templates = {
        'Prometheus': read('app/templates/prometheus/instance_form.html'),
        'Alertmanager': read('app/templates/alertmanager/instance_form.html'),
        'MinIO': read('app/templates/minio/instance_form.html'),
    }

    for marker in (
        'data-kaori-provider-edit-hero',
        'Configuration Posture',
        'Preserve Identity, Revalidate Changes',
        'Revalidate After Change',
        'Bindings Preserved',
        'After Save',
        'Full Validation',
        'Back to Registry',
    ):
        assert marker in shared

    for provider, template in templates.items():
        assert 'integrations/components/_provider_edit_hero.html' in template, provider
        assert 'provider_edit_hero.render(' in template, provider

    assert 'Edit Prometheus Connection' in templates['Prometheus']
    assert 'Edit Alertmanager Connection' in templates['Alertmanager']
    assert 'Edit MinIO Connection' in templates['MinIO']


def test_observability_edit_success_returns_to_registry_for_browser_and_htmx() -> None:
    prometheus = read('app/prometheus/edit_web.py')
    alertmanager = read('app/alertmanager/edit_web.py')
    minio = read('app/minio/routes.py')

    assert "registry_url = url_for('integrations.prometheus')" in prometheus
    assert "response.headers['HX-Redirect'] = registry_url" in prometheus
    assert "return redirect(registry_url)" in prometheus
    assert "'#configuration'" not in prometheus.split("event_type='prometheus_instance_updated'", 1)[1].split('context =', 1)[0]

    assert "registry_url = url_for('integrations.alertmanager')" in alertmanager
    assert "response.headers['HX-Redirect'] = registry_url" in alertmanager
    assert "return redirect(registry_url)" in alertmanager
    assert "'#configuration'" not in alertmanager.split("event_type='alertmanager_instance_updated'", 1)[1].split('context =', 1)[0]

    assert "return redirect(url_for('minio.index', tab='registry'))" in minio


def test_minio_edit_secret_can_preserve_existing_credential() -> None:
    forms = read('app/minio/forms.py')
    template = read('app/templates/minio/instance_form.html')

    secret_field = forms.split("secret_key = PasswordField(", 1)[1].split('region = StringField(', 1)[0]
    assert 'DataRequired()' not in secret_field
    assert 'validators=[Length(max=4096)]' in secret_field
    assert 'def validate_secret_key' in forms
    assert 'self.existing_instance is None' in forms
    assert 'current.secret_key' in forms
    assert 'Blank Preserves Existing Secret Key.' in template


def test_minio_compatibility_is_product_specific_and_range_aware() -> None:
    compatibility = read('app/integrations/minio/compatibility.py')
    capabilities = read('app/integrations/minio/capabilities.py')
    client = read('app/integrations/minio/client.py')
    adapter = read('app/integrations/minio/adapter.py')
    configuration = read('app/templates/minio/partials/_detail_configuration.html')
    validation = read('app/templates/minio/partials/_detail_validation.html')

    for marker in (
        'SUPPORTED_RELEASE_MIN',
        'SUPPORTED_RELEASE_MAX',
        'supported_range_label',
        'PRODUCT_PROFILE_CATALOG',
        "'minio': MINIO_COMPATIBILITY_PROFILES",
        "'astor': ()",
        'compatibility_policy_view',
    ):
        assert marker in compatibility

    assert 'COMPATIBILITY_PROFILE_KEYS' in capabilities
    assert "if 'astor' in normalized_header" in client
    assert "evaluate_minio_release(instance.declared_release, product=result.product)" in adapter
    assert 'Supported Range · ' in configuration
    assert 'Qualified range: ' in validation
    assert 'Product · ' in validation


def test_kubernetes_compact_readiness_import_is_wired() -> None:
    adapter = read('app/integrations/kubernetes/adapter.py')
    assert 'from app.integrations.kubernetes.messages import compact_readiness_reasons' in adapter
    assert 'compact_readiness_reasons(discovery.get(' in adapter
