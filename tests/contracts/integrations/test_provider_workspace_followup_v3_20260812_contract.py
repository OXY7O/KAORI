from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_metrics_source_empty_states_match_alertmanager_binding_style() -> None:
    registry = read('app/templates/integrations/observability/metrics_source/partials/_binding_registry.html')
    scope = read('app/templates/integrations/observability/metrics_source/partials/_detail_scope.html')

    assert 'No Consumer Bindings' in registry
    assert 'components/states/_empty_state.html' in registry
    assert 'No Consumer Bindings' in registry
    assert 'query-routing preference' in registry
    assert 'metrics-source-binding-registry' in registry
    assert 'Metrics Identity' in registry

    assert 'No Source Resolution Is Available Yet' in scope
    assert 'Create a binding to evaluate metrics-source resolution and analytics eligibility.' in scope
    assert 'No Resolution Context Yet' not in scope


def test_provider_edit_heroes_share_one_kaori_contract() -> None:
    shared = read('app/templates/integrations/components/_provider_edit_hero.html')
    templates = {
        'Metrics Source': read('app/templates/integrations/observability/metrics_source/instance_form.html'),
        'Alertmanager': read(
            'app/templates/integrations/observability/alert_source/providers/alertmanager/instance_form.html'
        ),
        'MinIO': read('app/templates/integrations/storage/object_storage/providers/minio/instance_form.html'),
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

    assert "'Edit ' ~ metrics_source_label ~ ' Connection'" in templates['Metrics Source']
    assert 'Edit Alertmanager Connection' in templates['Alertmanager']
    assert 'Edit MinIO Connection' in templates['MinIO']


def test_observability_edit_success_returns_to_registry_for_browser_and_htmx() -> None:
    metrics_source = read('app/integrations/observability/metrics_source/application/edit_web.py')
    alertmanager = read('app/integrations/observability/alert_source/providers/alertmanager/application/edit_web.py')
    minio = read('app/integrations/storage/object_storage/providers/minio/application/routes.py')

    assert "registry_url = url_for('integrations.metrics_sources')" in metrics_source
    assert "response.headers['HX-Redirect'] = registry_url" in metrics_source
    assert 'return redirect(registry_url)' in metrics_source
    assert (
        "'#configuration'"
        not in metrics_source.split("event_type='metrics_source_updated'", 1)[1].split('context =', 1)[0]
    )

    assert "registry_url = url_for('integrations.alertmanager')" in alertmanager
    assert "response.headers['HX-Redirect'] = registry_url" in alertmanager
    assert 'return redirect(registry_url)' in alertmanager
    assert (
        "'#configuration'"
        not in alertmanager.split("event_type='alertmanager_instance_updated'", 1)[1].split('context =', 1)[0]
    )

    assert "return redirect(url_for('minio.index', tab='registry'))" in minio


def test_minio_edit_secret_can_preserve_existing_credential() -> None:
    forms = read('app/integrations/storage/object_storage/providers/minio/application/forms.py')
    template = read('app/templates/integrations/storage/object_storage/providers/minio/instance_form.html')

    secret_field = forms.split('secret_key = PasswordField(', 1)[1].split('region = StringField(', 1)[0]
    assert 'DataRequired()' not in secret_field
    assert 'validators=[Length(max=4096)]' in secret_field
    assert 'def validate_secret_key' in forms
    assert 'self.existing_instance is None' in forms
    assert 'current.secret_key' in forms
    assert 'Blank Preserves Existing Secret Key.' in template


def test_minio_compatibility_is_product_specific_and_range_aware() -> None:
    compatibility = read('app/integrations/storage/object_storage/providers/minio/compatibility.py')
    capabilities = read('app/integrations/storage/object_storage/providers/minio/capabilities.py')
    provider_catalog = read('app/definitions/catalogs/integrations/storage/object_storage/contract.yaml')
    client = read('app/integrations/storage/object_storage/providers/minio/client.py')
    adapter = read('app/integrations/storage/object_storage/providers/minio/adapter.py')
    configuration = read(
        'app/templates/integrations/storage/object_storage/providers/minio/partials/_detail_configuration.html'
    )
    validation = read(
        'app/templates/integrations/storage/object_storage/providers/minio/partials/_detail_validation.html'
    )

    for marker in (
        'SUPPORTED_RELEASE_MIN',
        'SUPPORTED_RELEASE_MAX',
        'supported_range_label',
        'PRODUCT_PROFILE_CATALOG',
        'compatibility_policy_view',
        "integration_provider_document('object_storage')",
    ):
        assert marker in compatibility
    assert 'key: minio' in provider_catalog
    assert 'key: astor' in provider_catalog
    assert 'compatibility_profiles: []' in provider_catalog

    assert 'COMPATIBILITY_PROFILES' in capabilities
    assert 'key: minio-release-2024-08-03' in provider_catalog
    assert "if 'astor' in normalized_header" in client
    assert 'evaluate_minio_release(instance.declared_release, product=result.product)' in adapter
    assert 'Supported Range · ' in configuration
    assert 'for the qualified release.' in validation
    assert 'Profile · ' in validation
    assert 'Product · ' not in validation


def test_kubernetes_compact_readiness_import_is_wired() -> None:
    adapter = read('app/integrations/orchestration/container_orchestrator/adapters/kubernetes_api/adapter.py')
    assert 'app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.messages' in adapter
    assert 'compact_readiness_reasons' in adapter
    assert 'compact_readiness_reasons(discovery.get(' in adapter
