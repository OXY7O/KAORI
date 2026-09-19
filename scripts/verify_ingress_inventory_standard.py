from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []

    collector = read('app/kubernetes/inventory/collectors/ingresses.py')
    common = read('app/kubernetes/inventory/collectors/common.py')
    persistence = read('app/kubernetes/inventory/persistence.py')
    model = read('app/models/inventory.py')
    migration = read('migrations/versions/20260805_ingress_inventory_v2.py')
    backend = read('app/kubernetes/inventory/resources/ingresses.py')
    semantics = read('app/kubernetes/inventory/resources/ingress_semantics.py')
    routes = read('app/kubernetes/inventory/routes.py')
    topology = read('app/kubernetes/inventory/topology/node_builder.py')
    payload = read('app/reports/export/payloads/inventory.py')
    xlsx = read('app/reports/export/xlsx/profiles_kubernetes.py')
    workspace = read('app/templates/kubernetes/inventory/ingresses/partials/_page_workspace.html')
    card = read('app/templates/kubernetes/inventory/ingresses/partials/_table_card.html')
    table = read('app/templates/kubernetes/inventory/ingresses/partials/_table_content.html')
    summary = read('app/templates/kubernetes/inventory/ingresses/partials/_summary_cards.html')
    detail = read('app/templates/kubernetes/inventory/ingresses/partials/_ingress_detail_content.html')
    standard = read('docs/design/patterns/KUBERNETES_INGRESS_INVENTORY.md')
    audit = read('docs/design/audits/KUBERNETES_INGRESS_INVENTORY_ALIGNMENT_AUDIT_2026_08.md')
    quality_gate = read('scripts/quality_gate.sh')

    require(
        "evidence = {'inventory.ingresses': collection_state}" in collector,
        'Ingress collection evidence must be explicit.',
        errors,
    )
    require(
        "if getattr(exc, 'status', None) in {403, 404}:" in collector,
        'Ingress compatibility failures must be bounded to 403/404.',
        errors,
    )
    require(
        'raise' in collector and "status', None) in {403, 404}" in collector,
        'Unexpected Ingress API failures must not be hidden.',
        errors,
    )
    require(
        'if metadata is None or spec is None or not namespace or not name:' in collector,
        'Invalid Ingress identities or missing specifications must be skipped.',
        errors,
    )
    for token in (
        "'backend_type': 'Service'",
        "'backend_type': 'Resource'",
        "'backend_type': 'Unknown'",
        "host='All Hosts'",
        "'publication_evidence_reported': publication_reported",
        "'ingress_class_source': ingress_class_source",
    ):
        require(token in collector, f'Ingress collector missing canonical evidence token: {token}', errors)
    require(
        'def _mapping_dict(' in common,
        'Raw provider label and annotation maps must normalize safely.',
        errors,
    )
    require(
        'ingresses, collection_evidence = get_ingresses(' in persistence
        and 'committed_evidence.update(collection_evidence)' in persistence,
        'Ingress collection evidence must be persisted.',
        errors,
    )

    ingress_class = model.split('class IngressInventory', 1)[1].split('class StorageInventory', 1)[0]
    require(
        'host:' not in ingress_class and 'address:' not in ingress_class,
        'Ingress duplicate host/address columns must be removed.',
        errors,
    )
    require('String(255)' in ingress_class, 'Ingress class must support Kubernetes DNS-subdomain length.', errors)
    require("op.drop_column('ingress_inventory', 'host')" in migration, 'Ingress migration must drop host.', errors)
    require(
        "op.drop_column('ingress_inventory', 'address')" in migration, 'Ingress migration must drop address.', errors
    )
    require(
        "'addresses'" in migration and "'hosts'" in migration,
        'Ingress migration must preserve historical compact evidence.',
        errors,
    )

    require(
        'ingress_class == UNSET_CLASS_FILTER' in backend, 'Not Explicitly Set class state must be filterable.', errors
    )
    require(
        'cast(IngressInventory.details, String).ilike(pattern)' in backend,
        'Ingress search must include canonical JSON evidence.',
        errors,
    )
    require(
        "evidence.get('inventory.services')" in backend and "evidence.get('inventory.secrets')" in backend,
        'Ingress reference resolution must use committed collection evidence.',
        errors,
    )
    require(
        'filter_current_generation(ConfigurationInventory.query, ConfigurationInventory)' in backend,
        'TLS Secret references must resolve against committed Secret Inventory.',
        errors,
    )
    require(
        'filter_current_generation(ServiceInventory.query, ServiceInventory)' in backend,
        'Service backends must resolve against committed Service Inventory.',
        errors,
    )

    for token in ('Published', 'Address Pending', 'Not Reported', 'Resource Backend', 'Not Explicitly Set'):
        require(token in semantics, f'Ingress semantics missing state: {token}', errors)
    require(
        'service_collection_state != COLLECTED' in semantics,
        'Missing Service evidence must not be converted to Missing references.',
        errors,
    )
    require(
        'secret_collection_state != COLLECTED' in semantics,
        'Missing Secret evidence must not be converted to Missing references.',
        errors,
    )

    require(
        "for resource in ('nodes', 'namespaces', 'configuration', 'workloads', 'pods', 'services', 'ingresses', 'storage')"
        in routes,
        'Ingress must participate directly in the canonical Inventory workspace mapping.',
        errors,
    )
    require(
        'id="ingresses-page-workspace"' in workspace
        and 'kubernetes/inventory/components/_data_freshness.html' in workspace,
        'Ingress workspace must own Hero and Snapshot Context.',
        errors,
    )
    require(
        'hx-target="#ingresses-page-workspace"' in card and 'name="partial_mode" value="page_workspace"' in card,
        'Ingress filters must refresh the complete workspace.',
        errors,
    )
    require('aria-label="Ingress inventory filters"' in card, 'Ingress filters require an accessible label.', errors)
    require(
        '<caption class="sr-only">' in table and table.count('scope="col"') == 6,
        'Ingress table requires caption and scoped columns.',
        errors,
    )
    require(' · Age ' not in table, 'Age must remain in detail rather than the compact Ingress table.', errors)
    require('inventory.total_ingresses == 0' in summary, 'Empty Ingress posture must not use healthy tones.', errors)
    require(
        '<caption class="sr-only">Declared backend routes for Ingress' in detail,
        'Ingress route table requires accessible structure.',
        errors,
    )
    for token in (
        'Publication Evidence',
        'TLS Reference Evidence',
        'Routing Evidence',
        'Service collection evidence unavailable',
        'Secret collection evidence unavailable',
        'No TLS Reference',
        'Not Reported',
    ):
        require(token in detail or token in backend, f'Ingress detail missing evidence state: {token}', errors)
    require(
        'Open Declared Host' not in detail, 'Ingress detail must not infer a live protocol/reachability action.', errors
    )

    require(
        'ingress_publication_presentation(item.details or {})' in payload,
        'Ingress export status must use canonical publication evidence.',
        errors,
    )
    require(
        "'address_count': len(publication['addresses']) if publication['reported'] else None" in payload,
        'Unreported publication counts must remain blank in export.',
        errors,
    )
    require(
        'Resource Backends' in xlsx and 'Publication Status' in xlsx and 'All-Host Rules' in xlsx,
        'Ingress workbook must expose canonical host, publication, and backend fields.',
        errors,
    )
    require(
        "field('Host Scope', host_scope)" in topology and "field('Publication', publication['address'])" in topology,
        'Topology must consume canonical Ingress evidence.',
        errors,
    )

    require('Kubernetes Ingress Inventory Standard' in standard, 'Ingress standard documentation is missing.', errors)
    require(
        'removed the legacy `_inventory_scope.html` wrapper' in audit,
        'Ingress audit must record legacy cleanup.',
        errors,
    )
    require(
        'verify_ingress_inventory_standard.py' in quality_gate, 'Ingress verifier must run in the quality gate.', errors
    )

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    print('PASS — KAORI Ingress Inventory')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
