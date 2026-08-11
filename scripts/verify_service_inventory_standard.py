from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []

    collector = read('app/inventory/collectors/services.py')
    persistence = read('app/inventory/persistence.py')
    backend = read('app/inventory/resources/services.py')
    semantics = read('app/inventory/resources/service_semantics.py')
    routes = read('app/inventory/routes.py')
    payload = read('app/reports/export/payloads/inventory.py')
    xlsx = read('app/reports/export/xlsx/standard.py')
    workspace = read('app/templates/inventory/services/partials/_page_workspace.html')
    card = read('app/templates/inventory/services/partials/_table_card.html')
    table = read('app/templates/inventory/services/partials/_table_content.html')
    summary = read('app/templates/inventory/services/partials/_summary_cards.html')
    detail = read('app/templates/inventory/services/partials/_service_detail_content.html')
    standard = read('docs/design/patterns/KUBERNETES_SERVICE_INVENTORY.md')
    audit = read('docs/design/audits/KUBERNETES_SERVICE_INVENTORY_ALIGNMENT_AUDIT_2026_08.md')
    quality_gate = read('scripts/quality_gate.sh')

    require(
        "'inventory.services.backend-registration': endpoint_state" in collector,
        'Service backend collection evidence must be explicit.',
        errors,
    )
    require(
        "if getattr(exc, 'status', None) in {403, 404}:" in collector,
        'Endpoint fallback must only handle compatibility errors.',
        errors,
    )
    require(
        'LEGACY_TEXT_LIMIT' not in collector
        and "'external_addresses': external_addresses" in collector
        and "'ports': port_details" in collector
        and "'external_ip':" not in collector,
        'Service collector must persist canonical JSON evidence without duplicate presentation columns.',
        errors,
    )
    require(
        'if metadata is None or spec is None or not metadata.namespace or not metadata.name:' in collector,
        'Invalid Service identities must be skipped.',
        errors,
    )
    require(
        'services, collection_evidence = get_services(' in persistence
        and 'committed_evidence.update(collection_evidence)' in persistence,
        'Service collection evidence must be persisted.',
        errors,
    )

    require(
        'if not reported:' in semantics and "'label': 'Not Reported'" in semantics,
        'Missing endpoint evidence must not be hidden by selectorless semantics.',
        errors,
    )
    require(
        "'exception': bool(not_ready or total == 0)" in semantics,
        'Empty manual backend registration must create an attention signal.',
        errors,
    )
    require(
        "elif service_type == 'Unknown':" in backend,
        'Unknown Service type must be filterable.',
        errors,
    )

    require(
        "for resource in ('nodes', 'namespaces', 'configuration', 'workloads', 'pods', 'services', 'ingresses', 'storage')"
        in routes,
        'Service workspace partial must be registered.',
        errors,
    )
    require(
        'id="services-page-workspace"' in workspace and 'inventory/components/_data_freshness.html' in workspace,
        'Service workspace must own Hero and Snapshot Context.',
        errors,
    )
    require(
        'hx-target="#services-page-workspace"' in card and 'name="partial_mode" value="page_workspace"' in card,
        'Service filters must refresh the complete workspace.',
        errors,
    )
    require(
        'aria-label="Service inventory filters"' in card,
        'Service filters require an accessible label.',
        errors,
    )
    require(
        '<caption class="sr-only">' in table and table.count('scope="col"') == 6,
        'Service table requires caption and scoped columns.',
        errors,
    )
    require(
        "service.service_type ~ ' · Age '" not in table,
        'Age must remain in detail rather than the compact table.',
        errors,
    )
    require(
        'inventory.total_services == 0' in summary,
        'Empty Service posture must not use healthy tones.',
        errors,
    )

    for token in (
        'Endpoint Evidence Not Reported',
        'Pod Selection Not Applicable',
        'No Service Selector Configured',
        'No Ports Configured',
        'Not Reported',
        'Not Configured',
        'Not Applicable',
    ):
        require(token in detail, f'Service detail is missing evidence state: {token}', errors)
    require(
        '<caption class="sr-only">Declared port mappings for Service' in detail and detail.count('scope="col"') >= 6,
        'Service port mapping table requires accessible structure.',
        errors,
    )

    require(
        "details.get('load_balancer_ingress')" in payload,
        'Service export must read the canonical load-balancer field.',
        errors,
    )
    require(
        "'ready_endpoints': registration['ready'] if endpoint_reported else None" in payload,
        'Missing endpoint evidence must remain blank in export.',
        errors,
    )
    require(
        'Backend Registration' in xlsx and 'Load Balancer Addresses' in xlsx,
        'Service workbook must expose canonical backend fields.',
        errors,
    )

    require(
        'Kubernetes Service Inventory Standard' in standard,
        'Service standard documentation is missing.',
        errors,
    )
    require(
        'EndpointSlice fallback' in audit,
        'Service audit must record EndpointSlice fallback behavior.',
        errors,
    )
    require(
        'verify_service_inventory_standard.py' in quality_gate,
        'Service verifier must run in the quality gate.',
        errors,
    )

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    print('PASS — KAORI Service Inventory')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
