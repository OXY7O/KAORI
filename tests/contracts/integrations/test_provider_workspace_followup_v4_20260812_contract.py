from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_validation_polling_is_isolated_from_nested_registry_indicators() -> None:
    poller = read('app/templates/integrations/components/_validation_poller.html')
    assert 'data-kaori-validation-poller' in poller
    assert 'class="hidden"' in poller
    assert 'hx-target="{{ target }}"' in poller
    assert 'hx-swap="outerHTML"' in poller

    targets = {
        'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_capability_workspace.html': '#kubernetes-capability-workspace',
        'app/templates/integrations/observability/metrics_source/partials/_detail_validation_content.html': '#metrics-source-validation-workspace',
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_detail_validation_content.html': '#alertmanager-validation-workspace',
        'app/templates/integrations/storage/object_storage/providers/minio/partials/_detail_validation.html': '#minio-core-validation',
    }
    for relative, target in targets.items():
        text = read(relative)
        section_open = text.split('>{% call connection_validation_header.render', 1)[0]
        assert 'validation_poller.render(' in text, relative
        assert target in text, relative
        assert 'hx-get=' not in section_open.rsplit('<section', 1)[-1], relative
        assert 'hx-target="this"' not in section_open.rsplit('<section', 1)[-1], relative


def test_validation_has_one_provider_job_loading_surface_but_registry_keeps_own_action_loader() -> None:
    pages = {
        'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_capability_workspace.html': 'kubernetes-validation-loading',
        'app/templates/integrations/observability/metrics_source/partials/_detail_validation_content.html': 'metrics-source-validation-loading',
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_detail_validation_content.html': 'alertmanager-validation-loading',
        'app/templates/integrations/storage/object_storage/providers/minio/partials/_detail_validation.html': 'minio-validation-loading',
    }
    for relative, loading_id in pages.items():
        text = read(relative)
        assert f"loading_id='{loading_id}'" in text or f'loading_id="{loading_id}"' in text, relative
        assert f'hx-indicator="#{loading_id}"' in text, relative

    # Capability Registry action loaders stay independent for search/filter/pagination only.
    assert 'kubernetes-capability-loading' in read(
        'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_capability_registry.html'
    )
    assert 'metrics-source-capability-loading' in read(
        'app/templates/integrations/observability/metrics_source/partials/_capability_registry.html'
    )
    assert 'alertmanager-capability-loading' in read(
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_capability_registry.html'
    )
    assert 'minio-capability-loading' in read(
        'app/templates/integrations/storage/object_storage/providers/minio/partials/_capability_registry.html'
    )


def test_observability_edit_success_queues_registry_toast_even_for_htmx_redirect() -> None:
    metrics_source = read('app/integrations/observability/metrics_source/application/edit_web.py')
    alertmanager = read('app/integrations/observability/alert_source/providers/alertmanager/application/edit_web.py')

    p_success = metrics_source.split("event_type='metrics_source_updated'", 1)[1].split('if is_htmx:', 1)[0]
    a_success = alertmanager.split("event_type='alertmanager_instance_updated'", 1)[1].split('if is_htmx:', 1)[0]

    assert "title=f'{source_label} Connection Updated'" in p_success
    assert 'source_label = provider_definition(instance.provider_key).label' in metrics_source
    assert 'queue_feedback=True' in p_success
    assert "title='Alertmanager Connection Updated'" in a_success
    assert 'queue_feedback=True' in a_success


def test_minio_authority_boundary_keeps_only_authority_metadata() -> None:
    configuration = read(
        'app/templates/integrations/storage/object_storage/providers/minio/partials/_detail_configuration.html'
    )
    metadata = configuration.split('{% set operational_metadata = [', 1)[1].split('] %}', 1)[0]

    assert 'S3 API Authority' in metadata
    assert 'Read-Only Discovery' in metadata
    assert 'Region · ' in metadata
    assert 'Addressing' in metadata
    assert 'Product · ' not in metadata
    assert 'Supported Range · ' not in metadata


def test_minio_readiness_keeps_range_readable_without_long_range_badge() -> None:
    validation = read(
        'app/templates/integrations/storage/object_storage/providers/minio/partials/_detail_validation.html'
    )
    metadata = validation.split('{% set capability_metadata = [', 1)[1].split('] %}', 1)[0]
    shared = read('app/templates/integrations/components/_capability_readiness.html')

    assert 'Product · ' not in metadata
    assert 'Profile · ' in metadata
    assert 'Supported Range · ' not in metadata
    assert 'Qualified range: ' in validation
    assert 'sm:grid-cols-[minmax(12rem,1fr)_minmax(0,24rem)]' in shared


def test_provider_readiness_metadata_uses_one_concise_profile_identity() -> None:
    templates = (
        'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_capability_workspace.html',
        'app/templates/integrations/observability/metrics_source/partials/_detail_validation_content.html',
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_detail_validation_content.html',
        'app/templates/integrations/storage/object_storage/providers/minio/partials/_detail_validation.html',
    )
    for relative in templates:
        source = read(relative)
        metadata = source.split('{% set capability_metadata = [', 1)[1].split('] %}', 1)[0]
        assert 'Profile · ' in metadata, relative
        assert 'Compatibility · ' not in metadata, relative
        assert 'Core Profile · ' not in metadata, relative
        assert 'Core profile · ' not in metadata, relative
        assert 'Product · ' not in metadata, relative
