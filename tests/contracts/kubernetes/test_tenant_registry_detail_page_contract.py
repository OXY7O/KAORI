"""Tenant Registry → approved two-column KAORI Hero and governed accordion (#1073).

Reuses canonical page_hero context panel and the approved visual reference;
all existing governance services, CSRF forms and provider authority are unchanged.
"""
from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


REGISTRY = 'app/templates/kubernetes/tenant/partials/_tenant_registry.html'
DETAIL = 'app/templates/kubernetes/tenant/partials/_tenant_management_detail.html'
PAGE = 'app/templates/kubernetes/tenant/tenant_detail.html'


def test_registry_is_compact_and_uses_one_link_not_a_management_dialog():
    registry = read(REGISTRY)
    actions = registry.split(
        '<td class="{{ table_ui.cell_classes(action=true) }} align-middle">', 1
    )[1].split('</td>', 1)[0]
    assert actions.count('<a ') == 1
    assert 'tenant.tenant_detail' in actions
    assert 'hx-boost="false"' in actions
    assert 'tenant_id=tenant.id' in actions
    assert "'Manage' if can_manage else 'View'" in actions
    for key in ('page', 'per_page', 'search', 'cluster_id', 'environment', 'lifecycle_status'):
        assert f'registry_{key}=' in actions
    assert 'data-kaori-dialog-open' not in registry
    assert '<dialog' not in registry
    assert 'registry_ui.footer(' in registry


def test_single_hero_uses_unmodified_shared_kaori_template_and_spacing():
    detail = read(DETAIL)
    page = read(PAGE)
    hero = read('app/templates/components/page_hero.html')
    base = read('app/templates/kubernetes/tenant/base.html')
    layout = read('app/templates/layouts/app.html')
    assert '{% extends "kubernetes/tenant/base.html" %}' in page
    assert '{% block dashboard_content %}' in page
    assert '{% block tenant_content %}' not in page
    assert 'class="relative min-w-0 space-y-6"' in detail
    assert 'id="tenant-management-loading"' in detail
    assert 'htmx-indicator pointer-events-none absolute' in detail
    assert 'class="htmx-indicator text-sm' not in detail
    assert 'class="{{ page_hero.shell_classes() }}"' in detail
    assert 'class="{{ page_hero.layout_classes() }}"' in detail
    assert 'class="{{ page_hero.content_classes() }}"' in detail
    assert "page_hero.intro('building-2', 'Kubernetes Tenant', 'building-2')" in detail
    assert 'class="{{ page_hero.title_classes() }}"' in detail
    assert 'page_hero.description_classes()' in detail
    assert 'page_hero.persistent_metadata([' in detail
    assert 'page_hero.context_card(' in detail
    assert "'Tenant governance context'" in detail
    assert "'Tenant Details'" in detail
    assert "'Back to Registry'" in detail
    assert 'hero_tenant_metrics' in detail
    assert 'page_hero.context_panel_classes()' in hero
    assert 'page_hero.context_metric_card_classes()' not in detail
    assert 'data-kaori-hero-profile="transactional-admin"' in detail
    assert detail.count('Back to Registry') == 1
    assert '!min-h-0 !p-4' not in detail
    assert 'min-h-[15.5rem]' in hero
    assert '<div class="space-y-6" data-tenant-workspace=' in base
    assert 'data-kaori-capability-navigation=' in layout
    assert 'data-kaori-native-dialog' not in detail
    assert detail.count('page_hero.context_card(') == 1
    assert 'Tenant Overview' in detail


def test_one_described_page_not_a_new_tabbed_application():
    detail = read(DETAIL)
    common = read('app/kubernetes/tenant/route_common.py')
    assert 'id="tenant-detail-snapshot"' in detail
    assert 'Tenant Overview' in detail
    assert 'Identity, provider binding and governance details' in detail
    assert 'Identity &amp; Governance' in detail
    assert 'Quick Links' not in detail
    assert 'Description' in detail
    assert 'historical Namespace record' in detail
    assert 'row.namespace_history_count - row.namespace_count' in detail
    assert 'aria-label="Tenant management sections"' in detail
    assert 'role="region"' in detail
    assert 'content_tabs.render_links' not in detail
    assert 'data-tenant-active-view' not in detail
    assert 'active_tenant_detail_view' not in detail
    assert 'xl:sticky xl:top-4' not in detail
    assert 'Tenant at a glance' not in detail
    assert 'tenant_detail_tab_urls' not in common
    assert 'requested_view' not in common
    assert 'tenant_detail_view' not in common
    assert 'view=context[' not in common
    assert '<dialog' not in detail



def test_tenant_overview_record_sheet_preserves_committed_identity_and_audit():
    detail = read(DETAIL)
    overview = detail.split('id="tenant-detail-snapshot"', 1)[1].split(
        'aria-label="Tenant management sections"', 1
    )[0]
    Environment().parse(detail)

    # The existing KAORI shell keeps one compact, responsive record surface.
    assert overview.count('data-kaori-tenant-record-sheet') == 1
    assert 'section_intro.render(' in overview
    assert 'Identity &amp; Governance' in overview
    assert 'sm:grid-cols-2' in overview
    assert 'xl:grid-cols-4' in overview
    assert 'sm:grid-cols-[6rem_minmax(0,1fr)]' in overview
    assert overview.count('<dl ') == 3
    assert overview.count('<dt ') == 10
    assert 'Record History' not in overview
    assert 'Governance &amp; Responsibility' not in overview
    assert 'Identity &amp; Origin' not in overview

    # Exact provenance, provider governance and lifecycle are committed facts.
    assert "technical_value.render(tenant.id, monospace=true, size='body')" in overview
    assert '{% import "components/technical_value.html" as technical_value %}' in detail
    assert 'row.cluster.name if row.cluster else' in overview
    assert "tenant.provider_key|replace('_', ' ')|title" in overview
    assert "tenant.ownership_status|replace('_', ' ')|title" in overview
    assert "tenant.reconciliation_authority|replace('_', ' ')|title" in overview
    assert "tenant.lifecycle_status == 'ready'" in overview
    assert 'table_label.status_label(' in overview
    assert '{{ tenant.generation }}' in overview
    assert "tenant.created_at.strftime('%Y-%m-%d %H:%M')" in overview
    assert "tenant.updated_at.strftime('%Y-%m-%d %H:%M')" in overview
    assert "else 'Not recorded'" in overview

    # Full long text, readable optional history, no invented action/empty band.
    assert '[overflow-wrap:anywhere]' in overview
    assert 'min-w-0' in overview
    assert 'row.namespace_history_count - row.namespace_count' in overview
    assert 'not part of the active Namespace count' in overview
    assert "tenant.description or 'No Tenant description has been recorded.'" in overview
    assert 'whitespace-pre-wrap' in overview
    assert 'Quick Links' not in overview
    assert 'overflow-x-auto' not in overview
    assert overview.count('<form ') == 1  # Governed Decommission moved into the sheet.
    assert 'data-destructive-modal-open' in overview
    assert 'name="tenant_detail_section" value="lifecycle"' in overview
    assert 'aria-label="Authority Boundary"' in overview
    assert '<details id="tenant-lifecycle-actions"' in overview
    assert 'id="tenant-provider-authority"' in overview
    assert '<details id="tenant-provider-authority"' not in overview


def test_page_shows_all_governed_sections_in_authoritative_order():
    detail = read(DETAIL)
    labels = (
        'id="tenant-detail-snapshot"',
        'id="tenant-provider-authority"',
        'id="tenant-lifecycle-actions"',
        'id="tenant-release-governance"',
        'id="tenant-native-handback"',
    )
    assert all(label in detail for label in labels)
    assert [detail.index(label) for label in labels] == sorted(
        detail.index(label) for label in labels
    )
    assert 'tenant-namespace-attachment' not in detail
    assert 'data-capsule-namespace-attach' not in detail
    assert "tenant.ownership_status == 'adopted'" in detail
    assert "tenant.provider_key == 'native_kubernetes'" in detail
    assert "tenant.provider_key == 'capsule'" in detail
    assert "current_user.has_permission('clusters.manage')" in detail


def test_release_evidence_is_readable_full_width_without_nested_scroll():
    detail = read(DETAIL)
    release = detail.split('id="tenant-release-governance"', 1)[1].split(
        'id="tenant-native-handback"', 1
    )[0]
    for label in (
        'Scope readiness',
        'Provider handoff scope',
        'Independent approval and handoff',
        '04 · Verify and finalize',
        'aria-label="Release blockers"',
        'aria-label="Provider handoff inventory"',
        'aria-label="Release wizard active step"',
        'aria-label="Scope review coverage"',
        'View recorded conditions',
    ):
        assert label in release
    assert 'divide-y divide-outline-subtle' in release
    assert 'max-h-72' not in release
    assert 'overflow-y-auto' not in release
    assert 'text-sm leading-6' in release
    assert release.count('<form ') == 15



def test_release_handoff_inventory_is_structured_with_full_on_demand_identifiers():
    detail = read(DETAIL)
    handoff = detail.split('id="tenant-release-stage-inventory"', 1)[1].split(
        "{% elif tenant_release_step == 'approval' %}", 1
    )[0]
    Environment().parse(detail)
    assert 'aria-label="Provider handoff inventory"' in handoff
    assert 'aria-label="Recorded provider handoff resources"' in handoff
    assert "row.release_preflight.handoff_components|length" in handoff
    assert "row.release_preflight.handoff_required_count" in handoff
    assert "for item in row.release_preflight.handoff_components" in handoff
    assert '<ol class="mt-3 divide-y divide-outline-subtle border-y border-outline-subtle"' in handoff
    assert "item.kind == 'Namespace'" in handoff
    assert "item.kind == 'ResourceQuota'" in handoff
    assert "item.kind == 'LimitRange'" in handoff
    assert "item.kind == 'CapsuleTenant'" in handoff
    assert '{{ item.name }}' in handoff
    assert 'break-words' in handoff
    assert '[overflow-wrap:anywhere]' in handoff

    for state in ('external_acceptance_required', 'owner_review_required', 'observe_only'):
        assert state in handoff
    for label in ('Handoff Required', 'Ownership Conflict', 'Observed'):
        assert label in handoff
    assert "warning' if item.handoff != 'observe_only' else 'info'" in handoff

    # Each clickable summary contains the compact Kind/Name + ownership/manager
    # line; no extra metadata band or standalone identifiers row.
    assert 'Ownership:' in handoff
    assert 'Manager:' in handoff
    assert 'sm:grid-cols-[minmax(0,1fr)_auto]' in handoff
    assert 'group/identifiers min-w-0' in handoff
    assert '<li class="min-w-0">' in handoff
    assert 'cursor-pointer list-none' in handoff
    assert 'min-h-9' not in handoff
    assert "item.ownership|replace('_', ' ')|title" in handoff
    assert "item.managed_by if item.managed_by else 'Not recorded'" in handoff

    # Long provider identities are preserved unchanged in accessible native details.
    assert 'group/identifiers' in handoff
    assert 'aria-label="Provider identifiers for {{ item.kind }} {{ item.name }}"' in handoff
    assert 'Provider IDs' in handoff
    assert 'Provider identifiers for {{ item.kind }} {{ item.name }}' in handoff
    assert '{{ item.namespace }}' in handoff
    assert '{{ item.uid }}' in handoff
    assert '{{ item.resource_version }}' in handoff
    assert 'break-all font-mono' in handoff
    assert '<details' in handoff
    assert '<summary' in handoff
    assert 'overflow-y-auto' not in handoff
    assert 'overflow-x-auto' not in handoff
    assert 'max-h-72' not in handoff

    # Showing provider evidence never executes or authorizes a provider write.
    assert 'read-only provider observations' in handoff
    assert 'Recorded during the latest Release preflight' not in handoff
    assert "row.release_preflight.handoff_components|length" in handoff
    assert 'flex min-w-0 flex-wrap items-baseline gap-x-3' in handoff
    assert 'This does not authorize Release.' in handoff
    assert 'Run Review Release to collect' in handoff
    assert '<form ' not in handoff




def test_release_step_three_separates_plan_review_external_claim_and_platform_admin():
    detail = read(DETAIL)
    approval = detail.split('id="tenant-release-stage-approval"', 1)[1].split(
        "{% elif tenant_release_step == 'finalize' %}", 1
    )[0]
    Environment().parse(detail)
    assert 'Independent approval and handoff' in approval
    assert 'aria-label="Governed handoff workflow"' in approval
    assert 'data-release-handoff-approval' in approval
    assert 'One active plan per Tenant.' in approval
    assert 'requester and independent reviewer must be different' in approval

    # An acknowledged plan is locked without inventing approval or provider transfer.
    assert 'role="status" aria-label="Active handoff plan"' in approval
    assert "row.release_handoff_preparation_state == 'acknowledged'" in approval
    assert "row.release_handoff_preparation_state == 'expired'" in approval
    assert 'governed restart' in approval
    assert 'Successor owner' in approval
    assert 'Change record' in approval
    assert 'handoff_plan.successor_owner' in approval
    assert 'handoff_plan.change_reference' in approval
    assert '{{ handoff_plan.plan_sha256 }}' in approval
    assert 'break-all font-mono' in approval
    assert 'Plan SHA-256' in approval

    # Recorded independent review does not imply verified successor acceptance.
    assert 'Independent review recorded. External owner acceptance' in approval
    assert 'role="status" aria-label="External successor evidence"' in approval
    assert "successor_claim.plan_sha256 == handoff_plan.plan_sha256" in approval
    assert 'External Reference Unverified' in approval
    assert '{{ successor_claim.successor_reference }}' in approval
    assert 'not an additional approval' in approval
    assert 'provider ownership remains unchanged' in approval

    # Exact platform-admin permission/identity action is preserved verbatim.
    assert 'aria-label="Platform Admin provider verification"' in approval
    assert 'Platform Admin verification' in approval
    assert 'registered Kubernetes X.509 connection' in approval
    assert "tenant.accept_native_successor_handoff_route" in approval
    assert 'name="confirm_successor_acceptance"' in approval
    assert 'type="checkbox"' in approval
    assert 'required' in approval
    assert 'Verify Provider &amp; Accept as Platform Admin' in approval

    # All pre-existing conditional mutation routes and 14 CSRF forms are unchanged.
    for action in (
        'prepare_tenant_release_handoff_route',
        'record_tenant_release_successor_reference_route',
        'accept_native_successor_handoff_route',
        'approve_tenant_release_handoff_route',
        'restart_expired_tenant_release_handoff_route',
        'dry_run_native_release_handoff_route',
        'execute_native_release_handoff_route',
        'inspect_native_external_handoff_route',
        'release_tenant_governance_route',
        'finalize_verified_native_release_route',
    ):
        assert action in approval
    assert approval.count('<form ') == 10
    assert detail.count('<form ') == 17
    assert detail.count('name="csrf_token"') == 17




def test_native_platform_admin_acceptance_requires_verified_cluster_tls_in_ui():
    detail = read(DETAIL)
    approval = detail.split('id="tenant-release-stage-approval"', 1)[1].split(
        'id="tenant-release-stage-finalize"', 1
    )[0]
    final = detail.split('id="tenant-release-stage-finalize"', 1)[1].split(
        "{% if row.release_preflight and row.release_preflight.status == 'handoff_review_required'", 1
    )[0]
    Environment().parse(detail)

    # Status must not conceal missing/expired independent review evidence.
    assert 'current_handoff_approval.plan_sha256 == current_handoff_plan.plan_sha256' in approval
    assert 'row.native_release_readiness.approval_complete' in approval
    assert 'row.native_release_readiness.review_complete' in approval
    assert 'Verified TLS Required' in approval
    assert 'row.cluster.kubernetes_connection.verify_ssl is not true' in approval

    # The existing acceptance POST must only render in the positive TLS
    # branch. The backend continues to fail closed independently.
    before_acceptance = approval.split("tenant.accept_native_successor_handoff_route", 1)[0]
    assert 'aria-label="Kubernetes verified TLS prerequisite"' in before_acceptance
    assert 'if not row.cluster or not row.cluster.kubernetes_connection' in before_acceptance
    assert '{% else %}' in before_acceptance
    assert "url_for('cluster.edit_cluster', cluster_id=row.cluster.id)" in approval
    assert "current_user.has_permission('clusters.manage')" in approval
    assert 'Full Validation' in approval
    assert 'name="confirm_successor_acceptance"' in approval

    # Step 4 action explains the same canonical connection requirement.
    assert 'Next required action' in final
    assert 'Verified TLS Required' in final
    assert 'Test Connection and complete Full Validation' in final
    assert "url_for('cluster.edit_cluster', cluster_id=row.cluster.id)" in final

    # Existing operations are not deleted and may still render when eligible.
    assert detail.count('<form ') == 17
    assert detail.count('name="csrf_token"') == 17


def test_step_three_freshness_matches_native_readiness_and_hides_stale_acceptance():
    detail = read(DETAIL)
    step = detail.split('id="tenant-release-stage-approval"', 1)[1].split(
        'id="tenant-release-stage-finalize"', 1
    )[0]
    Environment().parse(detail)

    assert "row.get('native_release_readiness')" in step
    assert 'row.native_release_readiness.approval_expired' in step
    assert 'row.native_release_readiness.review_expired' in step
    assert "table_label.status_label('Approval Expired', 'warning')" in step
    assert "table_label.status_label('Review Expired', 'warning')" in step
    assert 'role="status" aria-label="Expired Native handoff evidence"' in step
    assert "tenant_release_step_urls['finalize']" in step
    assert 'View recovery steps' in step
    # Backend already checks both freshness conditions; UI must not offer the
    # successor-acceptance form based only on plan-SHA match.
    accept = step.split("tenant.accept_native_successor_handoff_route", 1)[0]
    assert 'row.native_release_readiness.approval_complete' in accept
    assert 'row.native_release_readiness.review_complete' in accept
    assert 'handoff_plan.requested_by != current_user.id' in accept
    assert 'name="confirm_successor_acceptance"' in step
    assert step.count('<form ') == 7


def test_step_four_has_compact_readiness_and_role_scoped_recovery():
    detail = read(DETAIL)
    step = detail.split('id="tenant-release-stage-finalize"', 1)[1].split(
        "{% if row.release_preflight and row.release_preflight.status == 'handoff_review_required'", 1
    )[0]
    Environment().parse(detail)
    assert 'Verify &amp; Finalize' in step
    assert 'aria-label="Native Kubernetes full-cycle readiness"' in step
    assert 'lg:grid-cols-5' in step
    assert 'aria-label="Native Release checkpoints"' in step
    assert 'native_cycle.stages' in step
    assert '{{ checkpoint.label }}' in step
    assert 'checkpoint.display_status' in step
    assert 'Next required action' in step
    assert 'role="status" aria-label="Expired handoff recovery"' in step
    assert 'native_cycle.approval_expired' in step
    assert 'native_cycle.review_expired' in step
    assert 'native_cycle.restart_blocked_by_readback' in step
    assert 'native_cycle.restart_required' in step
    assert 'native_cycle.restart_zero_transfer_recheck_required' in step
    assert 'Last committed read-back classified zero transferred resources' in step
    assert 'fresh authoritative provider verification' in step
    assert 'row.release_handoff_plan.requested_by == current_user.id' in step
    assert "current_user.has_permission('tenant.manage')" in step
    assert "current_user.has_permission('integrations.manage')" in step
    assert 'restart_expired_tenant_release_handoff_route' in step
    assert 'name="confirm_handoff_restart"' in step
    assert 'value="restart" required' in step
    assert 'Restart Expired Handoff Plan' in step
    assert 'This account is not the original requester' in step
    assert 'row.release_handoff_plan.requested_by != current_user.id' in step
    assert 'Restart requires the original requester with both Tenant and Integrations management permissions' in step
    assert 'Governed recovery review is required; automatic restart is prohibited.' in step
    assert "tenant_release_step_urls['scope']" in step
    assert "tenant_release_step_urls['approval']" in step
    assert 'External reference' not in step  # Not acceptance evidence.
    assert 'Kubernetes stays authoritative' in step
    assert step.count('<form ') == 1
    assert detail.count('<form ') == 17
    assert detail.count('name="csrf_token"') == 17






def test_recoverable_executor_has_priority_in_both_release_steps():
    detail = read(DETAIL)
    projection = read('app/kubernetes/tenant/native_release_readiness.py')
    Environment().parse(detail)

    approval = detail.split('id="tenant-release-stage-approval"', 1)[1].split(
        "{% elif tenant_release_step == 'finalize' %}", 1
    )[0]
    finalize = detail.split('id="tenant-release-stage-finalize"', 1)[1].split(
        "{% if row.release_preflight and row.release_preflight.status == 'handoff_review_required'", 1
    )[0]
    assert 'row.native_release_readiness.provider_handoff_recovery_required' in approval
    assert "table_label.status_label('Recovery Required', 'warning')" in approval
    assert approval.index('row.native_release_readiness.provider_handoff_recovery_required') < approval.index(
        'row.native_release_readiness.approval_expired'
    )
    assert 'partial_handoff_recovery_required' in approval
    assert 'Resume Verified Native Handoff' in approval
    assert "verified_consent.accepted_by == current_user.id" in approval

    assert 'native_cycle.provider_handoff_recovery_required' in finalize
    assert finalize.index('native_cycle.provider_handoff_recovery_required') < finalize.index(
        'native_cycle.approval_expired'
    )
    assert 'aria-label="Native provider handoff recovery"' in finalize
    assert 'Verified objects' in finalize
    assert 'Provider mutation reported' in finalize
    assert 'recovery_attempt.provider_mutation_performed is true' in finalize
    assert 'Zero verified objects does not prove zero resources changed.' in finalize
    assert 'tenant.release.native_handoff_recovery_required' in finalize
    assert 'Review Handoff Evidence' in finalize
    assert 'recovery_attempt.errors[:3]' in finalize
    assert "tenant_release_step_urls['approval']" in finalize
    assert '"Recovery Required" if label == "KAORI provider handoff"' in projection
    assert '"provider_handoff_recovery_required": provider_handoff_recovery_required' in projection
    assert detail.count('<form method="post"') == 17
    assert detail.count('name="csrf_token"') == 17
    assert detail.count('hx-post=') == 17



def test_expired_approval_does_not_offer_a_doomed_native_dry_run():
    detail = read(DETAIL)
    approval = detail.split('id="tenant-release-stage-approval"', 1)[1].split(
        "{% elif tenant_release_step == 'finalize' %}", 1
    )[0]
    Environment().parse(detail)
    assert 'tenant.dry_run_native_release_handoff_route' in approval
    before_preview = approval.split("tenant.dry_run_native_release_handoff_route", 1)[0]
    assert 'row.native_release_readiness.approval_complete' in before_preview
    assert 'row.native_release_readiness.review_complete' in before_preview
    assert 'Preview Native Transfer' in approval
    assert detail.count('<form method="post"') == 17
    assert detail.count('name="csrf_token"') == 17




def test_native_no_transfer_recovery_keeps_three_independent_governed_actions():
    detail = read(DETAIL)
    routes = read('app/kubernetes/tenant/routes.py')
    readiness = read('app/kubernetes/tenant/native_release_readiness.py')
    service = read('app/kubernetes/tenant/native_no_transfer_recovery.py')
    approval = read('app/kubernetes/tenant/release_handoff_approval.py')
    Environment().parse(detail)

    assert 'data-native-no-transfer-recovery' in detail
    assert 'Governed No-Transfer Recovery' in detail
    assert 'native_cycle.no_transfer_assessment_candidate' in detail
    assert '"no_transfer_assessment_candidate": no_transfer_assessment_candidate' in readiness
    assert 'native_cycle.provider_handoff_recovery_required' in detail
    assert 'native_cycle.no_transfer_assessment_current' in detail
    assert 'native_cycle.no_transfer_authorized_current' in detail
    assert 'recovery_requester and recovery_operator_permitted' in detail
    assert 'recovery_independent and recovery_operator_permitted' in detail
    assert 'current_user.id != recovery_assessment.assessed_by' in detail
    assert 'current_user.id != recovery_plan.requested_by' in detail
    assert 'current_user.id != recovery_assessment.executor_actor_id' not in detail
    assert 'The original failed executor may review' in detail
    assert 'a second authorized recovery reviewer' in detail
    assert 'assess_native_no_transfer_recovery_route' in detail
    assert 'authorize_native_no_transfer_recovery_route' in detail
    assert 'restart_expired_tenant_release_handoff_route' in detail
    assert 'name="confirm_no_transfer_assessment"' in detail
    assert 'name="confirm_no_transfer_authorization"' in detail
    assert 'name="assessment_sha256"' in detail
    assert 'tenant_detail_section" value="release"' in detail
    assert 'hx-disabled-elt="find button[type=\'submit\']"' in detail

    assert "def assess_native_no_transfer_recovery_route(" in routes
    assert "def authorize_native_no_transfer_recovery_route(" in routes
    assert "confirmed=request.form.get('confirm_no_transfer_assessment') == 'assess'" in routes
    assert "confirmed=request.form.get('confirm_no_transfer_authorization') == 'authorize'" in routes
    assert '"no_transfer_authorized_current": no_transfer_authorized_current' in readiness
    assert 'def _verify_original_provider_state(' in service
    assert 'summarize_native_handoff_recovery(' in service
    assert "proof.get('status') != 'provider_handoff_not_started'" in service
    assert 'def require_authorized_no_transfer_restart(' in service
    assert 'require_authorized_no_transfer_restart(' in approval
    assert '_verify_original_provider_state(' in approval
    assert "no_transfer_recovery_assessment_sha256" in approval

    assert detail.count('<form method="post"') == 17
    assert detail.count('name="csrf_token"') == 17
    assert detail.count('hx-post=') == 17


def test_external_readback_discloses_stale_requirements_before_read_only_inspection():
    detail = read(DETAIL)
    readiness = read('app/kubernetes/tenant/native_release_readiness.py')
    approval = detail.split('id="tenant-release-stage-approval"', 1)[1].split(
        "{% elif tenant_release_step == 'finalize' %}", 1
    )[0]
    Environment().parse(detail)

    assert 'readback_status.external_readback_prerequisites_current' in approval
    assert 'readback_status.approval_expired' in approval
    assert 'readback_status.external_reference_current' in approval
    assert 'readback_status.dry_run_passed' in approval
    assert 'aria-label="External read-back prerequisites"' in approval
    assert 'External handoff inspection is unavailable' in approval
    assert 'The original requester must restart it' in approval
    assert "tenant_release_step_urls['finalize']" in approval
    assert 'View recovery steps' in approval
    assert 'A historical Dry-Run Passed receipt' not in approval
    assert 'historical Dry-Run Passed receipt may be expired' in approval
    assert 'External operator handoff — inspection only' in approval
    assert 'Inspect External Handoff' in approval
    assert 'governed Native Handoff executor' in approval
    assert 'name="confirm_native_handoff_readback"' in approval
    assert 'tenant.inspect_native_external_handoff_route' in approval
    assert 'Historical / Not Current' in approval
    assert 'Last recorded read-back:' in approval
    assert 'This historical observation does not verify external acceptance' in approval

    assert '_checked_recently((successor_claim or {}).get("recorded_at"))' in readiness
    assert 'external_readback_prerequisites_current' in readiness
    assert '"external_reference_current": external_reference_current' in readiness
    assert 'and (dry_run or {}).get("release_authorized") is False' in readiness
    # Render-gating does not delete or silently replace original protected POST.
    assert detail.count('<form method="post"') == 17
    assert detail.count('name="csrf_token"') == 17
    assert detail.count('hx-post=') == 17



def test_exact_governance_forms_return_to_same_page_and_global_toast():
    detail = read(DETAIL)
    common = read('app/kubernetes/tenant/route_common.py')
    toast = read('app/templates/components/operational_toast.html')
    assert detail.count('<form ') == 17
    assert detail.count('name="csrf_token"') == 17
    assert detail.count('name="tenant_detail_id"') == 18
    assert detail.count('registry_state.items()') == 18
    assert detail.count('hx-target="#tenant-management-detail"') == 18
    assert detail.count('hx-select="#tenant-management-detail"') == 18
    assert detail.count('hx-post=') == 17
    assert 'name="tenant_detail_view"' not in detail
    assert detail.count('name="tenant_detail_section"') == 18
    assert detail.count('name="tenant_release_step"') == 15
    assert 'tenant_release_step_urls' in common
    assert "context['tenant_release_step']" in common
    assert "context['tenant_detail_open_section'] = active_section" in common
    assert "detail_id = str(request.form.get('tenant_detail_id')" in common
    assert "'kubernetes/tenant/partials/_tenant_management_detail.html'" in common
    assert "'tenant.tenant_detail', tenant_id=detail_id" in common
    assert 'toast_oob=True' in common
    assert 'beforeend:#operational-toast-stack' in toast
    assert 'data-kaori-native-dialog' not in detail



def test_release_wizard_navigation_is_fragment_get_with_history_and_plain_link_fallback():
    detail = read(DETAIL)
    routes = read('app/kubernetes/tenant/routes.py')
    Environment().parse(detail)
    # All four step tabs, footer Previous/Next, and internal recovery links
    # preserve normal href while using scoped HTMX GET and canonical URLs.
    assert detail.count('hx-get="{{ tenant_release_step_urls[') == 13
    assert detail.count('hx-push-url="{{ tenant_release_step_urls[') == 13
    assert detail.count('hx-select="#tenant-management-detail"') == 18
    assert detail.count('hx-target="#tenant-management-detail"') == 18
    assert detail.count('hx-select="#tenant-release-governance"') == 13
    assert detail.count('hx-target="#tenant-release-governance"') == 13
    assert detail.count('hx-swap="outerHTML show:none focus-scroll:false"') == 31
    assert 'hx-history="false"' in detail  # Avoid restoring stale authorization evidence.
    assert detail.count('href="{{ tenant_release_step_urls[') == 13
    assert "request.headers.get('HX-Target') == 'tenant-release-governance'" in routes
    assert "request.headers.get('HX-History-Restore-Request') != 'true'" in routes
    assert "'kubernetes/tenant/partials/_tenant_management_detail.html'" in routes
    assert "response.headers['Cache-Control'] = 'no-store, max-age=0'" in routes
    assert "return render_template(\n        'kubernetes/tenant/tenant_detail.html'" in routes
    assert 'data-kaori-tenant-detail-page' not in detail


def test_release_action_feedback_reports_server_result_without_persisting_confirmation():
    detail = read(DETAIL)
    common = read('app/kubernetes/tenant/route_common.py')
    Environment().parse(detail)
    assert 'tenant_action_feedback=feedback' in common
    assert "feedback = getattr(g, 'tenant_operational_feedback', None)" in common
    assert 'toast_oob=True' in common
    assert 'data-tenant-release-action-feedback' in detail
    assert "tenant_action_feedback.get('status', 'info')" in detail
    assert 'tenant_action_feedback.title' in detail
    assert 'tenant_action_feedback.message' in detail
    assert 'role="{{ \'alert\' if action_status == \'error\' else \'status\' }}"' in detail
    assert 'data-release-confirmation-guidance' in detail
    assert 'A checked box authorizes one submission, not a recorded approval.' in detail
    assert 'The confirmation resets after submission.' in detail
    assert 'hx-history="false"' in detail
    assert detail.count('hx-disabled-elt="find button[type=\'submit\']"') == 17
    assert detail.count('disabled:cursor-progress disabled:opacity-60') == 16
    assert 'Processing Tenant request…' in detail
    assert 'fixed bottom-4 right-4' in detail
    assert detail.count('<form method="post"') == 17
    assert detail.count('name="csrf_token"') == 17
    assert detail.count('hx-post=') == 17
    assert detail.count('name="tenant_release_step"') == 15



def test_service_endpoints_and_independent_approval_remain_unchanged():
    detail = read(DETAIL)
    for name in (
        'review_tenant_release_route',
        'prepare_tenant_release_handoff_route',
        'restart_expired_tenant_release_handoff_route',
        'approve_tenant_release_handoff_route',
        'record_tenant_release_successor_reference_route',
        'accept_native_successor_handoff_route',
        'dry_run_native_release_handoff_route',
        'execute_native_release_handoff_route',
        'inspect_native_external_handoff_route',
        'release_tenant_governance_route',
        'finalize_verified_native_release_route',
        'verify_native_successor_handback_route',
        'decommission_tenant_route',
    ):
        assert name in detail
    assert 'Acknowledge as Independent Reviewer' in detail
    assert 'handoff_plan.requested_by != current_user.id' in detail
    assert 'row.release_preflight.blockers' in detail
    # Attachment is a Discovery/Adoption operation, not a Tenant Detail form.
    discovery = read('app/templates/kubernetes/tenant/partials/_tenant_discovery.html')
    preflight = read('app/templates/kubernetes/tenant/partials/_tenant_adoption_preflight.html')
    routes = read('app/kubernetes/tenant/routes.py')
    assert 'data-capsule-namespace-attach' not in detail
    assert 'tenant-namespace-attachment' not in detail
    assert 'Review Attachment' in discovery
    assert 'tenant_adoption_attachment_only' in preflight
    assert 'attach_existing_capsule_namespace_route' in routes
    assert "destructive_modal.render('tenant-decommission-modal'" in detail
    assert 'data-destructive-modal-open' in detail
    assert 'name="kubernetes_successor_token"' not in detail


def test_detail_get_reads_one_exact_committed_tenant_without_provider_request():
    routes = read('app/kubernetes/tenant/routes.py')
    common = read('app/kubernetes/tenant/route_common.py')
    context = read('app/kubernetes/tenant/registry_context.py')
    assert "@tenant_bp.get('/tenants/<string:tenant_id>/manage')" in routes
    assert "@any_permission_required('tenant.view', 'tenant.manage')" in routes
    assert "def tenant_detail(tenant_id: str):" in routes
    assert '_tenant_detail_context(tenant_id)' in routes
    assert 'get_tenant_registry_context(tenant_id=tenant_id, per_page=1)' in common
    assert 'if not rows:' in common
    assert 'abort(404)' in common
    assert 'query.filter(Tenant.id == tenant_id)' in context
    assert 'runtime_adapter.build_client(' not in common
    assert 'runtime_adapter.build_client(' not in context


def test_independent_work_inbox_deep_link_targets_release_section():
    inbox = read('app/kubernetes/tenant/approval_inbox.py')
    assert '"tenant.tenant_detail"' in inbox
    assert '_anchor="tenant-release-governance"' in inbox
    assert 'tenant_detail_section="release"' in inbox
    assert 'release_step="approval"' in inbox
    assert 'view="release"' not in inbox


def test_tenant_templates_parse_under_jinja2():
    environment = Environment(autoescape=True)
    for path in (REGISTRY, PAGE, DETAIL):
        environment.parse(read(path))



def test_approved_kaori_hero_matches_reference_composition():
    detail = read(DETAIL)
    hero = read('app/templates/components/page_hero.html')
    assert 'page_hero.context_card(' in detail
    assert "'Tenant Details'" in detail
    assert "'Governed Resource State'" in detail
    assert "'Active Namespaces'" in detail
    assert "'Ownership'" in detail
    assert 'return_to_registry_url' in detail
    assert 'context_panel_classes()' in hero
    assert 'context_metric_card_classes()' in hero
    assert 'context_single_action_classes()' in hero
    assert 'class="{{ page_hero.layout_classes() }}"' in detail
    assert 'class="{{ page_hero.content_classes() }}"' in detail
    assert detail.count('Back to Registry') == 1


def test_governance_scope_reuses_approved_tenant_estate_posture_pattern():
    detail = read(DETAIL)
    fleet = read('app/templates/kubernetes/tenant/overview.html')
    card = read('app/templates/components/operational_section_card.html')
    posture = read('app/templates/components/resource_posture_grid.html')
    assert 'Governance Scope' in detail
    assert 'section_intro.render(' in detail
    assert 'operational_section_card.render(' in detail
    assert 'resource_posture_grid.render(tenant_governance_metrics, columns=4)' in detail
    assert "'Tenant Governance'" in detail
    assert "'layout-grid'" in detail
    assert "id='tenant-governance-scope-card'" in detail
    assert "body_classes='p-0'" in detail
    assert "aria_label='Tenant governance summary'" in detail
    assert "{% import \"components/operational_section_card.html\" as operational_section_card %}" in detail
    assert "{% import \"components/resource_posture_grid.html\" as resource_posture_grid %}" in detail
    assert 'operational_section_card.render(' in fleet
    assert 'resource_posture_grid.render(estate_metrics, columns=5)' in fleet
    assert 'border-b border-outline-subtle' in card
    assert 'grid gap-px bg-outline-subtle' in posture
    assert "columns == 5" in posture  # four-column responsive fallback also shared
    for label in ('Active Namespaces', 'Environments', 'Reconciliation Authority', 'Lifecycle'):
        assert f"'{label}'" in detail
    assert 'row.namespace_count' in detail
    assert 'row.environments|length' in detail
    assert 'tenant.reconciliation_authority' in detail
    assert 'tenant.lifecycle_status' in detail
    assert 'tenant_summary_cards' not in detail
    assert 'tenant-resource-coverage-title' not in detail
    assert 'tenant-authority-scope-title' not in detail
    assert "'Tenant Estate'," not in detail  # Never label one Tenant as fleet estate.


def test_single_tenant_overview_and_authority_boundary_preserved():
    detail = read(DETAIL)
    assert 'Identity &amp; Governance' in detail
    assert 'data-kaori-tenant-record-sheet' in detail
    assert "technical_value.render(tenant.id, monospace=true, size='body')" in detail
    assert "row.cluster.name if row.cluster else 'Cluster unavailable'" in detail
    assert "tenant.provider_key|replace('_', ' ')|title" in detail
    assert 'tenant.description or' in detail
    assert "url_for('tenant.resource_profiles')" not in detail
    assert "url_for('tenant.operations')" not in detail
    assert 'tenant.created_at.strftime(' in detail
    assert 'tenant.updated_at.strftime(' in detail
    assert 'role="note" aria-label="Authority Boundary"' in detail
    statement = (
        'KAORI presents committed governance evidence; Kubernetes or Capsule '
        'remains authoritative for provider resources.'
    )
    assert detail.count(statement) == 1




def test_compact_provider_and_lifecycle_evidence_without_duplicate_accordions():
    detail = read(DETAIL)
    overview = detail.split('id="tenant-detail-snapshot"', 1)[1].split(
        'aria-label="Tenant management sections"', 1
    )[0]

    # Provider values are already shown in the existing Overview facts.
    assert overview.count('id="tenant-provider-authority"') == 1
    assert '<details id="tenant-provider-authority"' not in detail
    assert "tenant.provider_key|replace('_', ' ')|title" in overview
    assert "tenant.reconciliation_authority|replace('_', ' ')|title" in overview
    statement = (
        'KAORI presents committed governance evidence; Kubernetes or Capsule '
        'remains authoritative for provider resources.'
    )
    assert detail.count(statement) == 1
    assert overview.count(statement) == 1
    assert detail.count('role="note" aria-label="Authority Boundary"') == 1
    assert '<aside' not in overview

    # Lifecycle is a native Overview disclosure, not a fifth standalone card.
    assert overview.count('id="tenant-lifecycle-actions"') == 1
    assert 'Lifecycle controls' in overview
    assert "tenant_detail_open_section == 'lifecycle'" in overview
    assert 'name="tenant-governance"' not in overview
    assert "row.decommission_preflight" in overview
    assert "tenant.decommission_tenant_route" in overview
    assert 'data-destructive-modal-open' in overview
    assert 'data-destructive-submit-button-id=' in overview
    assert 'aria-label="Decommission blockers"' in overview
    assert "for blocker in decommission.blockers" in overview
    assert '{{ blocker }}' in overview
    assert "destructive_modal.render('tenant-decommission-modal'" in detail
    assert detail.count('name="csrf_token"') == 17
    assert detail.count('<form ') == 17


def test_release_is_permanent_and_other_governance_sections_remain_accessible():
    detail = read(DETAIL)
    release = detail.split('id="tenant-release-governance"', 1)[1].split(
        'id="tenant-native-handback"', 1
    )[0]
    names = ('tenant-native-handback',)
    assert '<section id="tenant-release-governance"' in detail
    assert '<details id="tenant-release-governance"' not in detail
    assert '<summary' not in release.split('aria-label="Release wizard steps"', 1)[0]
    assert 'data-lucide="clipboard-check" class="h-5 w-5"' in release
    assert 'aria-label="Release Governance"' in release
    assert detail.count('name="tenant-governance"') == len(names)
    assert detail.count('tenant_detail_open_section ==') == len(names) + 1
    assert detail.count('group-open:rotate-180') == len(names) + 1
    for id_ in names:
        assert f'<details id="{id_}" name="tenant-governance"' in detail
    assert '<summary class="flex min-h-20 cursor-pointer' in detail
    for name in ('Release Governance', 'Platform Admin Handback',
                 'Lifecycle controls'):
        assert name in detail
    assert '<details id="tenant-provider-authority"' not in detail
    assert '<details id="tenant-lifecycle-actions"' in detail
    assert 'name="tenant-governance"' not in detail.split('id="tenant-lifecycle-actions"', 1)[1].split('</details>', 1)[0]
    assert 'tenant-release-stage-readiness' in detail
    assert 'tenant-release-stage-inventory' in detail
    assert 'tenant-release-stage-approval' in detail
    assert 'tenant-release-stage-finalize' in detail
    assert 'aria-label="Release wizard steps"' in detail
    assert 'id="tenant-release-workflow-details"' not in detail
    assert "{% if tenant_release_step == 'scope' %}" in detail
    assert "{% elif tenant_release_step == 'handoff' %}" in detail
    assert "{% elif tenant_release_step == 'approval' %}" in detail
    assert 'aria-current="step"' in detail
    assert 'aria-label="Release wizard previous and next"' in detail
    assert "tenant_detail_section" in detail
    assert 'max-h-72' not in detail
    assert "destructive_modal.render('tenant-decommission-modal'" in detail



def test_short_hero_subtitle_and_no_quick_links_regression():
    detail = read(DETAIL)
    assert 'Manage Tenant governance, provider authority, and lifecycle with committed evidence.' in detail
    assert 'Govern Tenant ownership, Namespace allocations' not in detail
    assert 'Quick Links' not in detail
    assert 'Tenant ID' in detail
    assert 'Identity &amp; Governance' in detail
    assert 'data-kaori-tenant-record-sheet' in detail
    assert 'No Tenant description has been recorded.' in detail


def test_release_wizard_only_one_step_renders_and_old_forms_are_preserved():
    detail = read(DETAIL)
    common = read('app/kubernetes/tenant/route_common.py')
    assert 'aria-label="Release wizard steps"' in detail
    assert 'aria-label="Release wizard active step"' in detail
    assert detail.count('href="{{ tenant_release_step_urls[') >= 7
    assert "requested_step if requested_step in steps else 'scope'" in common
    assert "'scope', 'handoff', 'approval', 'finalize'" in common
    assert "request.values.get('tenant_release_step')" in common
    assert "request.values.get('release_step')" in common
    assert "release_step=context['tenant_release_step']" in common
    assert 'Moving between steps does not approve a plan or bypass blockers.' not in detail
    assert 'Independent approval or an external reference alone cannot authorize provider handoff.' not in detail
    release = detail.split('id="tenant-release-governance"', 1)[1].split(
        'id="tenant-native-handback"', 1
    )[0]
    assert release.count('<form ') == 15
    assert release.count('name="tenant_release_step"') == 15
    assert 'id="tenant-release-stage-readiness"' in release
    assert 'id="tenant-release-stage-inventory"' in release
    assert 'id="tenant-release-stage-approval"' in release
    assert 'id="tenant-release-stage-finalize"' in release



def test_review_scope_is_scan_friendly_but_keeps_authoritative_blockers():
    detail = read(DETAIL)
    review = detail.split('id="tenant-release-stage-readiness"', 1)[1].split(
        "{% elif tenant_release_step == 'handoff' %}", 1
    )[0]
    assert 'Scope readiness' in review
    assert 'Review coverage' in review
    assert 'Provider resources' in review
    assert 'Allocation ownership' in review
    assert 'Governance dependencies' in review
    assert 'condition{{' in review
    assert 'View recorded conditions' in review
    assert 'aria-label="Release blockers"' in review
    assert 'row.release_preflight.blockers|length' in review
    assert 'for blocker in row.release_preflight.blockers' in review
    assert '{{ blocker }}' in review
    assert 'review_tenant_release_route' in review
    assert review.count('<form ') == 1
    assert 'Latest Release Review' not in review
    assert 'list-disc space-y-2' not in review
    assert 'row.release_preflight.status' in review
