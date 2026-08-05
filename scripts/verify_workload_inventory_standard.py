from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []

    collector = read('app/inventory/collectors/workloads.py')
    backend = read('app/inventory/resources/workloads.py')
    routes = read('app/inventory/routes.py')
    export_payload = read('app/reports/export/payloads/inventory.py')
    workspace = read('app/templates/inventory/workloads/partials/_page_workspace.html')
    table_card = read('app/templates/inventory/workloads/partials/_table_card.html')
    table_content = read('app/templates/inventory/workloads/partials/_table_content.html')
    summary = read('app/templates/inventory/workloads/partials/_summary_cards.html')
    detail = read('app/templates/inventory/workloads/partials/_workload_detail_content.html')
    standard = read('docs/design/patterns/KUBERNETES_WORKLOAD_INVENTORY.md')
    audit = read('docs/design/audits/KUBERNETES_WORKLOAD_INVENTORY_ALIGNMENT_AUDIT_2026_08.md')
    quality_gate = read('scripts/quality_gate.sh')

    require(
        "workload_status = 'Unknown'" in collector,
        'Missing controller status must not be classified as stable.',
        errors,
    )
    require(
        '_deployment_progress_deadline_exceeded(status)' in collector,
        'Deployment progress deadline failures must be classified.',
        errors,
    )
    require(
        "_condition_is_true(status, 'ReplicaFailure')" in collector,
        'Explicit replica failures must be classified as failed.',
        errors,
    )
    require(
        'observed_generation is not None and int(observed_generation) >= int(metadata_generation)' in collector,
        'Deployment stability must require a current observed generation.',
        errors,
    )
    require(
        "_condition_is_true(status, 'Failed')" in collector,
        'Job failure must use authoritative Job conditions.',
        errors,
    )
    require(
        "_condition_is_true(status, 'Complete')" in collector,
        'Job completion must use authoritative Job conditions.',
        errors,
    )
    require(
        "'conditions': _condition_rows(status)" in collector,
        'Controller conditions must be committed as evidence.',
        errors,
    )
    for field in (
        "'desired_replicas': desired",
        "'updated_replicas': updated",
        "'available_replicas': available",
        "'unavailable_replicas': unavailable",
    ):
        require(field in collector, f'Missing canonical export field: {field}', errors)

    require(
        "'stable': ('Stable', 'normal')" in backend,
        'Stable must be a canonical operational state.',
        errors,
    )
    require(
        "if normalized == 'unknown':" in backend,
        'Unknown workload state must be filterable.',
        errors,
    )
    require(
        '~lowered.in_(_KNOWN_STATUS_VALUES)' in backend,
        'Unrecognized runtime state must remain visible as Unknown.',
        errors,
    )
    require(
        "'placement_evidence_reported': pod_template_reported" in backend,
        'Placement absence must remain distinct from missing template evidence.',
        errors,
    )
    require(
        "'title': 'Validate Workload Runtime Evidence'" in backend,
        'Unknown runtime posture must not receive a healthy guidance state.',
        errors,
    )
    require(
        "'identity_supporting': current_type" in backend,
        'Age must remain in detail rather than the compact table row.',
        errors,
    )

    require(
        "for resource in ('nodes', 'namespaces', 'configuration', 'workloads', 'pods', 'services', 'ingresses', 'storage')" in routes,
        'Workload workspace partial must be registered.',
        errors,
    )
    require(
        'id="workloads-page-workspace"' in workspace,
        'Workload filters must own a complete page workspace.',
        errors,
    )
    require(
        'inventory/components/_data_freshness.html' in workspace,
        'Snapshot Context must refresh with Workload scope.',
        errors,
    )
    require(
        'hx-target="#workloads-page-workspace"' in table_card,
        'Workload filters must refresh Hero, snapshot, posture, and table.',
        errors,
    )
    require(
        'name="partial_mode" value="page_workspace"' in table_card,
        'Workload filters must select the workspace partial.',
        errors,
    )
    require(
        'aria-label="Workload inventory filters"' in table_card,
        'Workload filters require an accessible label.',
        errors,
    )

    require(
        '<caption class="sr-only">' in table_content,
        'Workload table requires an accessible caption.',
        errors,
    )
    require(
        table_content.count('scope="col"') == 6,
        'Workload table must expose six scoped columns.',
        errors,
    )
    require(
        '>Update Strategy<' in table_content,
        'Update Strategy must be present in the compact row.',
        errors,
    )
    require(
        '>Runtime Footprint<' not in table_content,
        'The compact row must not restore the deprecated container/runtime column.',
        errors,
    )
    require(
        '{{ workload.age }}' not in table_content,
        'Age belongs to Workload detail.',
        errors,
    )
    require(
        'inventory.total_workloads == 0' in summary,
        'Empty workload posture must use Unknown rather than healthy tones.',
        errors,
    )

    require(
        'Controller Conditions' in detail,
        'Workload detail must expose controller condition evidence.',
        errors,
    )
    require(
        'Placement Evidence Not Reported' in detail,
        'Missing Pod-template placement evidence must be explicit.',
        errors,
    )
    require(
        'workload.placement_evidence_reported' in detail,
        'Detail must not represent missing placement evidence as zero rules.',
        errors,
    )
    require(
        'search=workload.name' in detail,
        'Associated Pod navigation must preserve the selected workload context.',
        errors,
    )

    require(
        "update_strategy = details.get('update_strategy')" in export_payload
        and '_detail_row_value' not in export_payload,
        'Inventory export must require the canonical update strategy field.',
        errors,
    )
    require(
        "_optional_integer(details.get('desired_replicas'))" in export_payload
        and '_detail_integer' not in export_payload,
        'Inventory export must populate canonical desired replica evidence.',
        errors,
    )

    require(
        'Kubernetes Workload Inventory Standard' in standard,
        'Workload standard documentation is missing.',
        errors,
    )
    require(
        'Controller condition evidence' in audit,
        'Workload alignment audit must record controller condition evidence.',
        errors,
    )
    require(
        'verify_workload_inventory_standard.py' in quality_gate,
        'Workload verifier must run in the quality gate.',
        errors,
    )

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    print(
        'KAORI Workload Inventory Standard audit passed: canonical posture, '
        'controller conditions, committed scope, compact table, Pod-template '
        'evidence, export fields, accessibility, and documentation are aligned.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
