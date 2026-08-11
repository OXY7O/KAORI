from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []

    collector = read('app/inventory/collectors/pods.py')
    persistence = read('app/inventory/persistence.py')
    backend = read('app/inventory/resources/pods.py')
    semantics = read('app/inventory/resources/pod_semantics.py')
    detail_backend = read('app/inventory/resources/pod_detail.py')
    routes = read('app/inventory/routes.py')
    export_payload = read('app/reports/export/payloads/inventory.py')
    export_standard = read('app/reports/export/xlsx/standard.py')
    workspace = read('app/templates/inventory/pods/partials/_page_workspace.html')
    table_card = read('app/templates/inventory/pods/partials/_table_card.html')
    table_content = read('app/templates/inventory/pods/partials/_table_content.html')
    summary = read('app/templates/inventory/pods/partials/_summary_cards.html')
    detail = read('app/templates/inventory/pods/partials/_pod_detail_content.html')
    standard = read('docs/design/patterns/KUBERNETES_POD_INVENTORY.md')
    audit = read('docs/design/audits/KUBERNETES_POD_INVENTORY_ALIGNMENT_AUDIT_2026_08.md')
    quality_gate = read('scripts/quality_gate.sh')

    require(
        "ready = f'{ready_count}/{total_count}' if runtime_evidence_reported else 'Not Reported'" in collector,
        'Missing container runtime evidence must not become 0/0.',
        errors,
    )
    require(
        'total_count = len(regular_specs)' in collector,
        'Ready totals must use regular Pod specification containers.',
        errors,
    )
    require(
        "lifecycle_phase = 'Terminating' if deletion_timestamp is not None else kubernetes_phase" in collector,
        'Deletion timestamp must produce a Terminating lifecycle state.',
        errors,
    )
    require(
        "if getattr(exc, 'status', None) in {403, 404}:" in collector,
        'Optional owner enrichment must tolerate permission/API unavailability.',
        errors,
    )
    require(
        "'inventory.pods.owner-resolution.replicasets'" in collector
        and "'inventory.pods.owner-resolution.jobs'" in collector,
        'Owner enrichment collection evidence must be committed.',
        errors,
    )
    require(
        "*container_inventory['ephemeral_specs']" in collector,
        'Ephemeral container configuration references must be collected.',
        errors,
    )
    require(
        'ephemeral_container_statuses' in collector and 'ephemeral_container_images' in collector,
        'Ephemeral runtime and image evidence must be represented.',
        errors,
    )
    require(
        'pods, collection_evidence = get_pods(' in persistence
        and 'committed_evidence.update(collection_evidence)' in persistence,
        'Pod collection evidence must be persisted with the generation.',
        errors,
    )

    require(
        "UNKNOWN_FILTER = '__unknown__'" in backend,
        'Unknown lifecycle phase must be filterable.',
        errors,
    )
    require(
        "UNSCHEDULED_FILTER = '__unscheduled__'" in backend,
        'Unscheduled Pods must be filterable.',
        errors,
    )
    require(
        "if normalized_phase == 'terminating':" in semantics,
        'Pod operational semantics must include Terminating.',
        errors,
    )
    require(
        "elif str(ready or '').casefold() == 'not reported':" in semantics,
        'Unknown runtime evidence must remain explicit.',
        errors,
    )
    require(
        "'Unknown': (\n            'Validate Pod Runtime Evidence'" in semantics,
        'Unknown Pods must not receive healthy operational guidance.',
        errors,
    )
    require(
        "'owner_resolution_review': _owner_resolution_review(details)" in detail_backend,
        'Detail must expose incomplete higher-level owner resolution.',
        errors,
    )

    require(
        "for resource in ('nodes', 'namespaces', 'configuration', 'workloads', 'pods', 'services', 'ingresses', 'storage')"
        in routes,
        'Pod workspace partial must be registered.',
        errors,
    )
    require(
        'id="pods-page-workspace"' in workspace,
        'Pod filters must own a complete page workspace.',
        errors,
    )
    require(
        'inventory/components/_data_freshness.html' in workspace,
        'Snapshot Context must refresh with Pod scope.',
        errors,
    )
    require(
        'hx-target="#pods-page-workspace"' in table_card,
        'Pod filters must refresh Hero, snapshot, posture, and table.',
        errors,
    )
    require(
        'name="partial_mode" value="page_workspace"' in table_card,
        'Pod filters must select the workspace partial.',
        errors,
    )
    require(
        'aria-label="Pod inventory filters"' in table_card,
        'Pod filters require an accessible label.',
        errors,
    )
    require(
        'status_option.value' in table_card and 'node_option.value' in table_card,
        'Pod filter options must preserve canonical special values.',
        errors,
    )

    require(
        '<caption class="sr-only">' in table_content,
        'Pod table requires an accessible caption.',
        errors,
    )
    require(
        table_content.count('scope="col"') == 6,
        'Pod table must expose six scoped columns.',
        errors,
    )
    require(
        'inventory.total_pods == 0' in summary,
        'Empty Pod posture must use Unknown rather than healthy tones.',
        errors,
    )
    require(
        "'Terminating', inventory.terminating_count" in summary,
        'Pod posture must expose terminating lifecycle evidence.',
        errors,
    )

    for token in (
        'Condition Evidence Not Reported',
        'Pod Specification Not Reported',
        'Volume Evidence Not Reported',
        'Configuration Reference Evidence Not Reported',
        'Owner Resolution Incomplete',
    ):
        require(token in detail, f'Pod detail is missing explicit evidence state: {token}', errors)
    require(
        'pod.specification_evidence_reported' in detail and 'pod.runtime_evidence_reported' in detail,
        'Pod detail must distinguish specification and runtime evidence.',
        errors,
    )
    require(
        '<caption class="sr-only">Volumes and mounts for Pod' in detail and detail.count('scope="col"') >= 4,
        'Pod volume table requires accessible structure.',
        errors,
    )

    require(
        "'restarts': item.restart_count if runtime_reported else None" in export_payload,
        'Pod export must not manufacture zero restarts when runtime evidence is missing.',
        errors,
    )
    require(
        "'container_count': configured_container_count if specification_reported else None" in export_payload,
        'Pod export must leave container count blank when specification evidence is missing.',
        errors,
    )
    require(
        'regular, init, and ephemeral image references' in export_standard,
        'Pod export image-count definition must match collector semantics.',
        errors,
    )

    require(
        'Kubernetes Pod Inventory Standard' in standard,
        'Pod standard documentation is missing.',
        errors,
    )
    require(
        'Owner-resolution evidence' in audit,
        'Pod alignment audit must record owner-resolution evidence.',
        errors,
    )
    require(
        'verify_pod_inventory_standard.py' in quality_gate,
        'Pod verifier must run in the quality gate.',
        errors,
    )

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    print('PASS — KAORI Pod Inventory')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
