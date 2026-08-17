from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_provider_details_share_canonical_lifecycle_language() -> None:
    details = {
        'Kubernetes': read('app/templates/integrations/kubernetes/detail.html'),
        'Metrics Source': read('app/templates/metrics/instance_detail.html'),
        'Alertmanager': read('app/templates/alertmanager/instance_detail.html'),
        'MinIO': read('app/templates/minio/instance_detail.html'),
    }

    for provider, source in details.items():
        for label in ('Configuration', 'Validation & Capabilities', 'Runtime & History'):
            assert label in source, (provider, label)
        assert 'Produced by Full Validation' in source, provider
        assert 'Validated Capabilities' in source, provider

    assert 'Inventory & Lifecycle' in details['Kubernetes']
    assert 'Inventory & Lifecycle' in details['MinIO']
    assert 'Bindings & Consumers' in details['Metrics Source']
    assert 'Bindings & Consumers' in details['Alertmanager']


def test_provider_validation_workspaces_use_full_validation_and_shared_readiness() -> None:
    validation = {
        'Kubernetes': read('app/templates/integrations/kubernetes/partials/_capability_workspace.html'),
        'Metrics Source': read('app/templates/metrics/partials/_detail_validation_content.html'),
        'Alertmanager': read('app/templates/alertmanager/partials/_detail_validation_content.html'),
        'MinIO': read('app/templates/minio/partials/_detail_validation.html'),
    }

    for provider, source in validation.items():
        assert f'{provider} Full Validation' in source, provider
        assert 'Run Full Validation' in source, provider
        assert 'capability_readiness.render(' in source, provider

    assert 'Metrics Source Core Validation' not in validation['Metrics Source']
    assert 'Alertmanager Core Validation' not in validation['Alertmanager']


def test_provider_runtime_decision_is_shared_for_observability_and_minio() -> None:
    for provider, path in (
        ('Metrics Source', 'app/templates/metrics/partials/_runtime_panel.html'),
        ('Alertmanager', 'app/templates/alertmanager/partials/_runtime_panel.html'),
        ('MinIO', 'app/templates/minio/partials/_detail_runtime.html'),
    ):
        source = read(path)
        assert 'integrations/components/_runtime_decision.html' in source, provider
        assert 'runtime_decision.render(' in source, provider
        assert 'Runtime Health & Diagnostics' in source, provider

    minio = read('app/templates/minio/partials/_detail_runtime.html')
    assert 'Inventory Sync owns committed assets' in minio
    assert 'data-kaori-minio-runtime-evidence' in minio


def test_binding_modal_footer_actions_remain_single_line_and_resilient() -> None:
    modal = read('app/templates/integrations/components/_observability_binding_modal.html')
    assert 'min-w-0 flex-1 text-xs leading-5 text-content-muted' in modal
    assert 'flex shrink-0 items-center justify-end gap-2' in modal
    assert 'whitespace-nowrap rounded-lg bg-kaori-primary' in modal
    assert 'whitespace-nowrap rounded-lg border border-outline-default' in modal
