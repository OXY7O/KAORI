from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_namespace_filters_refresh_complete_scope_and_include_unknown() -> None:
    routes = read('app/inventory/kubernetes/routes.py')
    backend = read('app/inventory/kubernetes/resources/namespaces.py')
    table = read('app/templates/inventory/kubernetes/namespaces/partials/_table_card.html')
    workspace = read('app/templates/inventory/kubernetes/namespaces/partials/_page_workspace.html')

    assert (
        "for resource in ('nodes', 'namespaces', 'configuration', 'workloads', 'pods', 'services', 'ingresses', 'storage')"
        in routes
    )
    assert 'hx-target="#namespaces-page-workspace"' in table
    assert 'name="partial_mode" value="page_workspace"' in table
    assert 'id="namespaces-page-workspace"' in workspace
    assert 'inventory/kubernetes/components/_data_freshness.html' in workspace
    assert '_normalise_namespace_status(row[0])[0]' in backend
    assert "if status == 'Unknown'" in backend
    assert 'NamespaceInventory.status.is_(None)' in backend


def test_namespace_scope_label_does_not_depend_on_filtered_rows() -> None:
    routes = read('app/inventory/kubernetes/routes.py')
    backend = read('app/inventory/kubernetes/resources/namespaces.py')

    assert "inventory['scope_label'] = _inventory_scope_label(clusters, cluster_id)" in routes
    assert 'def _inventory_scope_label(' in routes
    assert 'db.session.query(Cluster.name).filter(Cluster.id == cluster_id).scalar()' in backend


def test_namespace_control_evidence_distinguishes_zero_from_not_reported() -> None:
    backend = read('app/inventory/kubernetes/resources/namespaces.py')
    summary = read('app/templates/inventory/kubernetes/namespaces/partials/_summary_cards.html')
    detail = read('app/templates/inventory/kubernetes/namespaces/partials/_namespace_detail_content.html')
    persistence = read('app/inventory/kubernetes/persistence.py')

    assert "RESOURCE_QUOTA_EVIDENCE_KEY = 'inventory.resourcequotas'" in backend
    assert 'quota_count = quota_counts.get(key, 0) if quota_state == COLLECTED else None' in backend
    assert "committed_evidence['inventory.resourcequotas'] = collection_evidence" in persistence
    assert 'inventory.quota_reported_namespaces < inventory.total_namespaces' in summary
    assert 'inventory.default_service_account_not_reported' in summary
    assert "namespace.quota_collection_state != 'Collected'" in detail
    assert 'ResourceQuota Evidence Not Reported' in detail
    assert "'title': 'Validate Namespace Control Evidence'" in backend


def test_namespace_psa_copy_does_not_infer_cluster_defaults() -> None:
    backend = read('app/inventory/kubernetes/resources/namespaces.py')
    detail = read('app/templates/inventory/kubernetes/namespaces/partials/_namespace_detail_content.html')

    assert "return normalized.title() if normalized else 'Not Explicitly Set'" in backend
    assert "'Inherited'" not in backend[backend.index('def _psa_label') :]
    assert 'does not infer a cluster-level Pod Security Admission default' in detail


def test_namespace_compact_table_keeps_age_in_detail_only() -> None:
    table = read('app/templates/inventory/kubernetes/namespaces/partials/_table_content.html')
    detail = read('app/templates/inventory/kubernetes/namespaces/partials/_namespace_detail_content.html')

    assert '<caption class="sr-only">' in table
    assert table.count('scope="col"') == 6
    assert 'namespace.age' not in table
    assert "('Age', namespace.age" in detail


def test_namespace_resourcequota_collector_uses_configured_spec_and_evidence() -> None:
    collector = read('app/inventory/kubernetes/collectors/configuration.py')

    assert 'with_evidence: bool = False' in collector
    assert 'evidence = COLLECTED' in collector
    assert "getattr(exc, 'status', None) in {403, 404}" in collector
    assert 'configured_hard = (spec.hard or {}) if spec else {}' in collector
    assert 'for key, value in (configured_hard or observed_hard).items()' in collector
    assert 'return (items, evidence) if with_evidence else items' in collector


def test_namespace_inventory_standard_is_documented_and_gated() -> None:
    standard = read('docs/design/patterns/KUBERNETES_NAMESPACE_INVENTORY.md')
    audit = read('docs/design/audits/KUBERNETES_NAMESPACE_INVENTORY_ALIGNMENT_AUDIT_2026_08.md')
    quality_gate = read('scripts/quality_gate.sh')

    assert 'Kubernetes Namespace Inventory Standard' in standard
    assert 'Not Explicitly Set' in standard
    assert 'ResourceQuota collection evidence' in audit
    assert 'verify_namespace_inventory_standard.py' in quality_gate


def test_namespace_detail_distinguishes_configuration_zero_from_unreported() -> None:
    detail = read('app/templates/inventory/kubernetes/namespaces/partials/_namespace_detail_content.html')
    resource = read('app/inventory/kubernetes/resources/namespaces.py')

    assert 'Configuration Object Evidence Not Reported' in detail
    assert "'config_maps': None" not in resource
    assert "CONFIGMAP_EVIDENCE_KEY = 'inventory.configmaps'" in resource
    assert "SECRET_EVIDENCE_KEY = 'inventory.secrets'" in resource
    assert "'control_evidence_display': f'{reported_controls}/5 Reported'" in resource
