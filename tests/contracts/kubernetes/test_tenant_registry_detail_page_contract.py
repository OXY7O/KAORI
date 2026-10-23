"""Tenant Registry → approved two-column KAORI Hero and governed accordion (#1073).

Reuses canonical page_hero context panel and the approved visual reference;
all existing governance services, CSRF forms and provider authority are unchanged.
"""

import re
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
    actions = registry.split('<td class="{{ table_ui.cell_classes(action=true) }} align-middle">', 1)[1].split(
        '</td>', 1
    )[0]
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
    assert 'htmx-indicator pointer-events-none fixed' in detail
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
    assert 'macro context_panel_classes() -' in hero
    assert '{{ context_panel_classes() }}' in hero
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
    overview = detail.split('id="tenant-detail-snapshot"', 1)[1].split('aria-label="Tenant management sections"', 1)[0]
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
    assert "tenant.provider_key|replace('_', ' ')|title" in detail
    assert re.search(r"tenant\.ownership_status\|replace\('_', ' '\)\s*\|title", overview)
    assert re.search(r"tenant\.reconciliation_authority\|replace\('_', ' '\)\s*\|title", overview)
    assert "tenant.lifecycle_status == 'ready'" in overview
    assert 'table_label.status_label(' in overview
    assert '{{ tenant.generation }}' in overview
    assert 'tenant.created_at.strftime("%Y-%m-%d %H:%M")' in overview
    assert 'tenant.updated_at.strftime("%Y-%m-%d %H:%M")' in overview
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
    assert [detail.index(label) for label in labels] == sorted(detail.index(label) for label in labels)
    assert 'tenant-namespace-attachment' not in detail
    assert 'data-capsule-namespace-attach' not in detail
    assert "tenant.ownership_status == 'adopted'" in detail
    assert "tenant.provider_key == 'native_kubernetes'" in detail
    assert "tenant.provider_key == 'capsule'" in detail
    assert "current_user.has_permission('clusters.manage')" in detail


def test_release_evidence_is_readable_full_width_without_nested_scroll():
    detail = read(DETAIL)
    release = detail.split('id="tenant-release-governance"', 1)[1].split('id="tenant-native-handback"', 1)[0]
    for label in (
        'Scope readiness',
        'Provider handoff scope',
        'Independent Approval and Handoff',
        "('finalize', 'Verify & Finalize', 'Read-back & Release')",
        'aria-label="Release blockers"',
        'aria-label="Provider handoff inventory"',
        'aria-label="Release wizard active step"',
        'aria-label="Scope review coverage"',
        'View recorded conditions',
    ):
        assert label in release
    assert 'divide-y divide-outline-subtle' in release
    assert 'max-h-72' not in release
    # Only the bounded Capsule exact-transfer resource list may scroll; the
    # primary Release evidence and wizard stages remain full-width/readable.
    assert release.count('overflow-y-auto') == 1
    assert 'max-h-44 overflow-y-auto' in release
    assert 'aria-label="Capsule exact transfer resource list"' in release
    assert 'text-sm leading-6' in release
    assert release.count('<form ') == 20


def test_release_handoff_inventory_is_structured_with_full_on_demand_identifiers():
    detail = read(DETAIL)
    handoff = detail.split('id="tenant-release-stage-inventory"', 1)[1].split(
        "{% elif tenant_release_step == 'approval' %}", 1
    )[0]
    Environment().parse(detail)
    assert 'aria-label="Provider handoff inventory"' in handoff
    assert 'aria-label="Recorded provider handoff resources"' in handoff
    assert 'row.release_preflight.handoff_components|length' in handoff
    assert 'row.release_preflight.handoff_required_count' in handoff
    assert 'for item in row.release_preflight.handoff_components' in handoff
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
    assert "item.ownership|replace('_', ' ') |title" in handoff
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
    assert 'row.release_preflight.handoff_components|length' in handoff
    assert 'flex min-w-0 flex-wrap items-baseline gap-x-3' in handoff
    assert 'This does not authorize Release.' in handoff
    assert 'Run Review Release to collect' in handoff
    assert '<form ' not in handoff


def test_release_wizard_actions_are_compact_on_desktop_and_full_width_on_mobile():
    detail = read(DETAIL)
    Environment().parse(detail)
    release = detail.split('id="tenant-release-governance"', 1)[1].split('id="tenant-native-handback"', 1)[0]

    # Step 1 keeps its full-width evidence surface and responsive primary CTA;
    # Step 2 is an evidence-only inventory with no mutation forms.
    stage_one = release.split('id="tenant-release-stage-inventory"', 1)[0]
    stage_two = release.split('id="tenant-release-stage-inventory"', 1)[1].split(
        "{% elif tenant_release_step == 'approval' %}", 1
    )[0]
    assert 'aria-label="Committed Release review status"' in stage_one
    assert 'w-full shrink-0 sm:w-auto' in stage_one
    assert '<form ' not in stage_two

    forms = re.findall(r'<form\b.*?</form>', release, flags=re.DOTALL)
    assert len(forms) == 20
    assert 'tenant.review_tenant_release_route' in forms[0]
    for form in forms[1:]:
        opening = form.split('>', 1)[0]
        assert re.search(r'class="[^"]*\bw-full\b', opening)
        button = re.search(r'<button type="submit"\s+class="([^"]+)"', form)
        assert button is not None
        assert {'w-full', 'sm:w-auto'}.issubset(button.group(1).split())
        assert 'hx-post=' in form
        assert 'name="csrf_token"' in form
        assert 'name="tenant_release_step"' in form

    # Short input forms use the narrower preset, while confirmation panels
    # retain adequate space for complete permission and provider scope copy.
    prepare = next(form for form in forms if 'tenant.prepare_tenant_release_handoff_route' in form)
    assert 'w-full max-w-xl' in prepare.split('>', 1)[0]
    assert 'name="successor_owner"' in prepare
    assert 'name="change_reference"' in prepare
    for route, expected_layout in (
        ('tenant.accept_native_successor_handoff_route', 'w-full mt-3 space-y-3'),
        ('tenant.execute_native_release_handoff_route', 'lg:w-3/5'),
        ('tenant.finalize_verified_native_release_route', 'max-w-4xl'),
        ('tenant.finalize_verified_capsule_release_route', 'max-w-2xl'),
    ):
        form = next(item for item in forms if route in item)
        assert expected_layout in form.split('>', 1)[0]

    # The Step 4 flex-column fallback CTA must not stretch on desktop.
    fallback = next(form for form in forms if 'tenant.release_tenant_governance_route' in form)
    assert 'w-full sm:w-auto self-start' in fallback
    assert 'id="tenant-release-stage-finalize"' in release


def test_release_step_three_preparation_uses_balanced_governance_panels():
    detail = read(DETAIL)
    Environment().parse(detail)
    approval = detail.split('id="tenant-release-stage-approval"', 1)[1].split(
        "{% elif tenant_release_step == 'finalize' %}", 1
    )[0]
    preparation = approval.split("{% if row.release_handoff_preparation_state == 'available'", 1)[1].split(
        '{% else %}', 1
    )[0]

    # Match the existing Step 4 3:2 panel pattern without constraining other
    # approved, blocked, expired or provider-recovery evidence branches.
    assert approval.count('data-release-handoff-preparation-layout') == 1
    assert 'data-release-handoff-preparation-layout' in preparation
    assert 'lg:grid-cols-5' in preparation
    assert 'lg:col-span-3' in preparation
    assert 'lg:col-span-2' in preparation
    assert preparation.count('<section ') == 2
    assert 'aria-labelledby="tenant-release-preparation-heading"' in preparation
    assert 'id="tenant-release-preparation-heading"' in preparation
    assert 'aria-labelledby="tenant-release-approval-boundaries-heading"' in preparation
    assert 'id="tenant-release-approval-boundaries-heading"' in preparation
    assert 'aria-label="Handoff approval sequence"' in preparation

    # The right panel is read-only guidance, never another authorization path,
    # implicit approval checkbox or invented provider-completion indicator.
    boundaries = preparation.split('id="tenant-release-approval-boundaries-heading"', 1)[1]
    assert boundaries.count('<li ') == 3
    assert '<form ' not in boundaries
    assert '<button ' not in boundaries
    assert 'A separate authorized operator must approve this exact plan.' in boundaries
    assert 'does not verify consent or transfer provider ownership.' in boundaries
    assert 'Release remains gated by committed verification' in boundaries

    # Original submission stays intact, bounded at desktop and touch-friendly
    # on mobile; no changes to the requester identity/CSRF/HTMX contract.
    assert preparation.count('<form ') == 1
    assert 'tenant.prepare_tenant_release_handoff_route' in preparation
    assert 'name="csrf_token"' in preparation
    assert 'name="successor_owner"' in preparation
    assert 'name="change_reference"' in preparation
    assert 'w-full max-w-xl mt-3 space-y-2' in preparation
    assert 'w-full sm:w-auto' in preparation
    assert 'Prepare Handoff' in preparation


def test_release_step_three_separates_plan_review_external_claim_and_platform_admin():
    detail = read(DETAIL)
    approval = detail.split('id="tenant-release-stage-approval"', 1)[1].split(
        "{% elif tenant_release_step == 'finalize' %}", 1
    )[0]
    Environment().parse(detail)
    assert 'Independent Approval and Handoff' in approval
    assert 'aria-label="Governed handoff workflow"' in approval
    assert 'data-release-handoff-approval' in approval
    assert 'One active plan per Tenant.' in approval
    assert 'requester and independent reviewer must be different' in approval
    # Section-title guidance reuses canonical popover; never hide required gating text.
    header = approval.split('</header>', 1)[0]
    assert header.count("info_tip.render('tenant-release-approval-handoff-help'") == 1
    assert "'Independent Approval and Handoff'" in header
    assert "variant='guide'" in header
    assert "placement='left'" in header
    assert 'The requester and reviewer must be different authorized operators.' in header
    assert 'External acceptance, provider read-back and Release require separate evidence.' in header
    assert header.index('Independent Approval and Handoff</h4>') < header.index(
        "info_tip.render('tenant-release-approval-handoff-help'"
    )

    # An acknowledged plan is locked without inventing approval or provider transfer.
    assert re.search(r'role="status"\s+aria-label="Active handoff plan"', approval)
    assert 'data-release-plan-review-cards' in approval
    assert 'md:border-r md:border-outline-subtle md:pr-5' in approval
    assert 'aria-label="Planned Handoff Record"' in approval
    assert 'gap-x-5 gap-y-2 sm:grid-cols-2' in approval
    assert 'gap-x-2 gap-y-0.5 border-b border-outline-subtle pb-3' in approval
    # A previous two-card redesign dropped the enclosing Jinja endif and
    # broke every Tenant detail GET with TemplateSyntaxError on the next elif.
    # Environment().parse(detail) above must compile the complete template.
    assert re.search(
        r'{%\s*endif\s*%}\s*</div>\s*{%\s*endif\s*%}\s*{%\s*if handoff_plan\s*%}'
        r'\s*<dl class="flex min-w-0 flex-wrap',
        approval,
    )
    assert 'md:grid-cols-2' in approval
    assert 'aria-label="Independent review status"' in approval
    assert 'aria-label="Planned Handoff Record"' in approval
    assert 'Scope locked to this plan.' in approval
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

    # Approved Native handoff uses two responsive peer surfaces without
    # forced equal-height whitespace; Capsule retains full-width approval.
    assert 'data-release-accepted-handoff-workspace' in approval
    assert 'data-release-accepted-handoff-actions' in approval
    assert 'lg:border-r lg:border-outline-subtle lg:pr-6' in approval
    assert 'border-b border-outline-subtle py-3' in approval
    assert 'rounded-xl border border-outline-subtle bg-surface-card p-4 sm:p-5 lg:col-span-1' not in approval
    assert 'data-release-accepted-handoff-evidence' in approval
    assert 'lg:grid-cols-2' in approval
    assert 'lg:col-span-3' in approval
    assert 'lg:col-span-2' in approval
    assert 'aria-label="External handoff and provider read-back"' in approval
    assert 'External Handoff &amp; Read-Back' in approval
    assert 'Evidence Boundaries' in approval
    assert 'data-release-evidence-boundaries' in approval
    assert 'mt-4 border-t border-outline-subtle py-3' in approval
    assert '<summary class="cursor-pointer text-xs font-semibold text-content-primary' in approval
    # Actions and evidence must be peer surfaces, not stacked bordered cards.
    assert 'items-start gap-x-7 gap-y-5 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]' in approval
    assert 'Handoff Actions' in approval
    assert 'Governed actions, when eligible.' in approval
    assert 'class="w-full mt-3 space-y-3"' in approval
    assert 'class="w-full mt-3 space-y-3 border-t border-outline-subtle pt-3"' in approval
    assert 'aria-label="Independent Platform Admin required"' in approval
    assert 'Another authorized Platform Admin must verify and accept.' in approval
    assert 'References and dry-runs prove neither consent nor transfer.' in approval
    assert 'aria-label="External read-back prerequisites"' in approval
    assert 'mt-4 flex min-w-0 items-start gap-2.5 py-2' in approval
    assert 'External Handoff &amp; Read-Back' in approval
    assert approval.count('data-release-accepted-handoff-evidence') == 1
    assert approval.count('External Handoff Inspection Unavailable') == 1
    assert (
        approval.index('data-release-accepted-handoff-workspace')
        < approval.index('data-release-accepted-handoff-evidence')
        < approval.index(
            "{% if tenant.provider_key == 'capsule' %}", approval.index('data-release-accepted-handoff-workspace')
        )
    )
    assert 'I reviewed the successor, change record, and provider evidence; no transfer occurred.' in approval
    for heading in (
        'Approval Boundaries',
        'Prepare Handoff Plan',
        'Planned Handoff Record',
        'Independent Approval and Handoff',
    ):
        assert heading in approval

    # Recorded independent review does not imply verified successor acceptance.
    assert 'Independent review recorded. External owner acceptance' in approval
    assert re.search(r'role="status"\s+aria-label="External successor evidence"', approval)
    assert 'successor_claim.plan_sha256 == handoff_plan.plan_sha256' in approval
    assert 'Record for external verification only; this does not prove acceptance or authorize transfer.' in approval
    assert 'name="confirm_successor_reference"' in approval
    assert 'External Reference Unverified' in approval
    assert '<span class="text-xs font-semibold text-content-primary">External Reference</span>' in approval
    assert '{{ successor_claim.successor_reference }}' in approval
    assert 'not an additional approval' in approval
    assert 'provider ownership remains unchanged' in approval

    # Exact platform-admin permission/identity action is preserved verbatim.
    assert 'aria-label="Platform Admin provider verification"' in approval
    assert 'Platform Admin Verification' in approval
    assert 'registered Kubernetes X.509 connection' in approval
    assert 'tenant.accept_native_successor_handoff_route' in approval
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
    # Conditional Native/Capsule plans and independent successor/recovery paths
    # contribute 19 separate Stage 3 forms; all 23 page forms still enforce CSRF.
    assert approval.count('<form ') == 19
    assert detail.count('<form ') == 23
    assert detail.count('name="csrf_token"') == 23


def test_native_platform_admin_acceptance_requires_verified_cluster_tls_in_ui():
    detail = read(DETAIL)
    approval = detail.split('id="tenant-release-stage-approval"', 1)[1].split('id="tenant-release-stage-finalize"', 1)[
        0
    ]
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
    before_acceptance = approval.split('tenant.accept_native_successor_handoff_route', 1)[0]
    assert 'aria-label="Kubernetes verified TLS prerequisite"' in before_acceptance
    assert 'if not row.cluster or not row.cluster.kubernetes_connection' in before_acceptance
    assert '{% else %}' in before_acceptance
    assert "url_for('cluster.edit_cluster', cluster_id=row.cluster.id)" in approval
    assert "current_user.has_permission('clusters.manage')" in approval
    assert 'Full Validation' in approval
    assert 'name="confirm_successor_acceptance"' in approval

    # Step 4 action explains the same canonical connection requirement.
    assert 'Next Required Action' in final
    assert 'Verified TLS Required' in final
    assert 'Test Connection and complete Full Validation' in final
    assert "url_for('cluster.edit_cluster', cluster_id=row.cluster.id)" in final

    # Existing operations are not deleted and may still render when eligible.
    assert detail.count('<form ') == 23
    assert detail.count('name="csrf_token"') == 23


def test_step_three_freshness_matches_native_readiness_and_hides_stale_acceptance():
    detail = read(DETAIL)
    step = detail.split('id="tenant-release-stage-approval"', 1)[1].split('id="tenant-release-stage-finalize"', 1)[0]
    Environment().parse(detail)

    assert "row.get('native_release_readiness')" in step
    assert 'row.native_release_readiness.approval_expired' in step
    assert 'row.native_release_readiness.review_expired' in step
    assert "table_label.status_label('Approval Expired', 'warning')" in step
    assert "table_label.status_label('Review Expired', 'warning')" in step
    assert re.search(r'role="status"\s+aria-label="Expired Native handoff evidence"', step)
    assert "tenant_release_step_urls['finalize']" in step
    assert 'View recovery steps' in step
    # Backend already checks both freshness conditions; UI must not offer the
    # successor-acceptance form based only on plan-SHA match.
    accept = step.split('tenant.accept_native_successor_handoff_route', 1)[0]
    assert 'row.native_release_readiness.approval_complete' in accept
    assert 'row.native_release_readiness.review_complete' in accept
    assert 'handoff_plan.requested_by != current_user.id' in accept
    assert 'name="confirm_successor_acceptance"' in step
    # The reviewed approval stage exposes independent native/Capsule actions
    # without conflating decision, dry-run and provider read-back authority.
    assert step.count('<form ') == 11


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
    assert 'Next Required Action' in step

    # Verification Required is now informative for each committed readiness
    # state; the same Step 3 navigation remains read-only and role-aware.
    verification = step.split('data-release-next-action-verification', 1)[1].split(
        '{% endif %}\n                                        </section>', 1
    )[0]
    assert 'aria-label="Native handoff verification next action"' in step
    assert 'Required Next Steps' in verification
    assert 'aria-label="Native handoff verification steps"' in verification
    assert 'verify_steps' in verification
    for message in (
        'Independent Platform Admin Required',
        'Verify Provider & Accept as Platform Admin',
        'Complete Native Provider Handoff',
        'Complete Release Finalization',
        'Review Exact Plan',
        'Verify Provider Access',
        'Record Acceptance',
        'Preview Native Transfer',
        'Execute Accepted Handoff',
        'Verify Read-Back',
        'Finalize Authorized Release',
    ):
        assert message in step
    assert 'Open Handoff Controls' in verification
    assert 'hx-get=' in verification
    assert '<form ' not in verification
    assert 'data-release-next-action-pending' in step
    assert 'aria-label="Independent approval required"' in step
    assert 'Remaining Approval Path' in step
    assert 'aria-label="Remaining Release approval gates"' in step
    assert 'The requester cannot self-approve;' in step
    assert 'Open Approval &amp; Handoff' in step
    # Match the existing Step 3 Approval boundaries numbered-list pattern,
    # without the previous three-card grid or additional approval forms.
    approval_pending = step.split('{% elif not native_cycle.approval_complete %}', 1)[1].split(
        '{% elif not row.cluster or not row.cluster.kubernetes_connection', 1
    )[0]
    approval_list = approval_pending.split('data-release-approval-path-list', 1)[1].split('</ol>', 1)[0]
    assert 'divide-y divide-outline-subtle' in approval_pending
    assert 'xl:grid-cols-3' not in approval_pending
    assert approval_list.count('<li class=') == 3
    for title, sentence in (
        ('Independent Review', 'A separate authorized operator reviews the exact plan and evidence.'),
        ('Provider Acceptance', 'An authorized Platform Admin verifies and records successor acceptance.'),
        ('Verify &amp; Finalize', 'Verify provider handoff and read-back before Release.'),
    ):
        assert title in approval_list
        assert sentence in approval_list
    assert 'hx-get=' in approval_pending
    assert '<form ' not in approval_pending
    assert re.search(r'role="status"\s+aria-label="Expired handoff recovery"', step)
    assert 'native_cycle.approval_expired' in step
    assert 'native_cycle.review_expired' in step
    # A stale provider preflight needs actionable read-only guidance, not a
    # nearly empty action panel or a misleading implicit Release approval.
    review_expired = step.split('{% elif native_cycle.review_expired %}', 1)[1].split(
        '{% elif not native_cycle.approval_complete %}', 1
    )[0]
    assert 'data-release-next-action-review-expired' in review_expired
    assert 'aria-label="Expired provider review next action"' in review_expired
    assert 'Refresh the Provider Review' in review_expired
    assert 'Required Next Steps' in review_expired
    assert 'aria-label="Expired provider review recovery steps"' in review_expired
    for instruction in (
        'Run Review Release',
        'Inspect Committed Evidence',
        'Revalidate Handoff Approval',
    ):
        assert instruction in review_expired
    assert 'does not approve the handoff, transfer ownership or authorize Release.' in review_expired
    assert "tenant_release_step_urls['scope']" in review_expired
    assert 'hx-get=' in review_expired
    assert '<form ' not in review_expired
    assert 'native_cycle.restart_blocked_by_readback' in step
    # Expired approval is one clean ordered recovery list, with the original
    # requester-only restart and blocked-by-read-back guards unchanged.
    expired_action = step.split('{% elif native_cycle.approval_expired %}', 1)[1].split(
        '{% elif native_cycle.review_expired %}', 1
    )[0]
    assert 'data-release-next-action-approval-expired' in expired_action
    assert 'aria-label="Expired handoff recovery"' in expired_action
    assert 'Renew Independent Approval' in expired_action
    # The recovery list already has a bottom divider. A second border on
    # the requester form or alternative guidance created duplicate rules.
    assert 'Expired approval is audit-only; it cannot authorize acceptance or Release.' in expired_action
    assert 'divide-y divide-outline-subtle border-y border-outline-subtle' in expired_action
    assert 'border-t border-outline-subtle' not in expired_action
    assert 'class="mt-3 flex w-full min-w-0 flex-col items-start gap-3"' in expired_action
    for role_message in (
        'native_cycle.restart_blocked_by_readback',
        'row.release_handoff_plan.requested_by == current_user.id',
        'row.release_handoff_plan.requested_by != current_user.id',
        'Restart requires the original requester with both Tenant and Integrations management permissions',
    ):
        assert role_message in expired_action
    assert 'aria-label="Expired handoff approval recovery steps"' in expired_action
    assert expired_action.count('<li class=') == 3
    for instruction in (
        'Verify Provider Ownership',
        'Restart the Expired Plan',
        'Request Governed Recovery',
        'Obtain Independent Approval',
    ):
        assert instruction in expired_action
    assert 'native_cycle.restart_blocked_by_readback' in expired_action
    assert 'native_cycle.restart_required' in expired_action
    assert 'row.release_handoff_plan.requested_by == current_user.id' in expired_action
    assert 'name="confirm_handoff_restart"' in expired_action
    assert 'Restart Expired Handoff Plan' in expired_action
    assert expired_action.count('<form ') == 1
    assert 'native_cycle.restart_required' in step
    assert 'native_cycle.restart_zero_transfer_recheck_required' in step
    assert 'Read-back: 0 transferred.' in step
    assert 'Restart rechecks UID/resourceVersion, ownership and dependencies;' in step
    assert 'no automatic clearance.' in step
    assert 'data-release-restart-recheck-note' in step
    assert 'data-release-restart-confirmation' in step
    assert 'I verified provider ownership is unchanged before restarting.' in step
    assert 'row.release_handoff_plan.requested_by == current_user.id' in step
    assert "current_user.has_permission('tenant.manage')" in step
    assert "current_user.has_permission('integrations.manage')" in step
    assert 'restart_expired_tenant_release_handoff_route' in step
    assert 'name="confirm_handoff_restart"' in step
    assert re.search(r'value="restart"\s+required', step)
    assert 'Restart Expired Handoff Plan' in step
    assert 'This account is not the original requester' in step
    assert 'row.release_handoff_plan.requested_by != current_user.id' in step
    assert 'Restart requires the original requester with both Tenant and Integrations management permissions' in step
    assert 'Governed recovery review is required; automatic restart is prohibited.' in step
    assert "tenant_release_step_urls['scope']" in step
    assert "tenant_release_step_urls['approval']" in step
    assert 'External reference recorded; not successor consent.' in step
    assert 'Dry-run and external references are not consent.' in step
    assert 'Kubernetes stays authoritative' in step
    # Step 4 exposes distinct assessment, restart and authorization
    # recovery POSTs. None is inferred as automatically authorized.
    assert step.count('<form ') == 5
    assert detail.count('<form ') == 23
    assert detail.count('name="csrf_token"') == 23


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
    assert 'verified_consent.accepted_by == current_user.id' in approval

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
    assert "'Recovery Required'" in projection
    assert "if label == 'KAORI provider handoff' and provider_handoff_recovery_required" in projection
    assert "'provider_handoff_recovery_required': provider_handoff_recovery_required" in projection
    assert detail.count('<form method="post"') == 23
    assert detail.count('name="csrf_token"') == 23
    assert detail.count('hx-post=') == 23


def test_expired_approval_does_not_offer_a_doomed_native_dry_run():
    detail = read(DETAIL)
    approval = detail.split('id="tenant-release-stage-approval"', 1)[1].split(
        "{% elif tenant_release_step == 'finalize' %}", 1
    )[0]
    Environment().parse(detail)
    assert 'tenant.dry_run_native_release_handoff_route' in approval
    before_preview = approval.split('tenant.dry_run_native_release_handoff_route', 1)[0]
    assert 'row.native_release_readiness.approval_complete' in before_preview
    assert 'row.native_release_readiness.review_complete' in before_preview
    assert 'Preview Native Transfer' in approval
    assert detail.count('<form method="post"') == 23
    assert detail.count('name="csrf_token"') == 23


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
    assert "'no_transfer_assessment_candidate': no_transfer_assessment_candidate" in readiness
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

    assert 'def assess_native_no_transfer_recovery_route(' in routes
    assert 'def authorize_native_no_transfer_recovery_route(' in routes
    assert "confirmed=request.form.get('confirm_no_transfer_assessment') == 'assess'" in routes
    assert "confirmed=request.form.get('confirm_no_transfer_authorization') == 'authorize'" in routes
    assert "'no_transfer_authorized_current': no_transfer_authorized_current" in readiness
    assert 'def _verify_original_provider_state(' in service
    assert 'summarize_native_handoff_recovery(' in service
    assert "proof.get('status') != 'provider_handoff_not_started'" in service
    assert 'def require_authorized_no_transfer_restart(' in service
    assert 'require_authorized_no_transfer_restart(' in approval
    assert '_verify_original_provider_state(' in approval
    assert 'no_transfer_recovery_assessment_sha256' in approval

    assert detail.count('<form method="post"') == 23
    assert detail.count('name="csrf_token"') == 23
    assert detail.count('hx-post=') == 23


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
    assert 'External Handoff Inspection Unavailable' in approval
    assert 'Original requester must restart with a new SHA and independent review.' in approval
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
    assert 'Last read-back:' in approval
    assert 'Historical evidence does not verify external acceptance' in approval

    assert "_checked_recently((successor_claim or {}).get('recorded_at'))" in readiness
    assert 'external_readback_prerequisites_current' in readiness
    assert "'external_reference_current': external_reference_current" in readiness
    assert "and (dry_run or {}).get('release_authorized') is False" in readiness
    # Render-gating does not delete or silently replace original protected POST.
    assert detail.count('<form method="post"') == 23
    assert detail.count('name="csrf_token"') == 23
    assert detail.count('hx-post=') == 23


def test_exact_governance_forms_return_to_same_page_and_global_toast():
    detail = read(DETAIL)
    common = read('app/kubernetes/tenant/route_common.py')
    toast = read('app/templates/components/operational_toast.html')
    assert detail.count('<form ') == 23
    assert detail.count('name="csrf_token"') == 23
    assert detail.count('name="tenant_detail_id"') == 23
    assert detail.count('registry_state.items()') == 23
    assert detail.count('hx-target="#tenant-management-detail"') == 23
    assert detail.count('hx-select="#tenant-management-detail"') == 23
    assert detail.count('hx-post=') == 23
    assert 'name="tenant_detail_view"' not in detail
    assert detail.count('name="tenant_detail_section"') == 23
    assert detail.count('name="tenant_release_step"') == 20
    assert 'tenant_release_step_urls' in common
    assert "context['tenant_release_step']" in common
    assert "context['tenant_detail_open_section'] = active_section" in common
    assert "detail_id = str(request.form.get('tenant_detail_id')" in common
    assert "'kubernetes/tenant/partials/_tenant_management_detail.html'" in common
    assert re.search(r"'tenant\.tenant_detail',\s+tenant_id=detail_id", common)
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
    assert detail.count('hx-select="#tenant-management-detail"') == 23
    assert detail.count('hx-target="#tenant-management-detail"') == 23
    assert detail.count('hx-select="#tenant-release-governance"') == 13
    assert detail.count('hx-target="#tenant-release-governance"') == 13
    assert detail.count('hx-swap="outerHTML show:none focus-scroll:false"') == 36
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
    assert "role=\"{{ 'alert' if action_status == 'error' else 'status' }}\"" in detail
    assert 'data-release-confirmation-guidance' in detail
    assert 'A checked box authorizes one submission, not a recorded approval.' in detail
    assert 'The confirmation resets after submission.' in detail
    assert 'hx-history="false"' in detail
    assert detail.count('hx-disabled-elt="find button[type=\'submit\']"') == 23
    assert detail.count('disabled:cursor-progress disabled:opacity-60') == 20
    assert 'Processing Tenant request…' in detail
    assert 'fixed bottom-4 right-4' in detail
    assert detail.count('<form method="post"') == 23
    assert detail.count('name="csrf_token"') == 23
    assert detail.count('hx-post=') == 23
    assert detail.count('name="tenant_release_step"') == 20


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
    assert 'def tenant_detail(tenant_id: str):' in routes
    assert '_tenant_detail_context(tenant_id)' in routes
    assert 'get_tenant_registry_context(tenant_id=tenant_id, per_page=1)' in common
    assert 'if not rows:' in common
    assert 'abort(404)' in common
    assert 'query.filter(Tenant.id == tenant_id)' in context
    assert 'runtime_adapter.build_client(' not in common
    assert 'runtime_adapter.build_client(' not in context


def test_independent_work_inbox_deep_link_targets_release_section():
    inbox = read('app/kubernetes/tenant/approval_inbox.py')
    assert "'tenant.tenant_detail'" in inbox
    assert "_anchor='tenant-release-governance'" in inbox
    assert "tenant_detail_section='release'" in inbox
    assert "release_step='approval'" in inbox
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
    assert '{% import "components/operational_section_card.html" as operational_section_card %}' in detail
    assert '{% import "components/resource_posture_grid.html" as resource_posture_grid %}' in detail
    assert 'operational_section_card.render(' in fleet
    assert 'resource_posture_grid.render(estate_metrics, columns=5)' in fleet
    assert 'border-b border-outline-subtle' in card
    assert 'grid gap-px bg-outline-subtle' in posture
    assert 'columns == 5' in posture  # four-column responsive fallback also shared
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
    assert 'role="note"' in detail
    assert 'aria-label="Authority Boundary"' in detail
    statement = (
        'KAORI presents committed governance evidence; Kubernetes or Capsule '
        'remains authoritative for provider resources.'
    )
    assert detail.count(statement) == 1


def test_compact_provider_and_lifecycle_evidence_without_duplicate_accordions():
    detail = read(DETAIL)
    overview = detail.split('id="tenant-detail-snapshot"', 1)[1].split('aria-label="Tenant management sections"', 1)[0]

    # Provider values are already shown in the existing Overview facts.
    assert overview.count('id="tenant-provider-authority"') == 1
    assert '<details id="tenant-provider-authority"' not in detail
    assert "tenant.provider_key|replace('_', ' ')|title" in detail
    assert re.search(r"tenant\.reconciliation_authority\|replace\('_', ' '\)\s*\|title", overview)
    statement = (
        'KAORI presents committed governance evidence; Kubernetes or Capsule '
        'remains authoritative for provider resources.'
    )
    assert detail.count(statement) == 1
    assert overview.count(statement) == 1
    assert detail.count('aria-label="Authority Boundary"') == 1
    assert 'role="note"' in overview
    assert '<aside' not in overview

    # Lifecycle is a native Overview disclosure, not a fifth standalone card.
    assert overview.count('id="tenant-lifecycle-actions"') == 1
    assert 'Lifecycle controls' in overview
    assert "tenant_detail_open_section == 'lifecycle'" in overview
    assert 'name="tenant-governance"' not in overview
    assert 'row.decommission_preflight' in overview
    assert 'tenant.decommission_tenant_route' in overview
    assert 'data-destructive-modal-open' in overview
    assert 'data-destructive-submit-button-id=' in overview
    assert 'aria-label="Decommission blockers"' in overview
    assert 'for blocker in decommission.blockers' in overview
    assert '{{ blocker }}' in overview
    assert "destructive_modal.render('tenant-decommission-modal'" in detail
    assert detail.count('name="csrf_token"') == 23
    assert detail.count('<form ') == 23


def test_release_is_permanent_and_other_governance_sections_remain_accessible():
    detail = read(DETAIL)
    release = detail.split('id="tenant-release-governance"', 1)[1].split('id="tenant-native-handback"', 1)[0]
    names = ('tenant-native-handback', 'tenant-capsule-handback')
    assert '<section id="tenant-release-governance"' in detail
    assert '<details id="tenant-release-governance"' not in detail
    assert '<summary' not in release.split('aria-label="Release wizard steps"', 1)[0]
    assert 'data-lucide="clipboard-check" class="h-5 w-5"' in release
    assert 'aria-label="Release Governance"' in release
    assert 'info_tip.render(' in release
    assert "'tenant-release-governance-help'" in release
    assert 'Independent plan approval is not external successor acceptance.' in release
    assert 'KAORI-mutated Namespace provider controls' in release
    assert 'KAORI-linked allocation ownership' in release
    assert 'Independent external handoff approval required.' in release
    assert 'Approve external handoff and verify provider state.' in release
    assert 'Exact recorded reason' in release
    assert detail.count('name="tenant-governance"') == len(names)
    assert detail.count('tenant_detail_open_section ==') == len(names) + 1
    assert detail.count('group-open:rotate-180') == len(names) + 1
    for id_ in names:
        assert f'<details id="{id_}"' in detail
        details = detail.split(f'<details id="{id_}"', 1)[1].split('>', 1)[0]
        assert 'name="tenant-governance"' in details
    assert '<summary class="flex min-h-20 cursor-pointer' in detail
    for name in ('Release Governance', 'Platform Admin Handback', 'Lifecycle controls'):
        assert name in detail
    assert '<details id="tenant-provider-authority"' not in detail
    assert '<details id="tenant-lifecycle-actions"' in detail
    assert (
        'name="tenant-governance"' not in detail.split('id="tenant-lifecycle-actions"', 1)[1].split('</details>', 1)[0]
    )
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
    assert 'tenant_detail_section' in detail
    assert 'max-h-72' not in detail
    assert "destructive_modal.render('tenant-decommission-modal'" in detail


def test_short_hero_subtitle_and_no_quick_links_regression():
    detail = read(DETAIL)
    assert 'Manage Tenant lifecycle and provider scope with committed evidence.' in detail
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
    release = detail.split('id="tenant-release-governance"', 1)[1].split('id="tenant-native-handback"', 1)[0]
    assert release.count('<form ') == 20
    assert release.count('name="tenant_release_step"') == 20
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


def test_release_guidance_notes_are_consistent_across_steps_without_changing_authority():
    detail = read(DETAIL)
    Environment().parse(detail)
    step_two = detail.split('id="tenant-release-stage-inventory"', 1)[1].split(
        "{% elif tenant_release_step == 'approval' %}", 1
    )[0]
    step_three = detail.split('id="tenant-release-stage-approval"', 1)[1].split(
        'id="tenant-release-stage-finalize"', 1
    )[0]
    step_four = detail.split('id="tenant-release-stage-finalize"', 1)[1].split(
        'aria-label="Release wizard previous and next"', 1
    )[0]

    assert detail.count('{% macro release_step_guidance(') == 1
    assert 'data-release-step-guidance' in detail
    assert 'border-outline-subtle bg-surface-elevated' in detail
    assert step_two.count('release_step_guidance(') == 2
    assert 'Run Review Release to collect the provider handoff inventory' in step_two
    assert 'This does not authorize Release.' in step_two
    assert 'release_step_guidance(' in step_three
    assert 'Run Review Release to determine whether handoff is required.' in step_three
    assert 'Run Review Release to establish committed scope' in step_four
    assert 'Resolve recorded conditions and independently verify the successor.' in step_four
    assert detail.count('<form ') == 23
    assert detail.count('name="csrf_token"') == 23
    assert detail.count('hx-post=') == 23


def test_release_review_scope_is_one_unified_committed_evidence_surface():
    detail = read(DETAIL)
    review = detail.split('id="tenant-release-stage-readiness"', 1)[1].split(
        "{% elif tenant_release_step == 'handoff' %}", 1
    )[0]
    Environment().parse(detail)
    assert 'aria-label="Committed Release review status"' in review
    assert 'aria-label="Scope review coverage"' in review
    assert 'sm:grid-cols-3' in review
    assert 'bg-kaori-primary' in review
    assert 'No dependency blockers recorded' in review
    assert 'Provider handoff and independent verification are still required.' in review
    assert 'View recorded conditions' in review
    assert review.count('<form ') == 1
    assert review.count('hx-post=') == 1
    assert 'for blocker in row.release_preflight.blockers' in review
    assert 'row.release_preflight.status' in review


def test_tenant_description_value_has_no_template_indentation() -> None:
    detail = read(DETAIL)
    overview = detail.split('id="tenant-detail-snapshot"', 1)[1].split('aria-label="Tenant management sections"', 1)[0]
    # Jinja whitespace trimming leaves the user's own multiline text unchanged.
    assert 'whitespace-pre-wrap break-words' in overview
    assert "{{- tenant.description or 'No Tenant description has been recorded.' -}}" in overview
    assert "{{ tenant.description or 'No Tenant description has been recorded.' }}" not in overview
    Environment().parse(detail)


def test_release_heading_uses_canonical_title_level_guide() -> None:
    detail = read(DETAIL)
    release_header = detail.split('id="tenant-release-governance"', 1)[1].split('aria-label="Release wizard steps"', 1)[
        0
    ]
    title = '<h2 class="text-lg font-semibold text-content-primary">Release Governance</h2>'
    guide_id = "'tenant-release-governance-help'"
    assert release_header.count(title) == 1
    assert release_header.count('info_tip.render(') == 1
    assert release_header.count(guide_id) == 1
    guide = release_header.split(guide_id, 1)[1].split(') }}', 1)[0]
    assert release_header.index(title) < release_header.index(guide_id)
    assert "placement='left'," in guide
    assert "variant='guide'" in guide
    assert 'Independent plan approval is not external successor acceptance.' in guide
    assert 'Provider handoff, verified read-back' in guide


def test_expired_release_review_has_compact_responsive_single_sentence() -> None:
    detail = read(DETAIL)
    expired = detail.split('data-release-next-action-review-expired', 1)[1].split(
        'aria-label="Expired provider review recovery steps"', 1
    )[0]
    copy = 'Kubernetes review expired; scope and fingerprint are stale for Release.'
    assert detail.count(copy) == 1
    assert copy in expired
    assert len(copy) <= 75
    assert copy.count('.') == 1
    assert 'The previous Kubernetes inventory review has expired.' not in detail
    assert 'whitespace-nowrap' not in expired
    assert 'Refresh the Provider Review' in expired
    assert 'Review Expired' in expired
    Environment().parse(detail)


def test_native_handoff_visual_density_remediation_preserves_safety() -> None:
    detail = read(DETAIL)
    approval = detail.split('id="tenant-release-stage-approval"', 1)[1].split('id="tenant-release-stage-finalize"', 1)[
        0
    ]
    final = detail.split('id="tenant-release-stage-finalize"', 1)[1]

    # Content hierarchy: concise status rows, unstretched peers, aligned actions.
    assert 'items-start gap-x-7 gap-y-5 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]' in approval
    assert 'data-release-accepted-handoff-actions' in approval
    assert 'data-release-accepted-handoff-evidence' in approval
    assert 'flex min-w-0 flex-col gap-1 border-b border-outline-subtle py-3' in approval
    assert 'Kubeconfig access verified; provider transfer remains separate.' in approval
    assert 'provider ownership unchanged.' in approval
    assert 'flex-col gap-3 border-y border-outline-subtle py-3 sm:flex-row' in approval
    assert 'data-tenant-native-dry-run-evidence' in approval
    assert 'name="confirm_native_handoff_dry_run"' in approval
    assert 'External Handoff Inspection Unavailable' in approval

    # A visual redesign never weakens native dry-run, mutation or finalization.
    for route in (
        'dry_run_native_release_handoff_route',
        'execute_native_release_handoff_route',
        'inspect_native_external_handoff_route',
    ):
        assert route in approval
    for required_field in (
        'confirm_native_handoff_dry_run',
        'confirm_native_handoff_execution',
        'confirm_native_handoff_readback',
    ):
        assert f'name="{required_field}"' in approval
    assert 'Partial failure requires recovery.' in approval
    assert 'No successor token or private key is required.' in approval
    assert 'historical Dry-Run Passed receipt may be expired' in approval

    release = final.split('tenant.finalize_verified_native_release_route', 1)[1]
    release = release.split('</form>', 1)[0]
    assert 'mx-auto mt-5 w-full max-w-4xl' in release
    assert 'Verified Native Transfer · Ready for Governance Release' in release
    assert 'confirm_native_release_finalization' in release
    assert 'Fresh provider read-back must preserve every Namespace' in release
    assert 'zero dependencies' in release
    assert 'Preserve all external Kubernetes resources.' in release

    # Entire page retains its existing privilege-gated mutation contracts.
    assert detail.count('<form method="post"') == 23
    assert detail.count('name="csrf_token"') == 23
    assert detail.count('hx-post=') == 23
    Environment().parse(detail)

def test_native_dry_run_compact_resource_rows_and_copy_reuse_shared_behavior() -> None:
    detail = read(DETAIL)
    approval = detail.split('id="tenant-release-stage-approval"', 1)[1].split(
        "{% elif tenant_release_step == 'finalize' %}", 1
    )[0]
    evidence = approval.split('{% set dry_run = row.release_native_handoff_dry_run %}', 1)[1].split(
        "{% elif row.release_handoff_preparation_state == 'pending'", 1
    )[0]
    Environment().parse(detail)

    # Historical preview remains a disclosure and never authorizes a Release.
    assert 'data-tenant-native-dry-run-evidence' in evidence
    assert 'group-open:rotate-180' in evidence
    assert "dry_run.plan_sha256 == handoff_plan.plan_sha256" in evidence
    assert 'not row.native_release_readiness.dry_run_passed' in evidence
    assert 'Historical / Not Current' in evidence
    assert 'Provider mutation: none. Release is still blocked.' in evidence
    assert 'dry_run.expected_component_count' in evidence
    assert 'dry_run.errors' in evidence
    assert 'role="status"' in evidence

    # Responsive exact-kind/name and full UID rows; clipboard is globally shared.
    assert 'sm:grid-cols-[minmax(0,16rem)_minmax(0,1fr)]' in evidence
    assert '{{ component.kind }}/{{ component.name }}' in evidence
    assert '{{ component.uid }}' in evidence
    assert evidence.count('data-kaori-copy-root') == 1
    assert evidence.count('data-kaori-copy-source') == 1
    assert evidence.count('data-kaori-copy-button') == 1
    assert 'data-kaori-copy-label' in evidence
    assert 'aria-live="polite"' in evidence
    assert "filename='js/clipboard.js'" in read('app/templates/layouts/app.html')

    # Labels are concise but preserve approval, ownership and freshness boundaries.
    assert 'Kubeconfig access verified; provider transfer remains separate.' in approval
    assert 'Inspect ownership only after external handoff. This action never transfers provider resources.' in approval
    assert 'Old evidence is invalid.' in approval
    assert 'SelfSubjectReview and SelfSubjectAccessReview. Provider transfer remains separate.' not in approval
    assert detail.count('<form method="post"') == 23
    assert detail.count('name="csrf_token"') == 23
    assert detail.count('hx-post=') == 23


def test_native_platform_admin_consent_is_violet_clear_and_only_authorizes_recorded_scope() -> None:
    detail = read(DETAIL)
    approval = detail.split('id="tenant-release-stage-approval"', 1)[1].split(
        "{% elif tenant_release_step == 'finalize' %}", 1
    )[0]
    form = next(
        form for form in re.findall(r'<form\b.*?</form>', approval, flags=re.DOTALL)
        if 'tenant.accept_native_successor_handoff_route' in form
    )
    Environment().parse(detail)

    # The confirmation is tinted, legible, responsive and explicitly not a successful transfer.
    assert 'data-tenant-platform-admin-consent' in form
    assert 'border-outline-subtle bg-kaori-soft/35' in form
    assert 'border-l-kaori-primary' not in form
    assert 'border-l-[3px]' not in form
    assert 'focus-within:ring-2 focus-within:ring-outline-focus' in form
    assert 'Platform Admin Consent' in form
    assert 'I authorize handoff for this plan SHA and exact scope; values stay unchanged.' in form
    assert 'mt-0.5 block text-xs leading-5 text-content-secondary' in form
    assert 'name="confirm_successor_acceptance"' in form
    assert re.search(r'name="confirm_successor_acceptance"\s+type="checkbox"\s+value="accept"\s+required', form)
    assert 'tenant.accept_native_successor_handoff_route' in form
    assert 'name="plan_sha256"' in form
    assert 'name="csrf_token"' in form
    assert 'hx-post=' in form

    # Separate provider verification, acceptance, and Release remain authoritative.
    assert 'recording Platform Admin consent' in form
    assert 'registered Kubernetes X.509 connection' in form
    assert 'No separate successor credentials are required.' in form
    assert 'Successor reference missing or expired.' in approval
    assert 'A reference does not prove successor acceptance.' in approval
    assert 'Approval expired. Original requester must restart with a new SHA' in approval
    assert 'Old evidence is invalid.' in approval
    assert 'readback_status.approval_expired' in approval
    assert 'readback_status.external_reference_current' in approval
    assert 'readback_status.external_readback_prerequisites_current' in approval
    assert detail.count('<form method="post"') == 23
    assert detail.count('name="csrf_token"') == 23
    assert detail.count('hx-post=') == 23



def test_accepted_native_handoff_uses_compact_nonmutating_workspace_rows() -> None:
    detail = read(DETAIL)
    approval = detail.split('id="tenant-release-stage-approval"', 1)[1].split(
        "{% elif tenant_release_step == 'finalize' %}", 1
    )[0]
    right = approval.split('data-release-accepted-handoff-evidence', 1)[1].split(
        '{% if tenant.provider_key == \'capsule\' %}', 1
    )[0]
    preview = approval.split('tenant.dry_run_native_release_handoff_route', 1)[1].split('</form>', 1)[0]
    Environment().parse(detail)

    # Right column has extra space for one-line desktop copy; mobile remains free to wrap.
    assert 'lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]' in approval
    assert 'Reference only; successor consent unverified and provider ownership unchanged.' in approval
    assert 'Kubeconfig access verified; provider transfer remains separate.' in approval
    assert 'Inspect external ownership; no transfer occurs here.' in right
    assert 'mt-3 w-full space-y-2 border-t border-outline-subtle pt-3' in right
    assert 'rounded-lg border border-outline-subtle bg-surface-elevated/35 p-3 sm:p-4' not in right
    assert 'After external transfer only; KAORI uses its governed Native Handoff executor.' in right
    assert 'External handoff complete; inspect markers only. No consent, writes or Release.' in right
    assert 'name="confirm_native_handoff_readback"' in right
    assert 'Inspect External Handoff' in right

    # The preview is a thin action strip, not an extra nested callout card.
    assert 'border-y border-outline-subtle py-3 sm:flex-row' in approval
    assert 'Server-side dry-run only; provider metadata, quotas and limits stay unchanged.' in approval
    assert 'name="confirm_native_handoff_dry_run"' in preview
    assert 'value="approved"' in preview
    assert 'required' in preview
    assert 'Preview Native Transfer' in preview
    assert 'rounded-xl border border-outline-subtle bg-surface-elevated/35 p-4 sm:p-5' not in preview

    # The change remains presentational; the same three provider pathways remain governed.
    assert 'tenant.inspect_native_external_handoff_route' in approval
    assert 'tenant.execute_native_release_handoff_route' in approval
    assert 'tenant.dry_run_native_release_handoff_route' in approval
    assert 'external_readback_prerequisites_current' in approval
    assert 'provider ownership unchanged.' in approval
    assert detail.count('<form method="post"') == 23
    assert detail.count('name="csrf_token"') == 23
    assert detail.count('hx-post=') == 23


def test_expired_native_restart_action_has_compact_readonly_evidence_and_required_consent() -> None:
    detail = read(DETAIL)
    step = detail.split('id="tenant-release-stage-finalize"', 1)[1]
    expired = step.split('{% elif native_cycle.approval_expired %}', 1)[1].split(
        '{% elif native_cycle.review_expired %}', 1
    )[0]
    form = expired.split('restart_expired_tenant_release_handoff_route', 1)[1].split(
        '</form>', 1
    )[0]
    Environment().parse(detail)

    assert 'data-release-restart-recheck-note' in form
    assert 'Read-back: 0 transferred.' in form
    assert 'UID/resourceVersion, ownership and dependencies; no automatic clearance.' in form
    assert 'native_cycle.restart_zero_transfer_recheck_required' in expired
    assert 'data-release-restart-confirmation' in form
    assert 'I verified provider ownership is unchanged before restarting.' in form
    assert re.search(r'name="confirm_handoff_restart"\s+value="restart"\s+required', form)
    assert 'name="plan_sha256"' in form
    assert 'name="csrf_token"' in form
    assert 'hx-post=' in form
    assert 'min-w-0 flex-col items-start gap-3' in form
    assert 'self-start rounded-lg border border-outline-default' in form
    assert 'native_cycle.restart_required' in expired
    assert 'row.release_handoff_plan.requested_by == current_user.id' in expired
    assert 'native_cycle.restart_blocked_by_readback' in expired
    assert detail.count('<form method="post"') == 23
    assert detail.count('name="csrf_token"') == 23
    assert detail.count('hx-post=') == 23
