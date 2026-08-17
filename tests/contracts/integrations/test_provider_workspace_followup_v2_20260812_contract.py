from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_full_validation_loader_matches_runtime_history_loading_bar_standard() -> None:
    header = read('app/templates/components/connection_validation_header.html')
    history = read('app/templates/integrations/partials/_runtime_history.html')

    assert 'components/loading_bar.html' in header
    assert 'components/loading_bar.html' in history
    assert 'loading_bar.render(loading_id' in header
    assert 'loading_bar.render(runtime_history_loading_id' in history

    providers = {
        'kubernetes': 'app/templates/integrations/kubernetes/partials/_capability_workspace.html',
        'metrics-source': 'app/templates/metrics/partials/_detail_validation_content.html',
        'alertmanager': 'app/templates/alertmanager/partials/_detail_validation_content.html',
        'minio': 'app/templates/minio/partials/_detail_validation.html',
    }
    registries = {
        'kubernetes': 'app/templates/integrations/kubernetes/partials/_capability_registry.html',
        'metrics-source': 'app/templates/metrics/partials/_capability_registry.html',
        'alertmanager': 'app/templates/alertmanager/partials/_capability_registry.html',
        'minio': 'app/templates/minio/partials/_capability_registry.html',
    }

    for provider, path in providers.items():
        workspace = read(path)
        registry = read(registries[provider])
        loading_id = f'{provider}-validation-loading'
        assert loading_id in workspace
        assert f'hx-indicator="#{loading_id}"' in workspace
        assert 'loading_active=validation_job and validation_job.is_active' in workspace
        assert 'active=validation_job and validation_job.is_active' not in registry


def test_observability_authority_boundary_has_right_side_metadata() -> None:
    operational = read('app/templates/integrations/components/_provider_operational_context.html')
    metrics_source = read('app/templates/metrics/partials/_detail_configuration.html')
    alertmanager = read('app/templates/alertmanager/partials/_detail_configuration.html')

    assert 'data-kaori-authority-boundary-metadata' in operational
    for source in (metrics_source, alertmanager):
        assert 'operational_metadata=operational_metadata' in source

    assert 'Metrics Authority' in metrics_source
    assert 'Read-Only Query' in metrics_source
    assert 'metrics_source_label ~ " Query API"' in metrics_source
    assert 'Alert Routing Authority' in alertmanager
    assert 'Read-Only Discovery' in alertmanager
    assert 'Alertmanager API v2' in alertmanager


def test_kubernetes_legacy_summary_compacts_existing_persisted_copy() -> None:
    messages = read('app/integrations/kubernetes/messages.py')
    adapter = read('app/integrations/kubernetes/adapter.py')
    service = read('app/integrations/service.py')
    runtime_presentation = read('app/integrations/runtime/presentation.py')
    validation = read('app/integrations/kubernetes/validation.py')

    assert "return f'{subject} is in a legacy lifecycle band. Plan an upgrade.'" in messages
    assert 'compact_readiness_reasons(' in adapter
    assert 'compact_readiness_reasons(' in service
    assert 'compact_readiness_reason(detail)' in runtime_presentation
    assert "f'Kubernetes {git_version} is in a legacy lifecycle band. Plan an upgrade.'" in validation
    assert 'Stable APIs remain usable, but upgrade planning is required' not in validation


def test_validation_operational_gate_copy_is_compact_for_every_provider() -> None:
    providers = (
        read('app/templates/integrations/kubernetes/partials/_capability_workspace.html'),
        read('app/templates/metrics/partials/_detail_validation_content.html'),
        read('app/templates/alertmanager/partials/_detail_validation_content.html'),
        read('app/templates/minio/partials/_detail_validation.html'),
    )
    combined = '\n'.join(providers)

    assert 'Resolve required API or RBAC gaps.' in combined
    assert 'Full Validation owns API and RBAC evidence; Runtime Refresh owns live API health.' in combined
    assert 'Revalidate after Kubernetes, API, or RBAC changes.' in combined
    assert 'Core Metrics Source APIs are usable.' in combined
    assert 'Core Alertmanager APIs are usable.' in combined
    assert 'Required MinIO S3 contracts are usable.' in combined

    verbose_copy = (
        'Resolve required API or RBAC evidence before runtime refresh and inventory synchronization.',
        (
            'Full Validation owns API discovery, compatibility selection, capability contracts, and effective RBAC. '
            'Runtime Refresh owns current Kubernetes API reachability, latency, and health.'
        ),
        'No corrective action is required. Revalidate after Kubernetes upgrades, API changes, or RBAC changes.',
        (
            'Full Validation owns provider compatibility and core API evidence only. Binding Validation owns '
            'consumer profiles, selectors, alert identity, and payload evidence. Runtime Refresh owns current '
            'endpoint health.'
        ),
        (
            'Full Validation owns MinIO product identity, compatibility, S3 API, and provider capability evidence. '
            'Runtime Refresh owns current endpoint health. Metrics Source and Alertmanager bindings own consumer-specific '
            'evidence.'
        ),
    )
    for text in verbose_copy:
        assert text not in combined
