from app.reports.generated.service import get_generated_scope_labels


def test_registry_scope_is_integration_and_has_no_namespace() -> None:
    assert get_generated_scope_labels('registry_integration', None) == ('Artifact Registry', 'Integration Scope')
    assert get_generated_scope_labels('registry_integration', 'ignored') == ('Artifact Registry', 'Integration Scope')


def test_other_scope_families_preserve_their_existing_labels() -> None:
    assert get_generated_scope_labels('object_storage_system', None) == (
        'Object Storage System',
        'System Scope',
    )
    assert get_generated_scope_labels('kubernetes_cluster', 'production') == (
        'Kubernetes Cluster',
        'production',
    )
    assert get_generated_scope_labels('kubernetes_cluster', None) == (
        'Kubernetes Cluster',
        'All Namespaces',
    )
