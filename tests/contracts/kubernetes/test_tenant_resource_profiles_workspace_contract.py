from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_resource_profiles_use_server_owned_kaori_content_tabs_and_snapshot_stats() -> None:
    page = read('app/templates/kubernetes/tenant/resource_profiles.html')
    routes = read('app/kubernetes/tenant/routes.py')
    service = read('app/kubernetes/tenant/service.py')

    assert 'components/section_intro.html' in page
    assert 'components/resource_posture_grid.html' in page
    assert 'Resource Profile Snapshot' in page
    assert 'Profile Estate' in page
    assert 'Resource Profile Workspace' in page
    assert 'Profile Administration' in page
    assert 'Total Profiles' in page
    assert 'Enabled' in page
    assert 'Custom' in page
    assert 'Active Allocations' in page
    assert 'resource_profile_stats.total' in page
    assert "'resource_profile_stats':" in service

    assert 'components/content_tabs.html' in page
    assert 'content_tabs.render_links' in page
    assert 'id="resource-profile-workspace"' in page
    assert "('profiles', 'Profile Library', 'layers-3', url_for('tenant.resource_profiles', view='profiles'))" in page
    assert "('capacity', 'Capacity Governance', 'gauge', url_for('tenant.resource_profiles', view='capacity'))" in page
    assert "('workflow', 'Workflow Guide'" in page
    assert 'profile_count),' not in page
    assert 'ready_clusters|length),' not in page
    assert "hx_target='#resource-profile-workspace'" in page
    assert 'active_resource_profile_view' in page
    assert "active_view not in {'profiles', 'capacity', 'workflow'}" in routes
    assert 'destructive_confirmation_modal.js' in page


def test_resource_profile_form_uses_full_width_dense_contract_sections() -> None:
    form = read('app/templates/kubernetes/tenant/partials/_resource_profile_form.html')
    advanced = read('app/templates/kubernetes/tenant/partials/_resource_profile_advanced_controls.html')
    script = read('app/static/js/tenant_resource_profile_presets.js')
    form_field = read('app/templates/components/form_field.html')

    assert 'Create Resource Profile' in form
    assert 'Identity &amp; Lineage' in form
    assert 'Quota Guardrails' in form
    assert 'Container Defaults' in form
    assert 'lg:grid-cols-4' in form
    assert 'lg:grid-cols-5' in form
    assert 'xl:grid-cols-12' not in form
    assert 'KAORI Preset · Fixed' in form
    assert 'components/table_label.html' in form
    assert "table_label.special_label('Fixed · Read Only', 'unknown', 'lock-keyhole')" in form
    assert "table_label.special_label('Custom · Editable', 'maintenance', 'pencil')" in form
    assert 'data-tenant-profile-mode-fixed-label' in form
    assert 'data-tenant-profile-mode-custom-label hidden' in form
    assert 'data-[locked=true]:border-dashed' in form
    assert 'bg-surface-card transition' in form
    assert 'data-[locked=true]:cursor-not-allowed' in form
    assert 'resource-profile-contract-tip' in form
    assert 'resource-profile-quota-tip' in form
    assert 'resource-profile-limitrange-tip' in form
    assert "placement='right'" in form
    assert 'inline-flex min-h-6 items-center gap-1.5' in form
    assert 'resource-profile-class-tip' in form
    assert 'resource-profile-base-tip' in form
    assert 'data-tenant-profile-class' in form
    assert 'data-tenant-base-preset-wrapper hidden' in form
    assert 'data-tenant-base-preset' in form
    assert 'data-tenant-resource-field="{{ field }}"' in form
    assert 'data-tenant-resource-control="{{ field }}"' in form
    assert 'control_contract_present' in form
    assert '>Medium</option>' in form
    assert '>Extra Large</option>' in form
    assert '_resource_profile_advanced_controls.html' in form
    assert 'advanced_profile_controls.render' in form
    assert 'advanced_control_contract_present' in form
    assert 'Advanced Controls' in advanced
    assert 'data-tenant-advanced-controls' in advanced
    assert 'data-tenant-advanced-control-group="ingress"' in advanced
    assert 'setReadonly(form, fields, true)' in script
    assert "wrapper.dataset.locked = readonly ? 'true' : 'false'" in script
    assert "fixedLabel.hidden = !readonly" in script
    assert "customLabel.hidden = readonly" in script
    assert "classSelect?.value === 'custom'" in script
    assert 'syncManagedState' in script
    assert "wrapper.dataset.controlled = managed ? 'true' : 'false'" in script
    assert "document.addEventListener('htmx:afterSwap'" in script
    assert 'read-only:bg-surface-disabled' in form_field
    assert 'read-only:text-content-muted' in form_field
    assert 'read-only:shadow-none' in form_field


def test_resource_profile_registry_uses_canonical_htmx_filters_and_pagination() -> None:
    registry = read('app/templates/kubernetes/tenant/partials/_resource_profile_registry.html')
    service = read('app/kubernetes/tenant/service.py')

    assert 'components/table_registry.html' in registry
    assert 'registry_ui.filter_form' in registry
    assert 'registry_ui.clear_filters_link' in registry
    assert 'registry_ui.footer' in registry
    assert 'profile_search' in registry
    assert 'profile_class' in registry
    assert 'profile_state' in registry
    assert '>Apply<' not in registry
    assert '_pagination_footer.html' not in registry
    assert 'Resource Profile Registry' in registry
    assert 'Allocation' in registry
    assert 'Usage' in registry
    assert '>Action</th>' in registry
    assert "table_ui.table_classes('min-w-[900px]')" in registry
    assert 'resource-profile-manage-' in registry
    assert "{{ 'Manage' if profile.profile_class == 'custom' else 'View' }}" in registry
    assert "{{ table_label.status_label('Editable' if profile.profile_class == 'custom' else 'Locked'" in registry
    assert '_resource_profile_management_dialogs.html' in registry
    assert 'Requests</th>' not in registry
    assert 'Namespace Quota</th>' not in registry
    assert 'Container Defaults</th>' not in registry
    assert 'Lineage</th>' not in registry
    assert "special_label('Locked'" not in registry

    assert 'def get_resource_profile_registry_context(' in service
    assert 'paginate_query(' in service
    assert "'profile_registry_filters':" in service


def test_resource_profile_workflow_uses_numbered_contract_stages_without_arrow_flow() -> None:
    workflow = read('app/templates/kubernetes/tenant/partials/_resource_profile_workflow.html')
    page = read('app/templates/kubernetes/tenant/resource_profiles.html')

    assert 'Governed Allocation Lifecycle' in workflow
    assert 'Define Contract' in workflow
    assert 'Admit Capacity' in workflow
    assert 'Provision Namespace' in workflow
    assert 'Verify Provider' in workflow
    assert 'Contract Boundaries' in workflow
    assert 'Admission Boundaries' in workflow
    assert 'Open Namespace Provisioning' in workflow
    assert 'operational_flow_steps' not in page


def test_capacity_governance_uses_canonical_cluster_budget_table() -> None:
    capacity = read('app/templates/kubernetes/tenant/partials/_capacity_governance.html')
    page = read('app/templates/kubernetes/tenant/resource_profiles.html')
    script = read('app/static/js/tenant_resource_profile_presets.js')
    routes = read('app/kubernetes/tenant/routes.py')
    service = read('app/kubernetes/tenant/service.py')

    assert 'components/table_registry.html' in capacity
    assert 'registry_ui.filter_form' in capacity
    assert 'registry_ui.footer' in capacity
    assert 'capacity_search' in capacity
    assert 'capacity_page' in capacity
    assert 'capacity_per_page' in capacity
    assert 'Budget</th>' in capacity
    assert 'Committed</th>' in capacity
    assert 'Headroom</th>' in capacity
    assert 'State</th>' in capacity
    assert 'space-y-3 p-4' not in capacity
    assert 'section class="space-y-5"' in capacity
    assert 'xl:grid-cols-12' not in capacity
    assert 'Uses fresh committed capacity evidence.' in capacity
    assert 'Quota enforces limits; admission uses committed requests, not physical reservation.' in capacity
    assert "action_button.classes('primary')" in capacity
    assert "action_button.classes('primary', full=true)" not in capacity
    assert 'components/info_tip.html' in capacity
    assert 'tenant-capacity-policy-tip' in capacity
    assert 'allocation-budget-status-tip' in capacity
    assert 'title_extra=title_info' in capacity
    assert 'table_ui.block_classes(allow_overflow=true)' in capacity
    assert "button_text='Status Guide'" not in capacity
    assert 'button_classes=table_ui.action_classes()' not in capacity
    assert 'status_detail_dialog' not in capacity

    assert 'tenant-capacity-policy-state' in page
    assert "'capacity_policy_state':" in service
    assert "const policies = readJson('tenant-capacity-policy-state')" in script
    assert 'paginate_sequence' in routes
    assert "context['capacity_pagination']" in routes
    assert "context['capacity_filters']" in routes


def test_capacity_commitment_excludes_deprovisioned_history_and_preserves_unknowns() -> None:
    governance = read('app/kubernetes/tenant/capacity_governance.py')

    assert 'TenantNamespace.provisioning_status != TenantNamespaceProvisioningStatus.DEPROVISIONED.value' in governance
    assert 'def _committed_evidence_reason(' in governance
    assert 'unbounded_namespaces: list[str] | None = None' in governance
    assert 'Unbounded or missing CPU/memory request commitment on active Namespace(s):' in governance
    assert 'Apply a bounded Resource Profile allocation before positive changes.' in governance
    assert "state = 'Unknown' if commitment_reason" in governance
    assert 'commitment_reason or _state_reason(state)' in governance


def test_custom_resource_profile_crud_preserves_preset_and_dependency_authority() -> None:
    service = read('app/kubernetes/tenant/service.py')
    routes = read('app/kubernetes/tenant/routes.py')
    model = read('app/models/tenant.py')
    readme = read('app/kubernetes/tenant/README.md')

    assert 'def update_resource_profile(profile_id: int' in service
    assert 'profile.profile_class != TenantResourceProfileClass.CUSTOM.value' in service
    assert 'Built-in Resource Profiles are locked.' in service
    assert "enabled_value not in {'enabled', 'disabled'}" in service
    assert 'contract_changed = quota !=' in service
    assert 'profile.version = int(profile.version or 1) + 1' in service

    assert 'def delete_resource_profile(profile_id: int)' in service
    assert 'def _resource_profile_dependency_counts(profile_id: int)' in service
    assert 'TenantNamespace.query.filter_by(resource_profile_id=profile_id).count()' in service
    assert 'TenantCapacityDecision.query.filter_by(resource_profile_id=profile_id).count()' in service
    assert "if dependencies['total']:" in service
    assert 'release all Resource Profile dependencies first' in service

    assert "@tenant_bp.post('/resource-profiles/<int:profile_id>/edit')" in routes
    assert "@tenant_bp.post('/resource-profiles/<int:profile_id>/delete')" in routes
    assert 'update_resource_profile_committed' in routes
    assert 'delete_resource_profile_committed' in routes

    assert "ForeignKey('tenant_resource_profiles.id', ondelete='RESTRICT')" in model
    assert 'Hard Delete' in readme
    assert 'zero Namespace references and zero Capacity Decision references' in readme


def test_resource_profile_registry_context_exposes_dependency_counts_for_actions() -> None:
    service = read('app/kubernetes/tenant/service.py')

    assert "'profile_dependencies': profile_dependencies" in service
    assert 'namespace_counts.get(profile.id, 0)' in service
    assert 'capacity_decision_counts.get(profile.id, 0)' in service


def test_resource_profile_management_dialogs_explain_preset_lock_and_govern_custom_lifecycle() -> None:
    dialogs = read('app/templates/kubernetes/tenant/partials/_resource_profile_management_dialogs.html')

    assert 'data-kaori-native-dialog' in dialogs
    assert 'resource-profile-manage-{{ profile.id }}' in dialogs
    assert 'KAORI Built-in Preset' in dialogs
    assert 'Why this preset is locked' in dialogs
    assert 'same preset identity mean different resources over time' in dialogs
    assert 'Create a Custom profile from this preset' in dialogs
    assert "url_for('tenant.update_resource_profile_route'" in dialogs
    assert 'resource-profile-update-form-{{ profile.id }}' in dialogs
    assert 'profile_enabled' in dialogs
    assert 'Existing Namespace allocations keep their committed source version' in dialogs
    assert 'resource-profile-delete-modal' in dialogs
    assert 'zero Namespace and zero Capacity Decision references remain' in dialogs
    assert 'KAORI does not detach historical evidence automatically.' in dialogs

def test_resource_profile_advanced_controls_are_real_profile_intent_and_placement_gated() -> None:
    form = read('app/templates/kubernetes/tenant/partials/_resource_profile_form.html')
    advanced = read('app/templates/kubernetes/tenant/partials/_resource_profile_advanced_controls.html')
    dialogs = read('app/templates/kubernetes/tenant/partials/_resource_profile_management_dialogs.html')
    namespace_form = read('app/templates/kubernetes/tenant/partials/_namespace_form.html')
    namespace_page = read('app/templates/kubernetes/tenant/namespace_provisioning.html')
    script = read('app/static/js/tenant_resource_profile_presets.js')
    service = read('app/kubernetes/tenant/service.py')
    model = read('app/models/tenant.py')
    migration = read('migrations/versions/20261001_profile_adv_controls.py')
    docs = read('docs/architecture/kubernetes-tenant-resource-profiles.md')

    assert 'data-tenant-placement-control-matrix' not in form
    assert 'Placement-Gated Controls' not in form
    assert '_resource_profile_advanced_controls.html' in form
    assert 'advanced_profile_controls.render' in form
    assert 'advanced_control_contract_present' in form
    assert 'data-tenant-advanced-controls' in advanced
    assert 'Advanced Controls' in advanced
    assert '<details' in advanced
    assert '#118' not in advanced
    assert '#119' not in advanced
    assert '#121' not in advanced
    assert '#124' not in advanced

    for key in (
        'ingress',
        'service_exposure',
        'hostname_reservation',
        'managed_tls',
        'managed_registry',
        'capsule_namespace_controls',
        'capsule_resource_rules',
        'capsule_resource_pools',
        'capsule_replication',
        'capsule_tenant_cordon',
    ):
        assert key in advanced
        assert key in service

    assert 'advanced_control_service_exposure_profile_key' in advanced
    assert 'advanced_control_hostname_reservation_hostname_pattern' in advanced
    assert 'advanced_control_managed_tls_mode' in advanced
    assert 'advanced_control_managed_registry_source_reference' in advanced
    assert 'advanced_control_capsule_namespace_controls_namespace_options_json' in advanced
    assert 'advanced_control_capsule_resource_rules_storage_classes' in advanced
    assert 'advanced_control_capsule_resource_pools_spec_json' in advanced
    assert 'advanced_control_capsule_replication_spec_json' in advanced
    assert 'advanced_control_capsule_tenant_cordon_prevent_deletion' in advanced
    assert 'Secret/private-key material is never stored in the profile.' in advanced
    assert 'Registry credentials are not stored in Resource Profile JSON.' in advanced
    assert 'const initAdvancedControls = (container) =>' in script
    assert "scope.querySelectorAll('[data-tenant-advanced-controls]').forEach(initAdvancedControls)" in script

    assert 'profile.advanced_controls_json = _advanced_profile_controls(source)' in service
    assert 'def evaluate_resource_profile_advanced_controls(' in service
    assert 'def resource_profile_attachment_controls(' in service
    assert 'def _validate_resource_profile_attachment_controls(' in service
    assert 'attachment_controls = _validate_resource_profile_attachment_controls(profile, tenant)' in service
    assert "'advanced_profile_controls'" in service
    assert 'advanced_controls_json: Mapped[dict]' in model
    assert "'advanced_controls_json'" in migration

    assert 'advanced_control_contract_present' in dialogs
    assert 'advanced_profile_controls.render(profile.advanced_controls_json or {}, true' in dialogs
    assert 'advanced_profile_controls.render(profile.advanced_controls_json or {}, false' in dialogs
    assert 'data-tenant-namespace-environment' in namespace_form
    assert 'Advanced Controls Preview' in namespace_form
    assert 'data-tenant-namespace-advanced-control' in namespace_form
    assert 'tenant-environment-advanced-control-state' in namespace_page
    assert "const environments = readJson('tenant-environment-advanced-control-state')" in script
    assert "stateLabel.textContent = 'Unavailable'" in script
    assert "stateLabel.textContent = 'Enabled'" in script

    assert '## Advanced profile controls' in docs
    assert 'operator-editable reusable contract, not a status/TODO matrix' in docs
    assert 'requested but unavailable advanced control blocks the provider mutation' in docs
    assert 'never substitutes Native behavior for Capsule-only controls' in docs


def test_tenant_provider_unavailable_copy_is_compact_and_uses_standard_hero_action() -> None:
    tenants = read('app/templates/kubernetes/tenant/tenants.html')
    base = read('app/templates/kubernetes/tenant/base.html')
    live = read('app/kubernetes/tenant/live_connection.py')
    blocked = read('app/templates/components/cluster/_hero_blocked_context.html')
    hero = read('app/templates/components/page_hero.html')

    assert 'Active principals' in tenants
    assert 'Active user, group, and machine principals' not in tenants
    assert 'Kubernetes unreachable. Mutations blocked.' in live
    assert 'Kubernetes unreachable. KAORI remains readable; provider mutations are blocked.' not in live
    assert 'KAORI state stays available. Provider mutations wait for a Ready, reachable integration.' not in base
    assert 'Review Cluster Integrations' in base
    assert 'Open Cluster Integrations' in base
    assert 'cluster_blocked_action_href' in base
    assert 'blocked_action_label' in blocked
    assert 'action_label=None' in hero
    assert 'context_single_action_classes()' in hero
