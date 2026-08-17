from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []

    backend = read('app/kubernetes/inventory/resources/namespaces.py')
    routes = read('app/kubernetes/inventory/routes.py')
    collector = read('app/kubernetes/inventory/collectors/configuration.py')
    persistence = read('app/kubernetes/inventory/persistence.py')
    workspace = read('app/templates/kubernetes/inventory/namespaces/partials/_page_workspace.html')
    table_card = read('app/templates/kubernetes/inventory/namespaces/partials/_table_card.html')
    table_content = read('app/templates/kubernetes/inventory/namespaces/partials/_table_content.html')
    summary = read('app/templates/kubernetes/inventory/namespaces/partials/_summary_cards.html')
    detail = read('app/templates/kubernetes/inventory/namespaces/partials/_namespace_detail_content.html')
    standard = read('docs/design/patterns/KUBERNETES_NAMESPACE_INVENTORY.md')
    audit = read('docs/design/audits/KUBERNETES_NAMESPACE_INVENTORY_ALIGNMENT_AUDIT_2026_08.md')
    quality_gate = read('scripts/quality_gate.sh')

    require(
        'filter_current_generation(query, NamespaceInventory)' in backend,
        'Namespace rows must use the committed generation.',
        errors,
    )
    require(
        "if status == 'Unknown'" in backend,
        'Unknown lifecycle evidence must be filterable.',
        errors,
    )
    require(
        'NamespaceInventory.status.is_(None)' in backend,
        'Unknown filtering must include missing phase evidence.',
        errors,
    )
    require(
        "return normalized.title() if normalized else 'Not Explicitly Set'" in backend,
        'Absent PSA labels must not imply inheritance.',
        errors,
    )
    require(
        "RESOURCE_QUOTA_EVIDENCE_KEY = 'inventory.resourcequotas'" in backend,
        'ResourceQuota evidence must have a canonical key.',
        errors,
    )
    require(
        'quota_count = quota_counts.get(key, 0) if quota_state == COLLECTED else None' in backend,
        'ResourceQuota zero must remain distinct from unavailable evidence.',
        errors,
    )
    require(
        "'title': 'Validate Namespace Control Evidence'" in backend,
        'Incomplete control evidence must produce explicit guidance.',
        errors,
    )
    require(
        'db.session.query(Cluster.name).filter(Cluster.id == cluster_id).scalar()' in backend,
        'Scope identity must not depend on filtered rows.',
        errors,
    )

    require(
        'configured_hard = (spec.hard or {}) if spec else {}' in collector,
        'ResourceQuota configured limits must come from spec.hard.',
        errors,
    )
    require(
        "getattr(exc, 'status', None) in {403, 404}" in collector,
        'ResourceQuota permission/API failures must be classified.',
        errors,
    )
    require(
        "committed_evidence['inventory.resourcequotas'] = collection_evidence" in persistence,
        'ResourceQuota collection state must be committed.',
        errors,
    )

    require(
        "for resource in ('nodes', 'namespaces', 'configuration', 'workloads', 'pods', 'services', 'ingresses', 'storage')"
        in routes,
        'Namespace workspace partial must be registered.',
        errors,
    )
    require(
        'id="namespaces-page-workspace"' in workspace,
        'Namespace filters must own a complete page workspace.',
        errors,
    )
    require(
        'kubernetes/inventory/components/_data_freshness.html' in workspace,
        'Snapshot Context must refresh with Namespace scope.',
        errors,
    )
    require(
        'hx-target="#namespaces-page-workspace"' in table_card,
        'Namespace filters must refresh Hero, snapshot, posture, and table.',
        errors,
    )
    require(
        'name="partial_mode" value="page_workspace"' in table_card,
        'Namespace filters must select the workspace partial.',
        errors,
    )
    require(
        'aria-label="Namespace inventory filters"' in table_card,
        'Namespace filters require an accessible label.',
        errors,
    )

    require(
        '<caption class="sr-only">' in table_content,
        'Namespace table requires an accessible caption.',
        errors,
    )
    require(
        table_content.count('scope="col"') == 6,
        'Namespace table must expose six scoped columns.',
        errors,
    )
    require(
        'namespace.age' not in table_content,
        'Age belongs to Namespace detail, not the compact table.',
        errors,
    )
    require(
        'inventory.quota_reported_namespaces < inventory.total_namespaces' in summary,
        'Quota posture must show incomplete evidence.',
        errors,
    )
    require(
        'inventory.default_service_account_not_reported' in summary,
        'ServiceAccount evidence gaps must remain visible.',
        errors,
    )
    require(
        "namespace.quota_collection_state != 'Collected'" in detail,
        'Detail must separate quota absence from collection failure.',
        errors,
    )
    require(
        'ResourceQuota Evidence Not Reported' in detail,
        'Detail must explain unavailable quota evidence.',
        errors,
    )
    require(
        'does not infer a cluster-level Pod Security Admission default' in detail,
        'Detail copy must avoid unsupported PSA inheritance.',
        errors,
    )

    require(
        'Kubernetes Namespace Inventory Standard' in standard,
        'Namespace standard documentation is missing.',
        errors,
    )
    require(
        'ResourceQuota collection evidence' in audit,
        'Namespace alignment audit must record ResourceQuota evidence.',
        errors,
    )
    require(
        'verify_namespace_inventory_standard.py' in quality_gate,
        'Namespace verifier must run in the quality gate.',
        errors,
    )

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    print(
        'KAORI Namespace Inventory Standard audit passed: committed scope, '
        'lifecycle filters, control evidence, PSA semantics, compact table, '
        'detail guidance, accessibility, and documentation are aligned.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
