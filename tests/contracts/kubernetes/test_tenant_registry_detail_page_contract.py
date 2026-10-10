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
    assert 'Identity, allocation scope and historical governance evidence' in detail
    assert 'Tenant Name' in detail
    assert 'Quick Links' in detail
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


def test_page_shows_all_governed_sections_in_authoritative_order():
    detail = read(DETAIL)
    labels = (
        'id="tenant-detail-snapshot"',
        'id="tenant-release-governance"',
        'id="tenant-native-handback"',
        'id="tenant-namespace-attachment"',
        'id="tenant-provider-authority"',
        'id="tenant-lifecycle-actions"',
    )
    assert all(label in detail for label in labels)
    assert [detail.index(label) for label in labels] == sorted(
        detail.index(label) for label in labels
    )
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
        '01 · Preflight and blockers',
        '02 · Provider handoff scope',
        '03 · Independent approval and handoff',
        '04 · Verify and finalize',
        'aria-label="Release blockers"',
        'aria-label="Provider handoff inventory"',
        'aria-label="Release governance workflow"',
    ):
        assert label in release
    assert 'divide-y divide-outline-subtle' in release
    assert 'max-h-72' not in release
    assert 'overflow-y-auto' not in release
    assert 'text-sm leading-6' in release
    assert release.count('<form ') == 11


def test_exact_governance_forms_return_to_same_page_and_global_toast():
    detail = read(DETAIL)
    common = read('app/kubernetes/tenant/route_common.py')
    toast = read('app/templates/components/operational_toast.html')
    assert detail.count('<form ') == 14
    assert detail.count('name="csrf_token"') == 14
    assert detail.count('name="tenant_detail_id"') == 14
    assert detail.count('registry_state.items()') == 14
    assert detail.count('hx-target="#tenant-management-detail"') == 14
    assert detail.count('hx-select="#tenant-management-detail"') == 14
    assert detail.count('hx-post=') == 14
    assert 'name="tenant_detail_view"' not in detail
    assert detail.count('name="tenant_detail_section"') == 14
    assert "context['tenant_detail_open_section'] = active_section" in common
    assert "detail_id = str(request.form.get('tenant_detail_id')" in common
    assert "'kubernetes/tenant/partials/_tenant_management_detail.html'" in common
    assert "'tenant.tenant_detail', tenant_id=detail_id" in common
    assert 'toast_oob=True' in common
    assert 'beforeend:#operational-toast-stack' in toast
    assert 'data-kaori-native-dialog' not in detail


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
        'attach_existing_capsule_namespace_route',
        'decommission_tenant_route',
    ):
        assert name in detail
    assert 'Acknowledge as Independent Reviewer' in detail
    assert 'handoff_plan.requested_by != current_user.id' in detail
    assert 'row.release_preflight.blockers' in detail
    assert 'data-capsule-namespace-attach' in detail
    assert 'name="namespace_uid"' in detail
    assert 'name="namespace_resource_version"' in detail
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


def test_overview_matches_two_column_identity_and_quick_links():
    detail = read(DETAIL)
    assert 'sm:grid-cols-2 xl:grid-cols-4' in detail
    assert "('Active Namespaces', " not in detail  # actual summary includes icon
    assert "'Active Namespaces', row.namespace_count" in detail
    assert 'row.environments|length' in detail
    assert 'tenant.reconciliation_authority' in detail
    assert 'tenant.lifecycle_status' in detail
    assert 'lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]' in detail
    assert "'Tenant Name', tenant.name" in detail
    assert "'Cluster', row.cluster.name" in detail
    assert "'Provider', tenant.provider_key" in detail
    assert 'tenant.description or' in detail
    assert "url_for('tenant.resource_profiles')" in detail
    assert "url_for('tenant.operations')" in detail
    assert 'tenant.created_at.strftime(' in detail
    assert 'tenant.updated_at.strftime(' in detail


def test_governance_sections_use_native_accessible_expandables_and_existing_controls():
    detail = read(DETAIL)
    names = (
        'tenant-release-governance', 'tenant-native-handback',
        'tenant-namespace-attachment', 'tenant-provider-authority',
        'tenant-lifecycle-actions',
    )
    assert detail.count('name="tenant-governance"') == len(names)
    assert detail.count('tenant_detail_open_section ==') == len(names)
    assert detail.count('group-open:rotate-180') == len(names)
    for id_ in names:
        assert f'<details id="{id_}" name="tenant-governance"' in detail
    assert '<summary class="flex min-h-20 cursor-pointer' in detail
    for name in ('Release Governance', 'Platform Admin Handback',
                 'Namespace Attachment', 'Provider Authority', 'Lifecycle Actions'):
        assert name in detail
    assert 'tenant-release-stage-readiness' in detail
    assert 'tenant-release-stage-inventory' in detail
    assert 'tenant-release-stage-approval' in detail
    assert 'tenant-release-stage-finalize' in detail
    assert 'aria-label="Governed Release sequence"' in detail
    assert 'id="tenant-release-workflow-details"' in detail
    assert '{% if tenant_detail_release_expanded %}open{% endif %}' in detail
    assert 'View full Release workflow and evidence' in detail
    assert "tenant_detail_section" in detail
    assert 'max-h-72' not in detail
    assert "destructive_modal.render('tenant-decommission-modal'" in detail
