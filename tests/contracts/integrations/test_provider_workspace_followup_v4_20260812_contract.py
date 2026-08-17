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
        'app/templates/integrations/kubernetes/partials/_capability_workspace.html': '#kubernetes-capability-workspace',
        'app/templates/prometheus/partials/_detail_validation_content.html': '#prometheus-validation-workspace',
        'app/templates/alertmanager/partials/_detail_validation_content.html': '#alertmanager-validation-workspace',
        'app/templates/minio/partials/_detail_validation.html': '#minio-core-validation',
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
        'app/templates/integrations/kubernetes/partials/_capability_workspace.html': 'kubernetes-validation-loading',
        'app/templates/prometheus/partials/_detail_validation_content.html': 'prometheus-validation-loading',
        'app/templates/alertmanager/partials/_detail_validation_content.html': 'alertmanager-validation-loading',
        'app/templates/minio/partials/_detail_validation.html': 'minio-validation-loading',
    }
    for relative, loading_id in pages.items():
        text = read(relative)
        assert f"loading_id='{loading_id}'" in text or f'loading_id="{loading_id}"' in text, relative
        assert f'hx-indicator="#{loading_id}"' in text, relative

    # Capability Registry action loaders stay independent for search/filter/pagination only.
    assert 'kubernetes-capability-loading' in read(
        'app/templates/integrations/kubernetes/partials/_capability_registry.html'
    )
    assert 'prometheus-capability-loading' in read('app/templates/prometheus/partials/_capability_registry.html')
    assert 'alertmanager-capability-loading' in read('app/templates/alertmanager/partials/_capability_registry.html')
    assert 'minio-capability-loading' in read('app/templates/minio/partials/_capability_registry.html')


def test_observability_edit_success_queues_registry_toast_even_for_htmx_redirect() -> None:
    prometheus = read('app/prometheus/edit_web.py')
    alertmanager = read('app/alertmanager/edit_web.py')

    p_success = prometheus.split("event_type='prometheus_instance_updated'", 1)[1].split('if is_htmx:', 1)[0]
    a_success = alertmanager.split("event_type='alertmanager_instance_updated'", 1)[1].split('if is_htmx:', 1)[0]

    assert "title=f'{source_label} Connection Updated'" in p_success
    assert "source_label = 'Thanos Query' if instance.source_type == 'thanos' else 'Prometheus'" in prometheus
    assert 'queue_feedback=True' in p_success
    assert "title='Alertmanager Connection Updated'" in a_success
    assert 'queue_feedback=True' in a_success


def test_minio_authority_boundary_keeps_only_authority_metadata() -> None:
    configuration = read('app/templates/minio/partials/_detail_configuration.html')
    metadata = configuration.split('{% set operational_metadata = [', 1)[1].split('] %}', 1)[0]

    assert 'S3 API Authority' in metadata
    assert 'Read-Only Discovery' in metadata
    assert 'Region · ' in metadata
    assert 'Addressing' in metadata
    assert 'Product · ' not in metadata
    assert 'Supported Range · ' not in metadata


def test_minio_readiness_keeps_range_readable_without_long_range_badge() -> None:
    validation = read('app/templates/minio/partials/_detail_validation.html')
    metadata = validation.split('{% set capability_metadata = [', 1)[1].split('] %}', 1)[0]
    shared = read('app/templates/integrations/components/_capability_readiness.html')

    assert 'Product · ' in metadata
    assert 'Profile · ' in metadata
    assert 'Supported Range · ' not in metadata
    assert 'Qualified range: ' in validation
    assert 'sm:grid-cols-[minmax(12rem,1fr)_minmax(0,24rem)]' in shared
