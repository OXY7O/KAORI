from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


PROVIDER_EDIT_FORMS = {
    'metrics_source': 'app/templates/integrations/observability/metrics_source/instance_form.html',
    'alertmanager': 'app/templates/integrations/observability/alert_source/providers/alertmanager/instance_form.html',
    'minio': 'app/templates/integrations/storage/object_storage/providers/minio/instance_form.html',
    'harbor': 'app/templates/integrations/registry/providers/harbor/instance_form.html',
}


def test_kubernetes_edit_reuses_shared_provider_edit_hero() -> None:
    edit = read('app/templates/kubernetes/cluster/edit.html')

    assert 'integrations/components/_provider_edit_hero.html' in edit
    assert 'provider_edit_hero.render(' in edit
    assert 'kubernetes/cluster/partials/_page_header.html' not in edit
    assert 'Edit Kubernetes Connection' in edit
    assert 'Save Changes' in edit
    assert 'Test credentials before saving. Connection or TLS changes require Full Validation.' in edit
    assert 'How saved changes restore operational readiness.' in edit


def test_all_current_provider_edit_forms_use_embedded_action_bar() -> None:
    kubernetes_form = read('app/templates/kubernetes/cluster/partials/_form.html')
    assert "aria_label='Kubernetes Configuration Actions', embedded=true" in kubernetes_form
    assert "action_button.classes('secondary')" in kubernetes_form
    assert "action_button.classes('primary')" in kubernetes_form

    for provider, path in PROVIDER_EDIT_FORMS.items():
        source = read(path)
        assert 'provider_edit_hero.render(' in source, provider
        assert 'embedded=true' in source, provider
        assert "action_button.classes('secondary')" in source, provider
        assert "action_button.classes('primary')" in source, provider


def test_edit_form_operator_language_uses_full_validation() -> None:
    kubernetes = read('app/templates/kubernetes/cluster/edit.html')
    metrics = read(PROVIDER_EDIT_FORMS['metrics_source'])
    alertmanager = read(PROVIDER_EDIT_FORMS['alertmanager'])
    minio = read(PROVIDER_EDIT_FORMS['minio'])
    harbor = read(PROVIDER_EDIT_FORMS['harbor'])

    assert (
        "('Run Full Validation', 'Rebuild Kubernetes API, capability, RBAC, and runtime evidence before operational use.')"
        in kubernetes
    )
    assert (
        "('Run Full Validation', 'Rebuild provider compatibility and adapter and query-contract readiness evidence.')"
        in metrics
    )
    assert 'Saving changes does not establish readiness until Full Validation succeeds.' in metrics
    assert (
        "('Run Full Validation', 'Rebuild Alertmanager API compatibility and provider readiness evidence.')"
        in alertmanager
    )
    assert 'Saving changes does not establish readiness until Full Validation succeeds.' in alertmanager
    assert (
        "('Run Full Validation', 'Rebuild MinIO compatibility and provider capability evidence after saving.')" in minio
    )
    assert 'Save changes, then run Full Validation.' in minio
    assert "('Run Full Validation', 'Rebuild compatibility and capability evidence after saving.')" in harbor


def test_reviewed_minio_edit_copy_stays_compact() -> None:
    minio = read(PROVIDER_EDIT_FORMS['minio'])

    assert 'Update S3 access while preserving assets, bindings, and validation.' in minio
    assert 'How changes restore object-storage readiness.' in minio
    assert 'How connection changes return this object-storage provider to an operationally ready state.' not in minio


def test_provider_edit_form_standard_is_documented() -> None:
    standard = read('docs/design/components/INTEGRATIONS_WORKSPACE_STANDARD.md')

    assert '**Provider edit-form parity.**' in standard
    assert 'integrations/components/_provider_edit_hero.html' in standard
    assert 'components/form_action_bar.html' in standard
    assert 'embedded=true' in standard
    assert 'components/action_button.html' in standard
    assert 'User-visible edit guidance uses **Full Validation**' in standard
