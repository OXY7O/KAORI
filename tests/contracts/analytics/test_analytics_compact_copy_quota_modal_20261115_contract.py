"""#4763: screenshot review — compact Analytics copy and quota modal chrome."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]
ANALYTICS = ROOT / "app/templates/kubernetes/analytics"
CAPACITY_DOMAIN = ROOT / "app/kubernetes/analytics/capacity/domain.py"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_operational_action_copy_is_compact_and_keeps_decision_gates() -> None:
    template = read(ANALYTICS / "overview/partials/_actionable_recommendation_summary.html")
    Environment(autoescape=True).parse(template)
    statements = [
        "Check impact, owner, fresh evidence, and rollback.",
        "Confirm snapshot and resource are current.",
        "Set change window, validation, and rollback.",
    ]
    for statement in statements:
        assert statement in template
        assert len(statement) <= 72

    assert "summary.priority_summary.critical > 0" in template
    assert "summary.priority_summary.warning > 0" in template
    assert "not evidence_complete" in template
    assert "Before Execution" in template
    assert "Confirm Accountable Owner" in template
    assert "Validate Current Evidence" in template
    assert "Prepare Change And Rollback" in template
    assert "whitespace-nowrap" not in template


def test_capacity_healthy_copy_and_source_scope_remain_precise() -> None:
    domain = read(CAPACITY_DOMAIN)
    summary = read(ANALYTICS / "capacity/partials/_overview.html")
    risk = read(ANALYTICS / "capacity/partials/_risk.html")
    for source in (summary, risk):
        Environment(autoescape=True).parse(source)

    healthy = [
        "Requests, limits, and observed usage fit capacity.",
        "Pod placement fits Ready-worker capacity.",
    ]
    for statement in healthy:
        assert statement in domain
        assert len(statement) <= 50

    assert "CPU cores · Memory GiB · Pod count · FS GiB (reference)." in summary
    assert "Policy and allocation signals that raise risk." in risk
    assert "'scheduling_resource': False" in domain
    assert "Ready-worker allocatable" in domain
    assert "if percentages['requests'] is not None and percentages['requests'] >= 100" in domain
    assert "if percentages['actual'] is not None and percentages['actual'] >= 95" in domain
    assert "if missing:" in domain
    assert "analysis_surface.interpretation_callout('Measurement Standard'" in summary
    assert "Governance Findings" in risk


def test_tenant_quota_modal_uses_opt_in_kaori_committed_evidence_chrome() -> None:
    modal = read(ANALYTICS / "components/_record_detail_modal.html")
    tenant = read(ANALYTICS / "workload/partials/_tenant_quota_section.html")
    mapping = read(ANALYTICS / "workload/partials/_workload_mapping_section.html")
    for source in (modal, tenant):
        Environment(autoescape=True).parse(source)

    assert "evidence_context=false, context_facts=none" in modal
    assert "if evidence_context and context_facts" in modal
    assert "if evidence_context" in modal
    assert "Committed Snapshot" in modal
    assert "Evidence Source · Read Only" in modal
    assert "'flex-col sm:flex-row sm:items-center' if evidence_context else 'items-center'" in modal
    assert "'w-full shrink-0 sm:ml-auto sm:w-auto' if evidence_context else 'ml-auto'" in modal
    assert 'analytics/components/_analysis_surfaces.html' in modal
    assert "aria-labelledby=\"{{ modal_id }}-title\"" in modal
    assert "aria-describedby=\"{{ modal_id }}-description\"" in modal
    assert 'role="dialog"' in modal
    assert 'aria-modal="true"' in modal
    assert 'x-teleport="body"' in modal
    assert '@keydown.escape.window="detailOpen = false"' in modal
    assert '@click="detailOpen = false"' in modal
    assert "max-w-7xl" in modal
    assert "max-h-[calc(100dvh-2rem)]" in modal

    assert "evidence_context=true" in tenant
    assert "context_facts=[('Active Pods', row.workloads), ('Quota Objects', row.quota_object_count)]" in tenant
    assert "'Review committed quota boundaries, observed usage, and active-Pod demand.'" in tenant
    assert "size='expanded'" in tenant
    assert "evidence_context=true" in mapping
    assert "context_facts=[('Type', row.type), ('Namespace', row.namespace), ('Pods', row.detail.pods|length)]" in mapping
    assert "row.quota_objects|length > 1" in tenant
    assert "lg:grid-cols-2" in tenant
    assert 'class="col-span-full"' in tenant
    assert "quota.hard_items" in tenant
    assert "quota.used_items" in tenant
    assert "row.missing_key_labels" in tenant
    assert "Runtime Demand Interpretation" in tenant
    assert "Recommended Action" in tenant
