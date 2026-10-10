from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def tenant_service_source() -> str:
    return '\n'.join(
        read(path)
        for path in (
            'app/kubernetes/tenant/service.py',
            'app/kubernetes/tenant/service_contracts.py',
            'app/kubernetes/tenant/registry_context.py',
            'app/kubernetes/tenant/resource_profile_controls.py',
        )
    )


def capacity_governance_source() -> str:
    return (
        read('app/kubernetes/tenant/capacity_governance.py')
        + '\n'
        + read('app/kubernetes/tenant/capacity_governance_support.py')
    )


def tenant_discovery_source() -> str:
    return (
        read('app/kubernetes/tenant/discovery_service.py') + '\n' + read('app/kubernetes/tenant/discovery_adoption.py')
    )


def test_resource_profiles_use_server_owned_kaori_content_tabs_and_snapshot_stats() -> None:
    page = read('app/templates/kubernetes/tenant/resource_profiles.html')
    routes = read('app/kubernetes/tenant/routes.py')
    service = tenant_service_source()

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
    management = read('app/templates/kubernetes/tenant/partials/_resource_profile_management_dialogs.html')
    advanced = read('app/templates/kubernetes/tenant/partials/_resource_profile_advanced_controls.html')
    script = read('app/static/js/tenant_resource_profile_presets.js')
    service = tenant_service_source()
    form_field = read('app/templates/components/form_field.html')

    assert 'Create Resource Profile' in form
    assert 'Identity &amp; Lineage' in form
    assert 'Basic Resources' in form
    assert 'Storage Guardrails' in form
    assert 'Object Limits' in form
    assert 'Container Defaults' in form
    assert '[grid-template-columns:repeat(auto-fit,minmax(14rem,1fr))]' in form
    assert 'resource-profile-identity-tip' in form
    assert 'resource-profile-contract-tip' not in form
    assert 'resource-profile-class-tip' not in form
    assert 'resource-profile-base-tip' not in form
    assert 'KAORI Preset · Fixed' in form
    assert 'data-mode="fixed"' in form
    assert 'border border-kaori-primary/20 bg-kaori-soft px-4 py-3 transition-colors' in form
    assert 'data-[mode=fixed]:bg-kaori-soft' not in form
    assert 'data-[mode=fixed]:bg-kaori-primary/15' not in form
    assert "table_label.special_label('Fixed · Read Only', 'maintenance', 'lock-keyhole')" in form
    assert "table_label.special_label('Custom · Editable', 'maintenance', 'pencil')" in form
    assert "modeBanner.dataset.mode = readonly ? 'fixed' : 'custom'" in script
    assert 'data-[locked=true]:border-dashed' in form
    assert 'data-[locked=true]:cursor-not-allowed' in form

    assert 'Namespace Quota' in form
    assert 'Per-PVC Policy' in form
    assert 'PVCs' in form
    assert 'Total Storage' in form
    assert 'pvc_min_storage' in form
    assert 'pvc_max_storage' in form
    assert 'pvc_default_request_storage' not in form
    assert 'pvc_default_storage' not in form
    assert 'PVC Default Request' not in management
    assert 'PVC Default Limit' not in management
    assert "pvc_min_storage: ['storage_policy', 'min']" in script
    assert "pvc_max_storage: ['storage_policy', 'max']" in script
    assert 'pvc_default_request_storage:' not in script
    assert 'pvc_default_storage:' not in script
    assert "wrapper?.dataset.controlRequiresValue === 'true'" in script

    for key in ("'small': {", "'standard': {", "'large': {", "'extra_large': {"):
        assert key in service
    assert service.count("'storage_policy': {'min': '1Gi', 'max': '10Gi'}") == 4
    assert service.count("'version': 2") >= 4

    assert 'control_contract_present' in form
    assert '>Medium</option>' in form
    assert '>Extra Large</option>' in form
    assert '_resource_profile_advanced_controls.html' in form
    assert 'advanced_profile_controls.render' in form
    assert 'advanced_control_contract_present' in form
    assert 'Advanced Controls' in advanced
    assert "'Scope: ' ~ scope" in advanced
    assert "'Effect when enabled: ' ~ effect" in advanced
    assert 'Provider behavior: placement capability is checked at attachment and again before mutation.' in advanced
    assert 'show_tips=true' in advanced
    assert 'data-tenant-advanced-controls-view' in advanced
    assert 'Exposure &amp; Access' in advanced
    assert 'Capsule Namespace Governance' in advanced
    assert 'Capsule Platform Extensions' in advanced
    assert 'data-tenant-advanced-controls' in advanced
    assert 'data-tenant-advanced-control-group="ingress"' in advanced
    assert 'components/info_tip.html' in advanced
    assert "id_prefix ~ '-overview-tip'" in advanced
    assert (
        'Scope: optional governance beyond basic allocation, storage, object limits, and container defaults.'
        in advanced
    )
    assert (
        'Provider behavior: the selected Native or Capsule placement is evaluated at attachment and again before mutation'
        in advanced
    )
    assert "'ingress'" in advanced
    assert 'Ingress exposure governance for namespaces using this profile.' in advanced
    assert "'service-exposure'" in advanced
    assert (
        'ClusterIP, Ingress, NodePort, LoadBalancer, and ExternalName exposure decisions for attached namespaces.'
        in advanced
    )
    assert "'hostname-reservation'" in advanced
    assert 'Exact, wildcard, or regex hostname ownership and collision protection for Tenant exposure.' in advanced
    assert "'managed-tls'" in advanced
    assert 'TLS delivery for attached workloads using platform TLS or namespace compatibility mode.' in advanced
    assert "'managed-registry'" in advanced
    assert 'Private image-registry credential delivery for namespaces attached to this profile.' in advanced
    assert "'capsule-namespace-controls'" in advanced
    assert 'Capsule Tenant namespace naming and namespaceOptions policy.' in advanced
    assert "'capsule-resource-rules'" in advanced
    assert (
        'Capsule Tenant policy for container registries, PriorityClasses, StorageClasses, and admitted rule payloads.'
        in advanced
    )
    assert "'capsule-resource-pools'" in advanced
    assert 'Capsule ResourcePool or ResourcePoolClaim association and desired spec.' in advanced
    assert "'capsule-replication'" in advanced
    assert 'Capsule TenantResource or GlobalTenantResource replication intent.' in advanced
    assert "'capsule-tenant-cordon'" in advanced
    assert 'Capsule Tenant spec cordoned and preventDeletion state.' in advanced
    assert 'setReadonly(form, fields, true)' in script
    assert "wrapper.dataset.locked = readonly ? 'true' : 'false'" in script
    assert "classSelect?.value === 'custom'" in script
    assert 'syncManagedState' in script
    assert "wrapper.dataset.controlled = managed ? 'true' : 'false'" in script
    assert "document.addEventListener('htmx:afterSwap'" in script
    assert 'read-only:bg-surface-disabled' in form_field
    assert 'read-only:text-content-muted' in form_field
    assert 'read-only:shadow-none' in form_field


def test_resource_profile_registry_uses_canonical_htmx_filters_and_pagination() -> None:
    registry = read('app/templates/kubernetes/tenant/partials/_resource_profile_registry.html')
    service = tenant_service_source()

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
    assert "table_ui.table_classes('min-w-[1150px] !table-fixed')" in registry
    assert 'resource-profile-manage-' in registry
    assert 'data-dialog-target="resource-profile-manage-{{ profile.id }}"' in registry
    assert 'Versioned Controls' in registry
    assert 'pending rollout' in registry
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
    service = tenant_service_source()

    assert 'components/table_registry.html' in capacity
    assert 'registry_ui.filter_form' in capacity
    assert 'registry_ui.footer' in capacity
    assert 'capacity_search' in capacity
    assert 'capacity_page' in capacity
    assert 'capacity_per_page' in capacity
    assert 'Budget</th>' not in capacity
    assert 'Committed</th>' not in capacity
    assert 'Headroom</th>' not in capacity
    assert 'State</th>' in capacity
    assert 'Details</th>' in capacity
    assert 'components/status_detail_dialog.html' not in capacity
    assert 'data-kaori-dialog-open' in capacity
    assert 'data-kaori-native-dialog' in capacity
    assert 'class="{{ table_ui.action_classes() }}"' in capacity
    assert 'View More' in capacity
    assert 'lg:grid-cols-3' in capacity
    assert "('Budget', 'gauge', item.display.budget" in capacity
    assert "('Committed', 'layers-3', item.display.committed" in capacity
    assert "('Headroom', 'chart-no-axes-combined', item.display.headroom" in capacity
    assert 'No governed namespaces' in capacity
    assert "dialog_id = 'capacity-budget-details-'" in capacity
    assert 'space-y-3 p-4' not in capacity
    assert 'section class="space-y-5"' in capacity
    assert 'xl:grid-cols-12' not in capacity
    assert 'Recalculates governed CPU, memory, Pod, and storage headroom before save.' in capacity
    assert (
        'Quota enforces limits; admission governs CPU, memory, Pods, and logical storage commitment without claiming physical reservation.'
        not in capacity
    )
    assert 'Compute &amp; Pod Budget' in capacity
    assert 'platform_reserve_pods' in capacity
    assert 'unmanaged_commitment_pods' in capacity
    assert 'Tenant Storage Budget (GiB)' in capacity
    assert 'name="tenant_storage_budget_gib"' in capacity
    assert 'type="number"' in capacity
    assert 'min="0.01"' in capacity
    assert 'step="0.01"' in capacity
    assert 'placeholder="2048"' in capacity
    assert '2048 GiB = 2 TiB' in capacity
    assert 'Compute evidence required' in capacity
    assert 'Logical storage policy remains active' in capacity
    assert "('Storage', values.storage)" in capacity
    assert 'Storage is logical admission capacity.' in capacity
    assert 'Budget, committed allocation, and remaining headroom.' in capacity
    assert capacity.count('Logical budget only.') == 1
    assert 'Physical and usable capacity remain separate Storage Analytics evidence.' in capacity
    assert 'min-h-10 w-full items-center' in capacity
    assert 'mt-2 grid gap-3 lg:grid-cols-[minmax(14rem,22rem)_minmax(0,1fr)] lg:items-center' in capacity
    assert "form_field.help('Enter GiB" not in capacity
    assert 'values.pods' in capacity
    assert 'values.storage' in capacity
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

    governance = capacity_governance_source()
    assert "'tenant_storage_budget_gib': _quantity_gib_text(policy.tenant_storage_budget)" in governance
    assert 'logical_budget = _logical_storage_budget_vector(policy)' in governance
    assert 'logical_headroom = _headroom(logical_budget, committed)' in governance

    assert 'tenant-capacity-policy-state' in page
    assert "'capacity_policy_state':" in service
    assert "const policies = readJson('tenant-capacity-policy-state')" in script
    assert 'paginate_sequence' in routes
    assert "context['capacity_pagination']" in routes
    assert "context['capacity_filters']" in routes


def test_capacity_commitment_excludes_deprovisioned_history_and_preserves_unknowns() -> None:
    governance = capacity_governance_source()

    assert 'TenantNamespace.provisioning_status != TenantNamespaceProvisioningStatus.DEPROVISIONED.value' in governance
    assert 'def _committed_evidence_reason(' in governance
    assert 'unbounded_namespaces: list[str] | None = None' in governance
    assert 'Unbounded or missing governed' in governance
    assert "('Pods', governed.pods, committed.pods)" in governance
    assert "('storage', governed.storage_bytes, committed.storage_bytes)" in governance
    assert 'Apply a bounded Resource Profile allocation before positive changes.' in governance
    assert "state = 'Unknown' if commitment_reason" in governance
    assert 'commitment_reason or _state_reason(state)' in governance


def test_resource_profile_revision_preserves_fixed_preset_values_and_dependency_authority() -> None:
    service = tenant_service_source()
    routes = read('app/kubernetes/tenant/routes.py')
    model = read('app/models/tenant.py')
    docs = read('docs/architecture/kubernetes-tenant-resource-profiles.md')

    assert 'def update_resource_profile(profile_id: int' in service
    assert 'is_builtin = profile.profile_class in RESOURCE_PROFILE_PRESETS' in service
    assert '_preset_controlled_values(RESOURCE_PROFILE_PRESETS[profile.profile_class], source)' in service
    assert '_preset_storage_policy_values(RESOURCE_PROFILE_PRESETS[profile.profile_class], source)' in service
    assert 'Built-in Resource Profiles are locked.' not in service
    assert 'profile.version = int(profile.version or 1) + 1' in service
    assert 'profile_version = int(profile.version or 1)' in service

    assert 'def rollout_resource_profile_to_tenant_committed(' in service
    assert 'def _resource_profile_rollout_targets(' in service
    assert 'change_native_namespace_allocation_committed(' in service
    assert "'profile_rollout_targets': profile_rollout_targets" in service
    assert 'A blocked Namespace stays on its previous committed version.' not in service

    assert "@tenant_bp.post('/resource-profiles/<int:profile_id>/edit')" in routes
    assert "@tenant_bp.post('/resource-profiles/<int:profile_id>/rollout')" in routes
    assert 'rollout_resource_profile_to_tenant_committed' in routes

    assert 'def delete_resource_profile(profile_id: int)' in service
    assert 'Built-in Resource Profiles are KAORI-owned and cannot be deleted.' in service
    assert "ForeignKey('tenant_resource_profiles.id', ondelete='RESTRICT')" in model

    assert '### Profile revision and rollout' in docs
    assert 'same profile identity' in docs
    assert 'Small-2' in docs


def test_resource_profile_registry_context_exposes_dependency_counts_for_actions() -> None:
    service = tenant_service_source()

    assert "'profile_dependencies': profile_dependencies" in service
    assert "'profile_rollout_targets': profile_rollout_targets" in service
    assert 'namespace_counts.get(profile.id, 0)' in service
    assert 'capacity_decision_counts.get(profile.id, 0)' in service


def test_resource_profile_management_dialogs_support_versioned_builtin_governance_and_rollout() -> None:
    dialogs = read('app/templates/kubernetes/tenant/partials/_resource_profile_management_dialogs.html')
    advanced = read('app/templates/kubernetes/tenant/partials/_resource_profile_advanced_controls.html')

    assert 'data-kaori-native-dialog' in dialogs
    assert 'resource-profile-manage-{{ profile.id }}' in dialogs
    assert 'max-w-7xl' in dialogs
    assert 'max-w-6xl' not in dialogs
    assert 'KAORI Built-in Preset' in dialogs
    assert 'Fixed values · Versioned controls' in dialogs
    assert 'Why this preset is locked' not in dialogs
    assert 'border border-kaori-primary/20 bg-kaori-soft px-4 py-3' in dialogs
    assert 'Save New Version' in dialogs
    assert 'Attached Namespace Rollout' in dialogs
    assert "url_for('tenant.rollout_resource_profile_route', profile_id=profile.id)" in dialogs
    assert 'Each Namespace runs its own capacity admission, provider mutation, and read-back.' in dialogs
    assert 'Capsule workflow' in dialogs

    assert (
        "advanced_profile_controls.render(profile.advanced_controls_json or {}, true, 'resource-profile-edit-' ~ profile.id, false)"
        in dialogs
    )
    assert 'show_tips' in advanced
    assert 'Read-only governance intent grouped by operational scope.' in advanced

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
    service = tenant_service_source()
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
    assert 'block sm:col-span-2' in advanced
    assert 'Required fails closed when admission enforcement is unavailable.' not in advanced
    assert 'Reference only. Secret/private-key material is never stored in the profile.' not in advanced
    assert 'Reference only. Registry credentials are not stored in Resource Profile JSON.' not in advanced
    assert 'advanced_control_capsule_namespace_controls_namespace_options_json' in advanced
    assert 'name="advanced_control_capsule_resource_rules_{{ field }}"' in advanced
    assert "('storage_classes', 'Storage Classes')" in advanced
    assert 'advanced_control_capsule_resource_pools_spec_json' in advanced
    assert 'advanced_control_capsule_replication_spec_json' in advanced
    assert 'advanced_control_capsule_tenant_cordon_prevent_deletion' in advanced
    assert 'Secret or private-key material is never stored in the Resource Profile.' in advanced
    assert 'Credential values are never stored in profile JSON.' in advanced
    assert 'const initAdvancedControls = (container) =>' in script
    assert "scope.querySelectorAll('[data-tenant-advanced-controls]').forEach(initAdvancedControls)" in script
    assert 'const advancedControlSummary = (key, value) =>' in script
    assert 'configuration = advancedControlSummary(key, rawRequest)' in script

    assert 'profile.advanced_controls_json = _advanced_profile_controls(source)' in service
    assert 'def evaluate_resource_profile_advanced_controls(' in service
    assert 'def resource_profile_attachment_controls(' in service
    assert 'def _validate_resource_profile_attachment_controls(' in service
    assert 'attachment_controls = _validate_resource_profile_attachment_controls(profile, tenant)' in service
    assert "'advanced_profile_controls'" in service
    assert 'advanced_controls_json: Mapped[dict]' in model
    assert "'advanced_controls_json'" in migration

    assert 'advanced_control_contract_present' in dialogs
    assert (
        dialogs.count(
            "advanced_profile_controls.render(profile.advanced_controls_json or {}, true, 'resource-profile-edit-' ~ profile.id, false)"
        )
        >= 2
    )
    assert (
        "advanced_profile_controls.render_view(profile.advanced_controls_json or {}, 'resource-profile-view-' ~ profile.id)"
        not in dialogs
    )
    assert 'data-tenant-namespace-environment' in namespace_form
    assert 'Effective Allocation Preview' in namespace_form
    assert 'data-tenant-value-display' in namespace_form
    assert 'Quota &amp; Default Details' in namespace_form
    assert 'data-tenant-allocation-details' in namespace_form
    assert 'Advanced Controls Preview' in namespace_form
    assert 'data-tenant-namespace-advanced-preview' in namespace_form
    assert '<details' in namespace_form
    assert 'data-tenant-namespace-advanced-control' in namespace_form
    assert 'cursor-not-allowed border-dashed' not in namespace_form
    assert 'Provisioning commits intent and evidence; Sync remains observation-only.' in namespace_form
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


def test_resource_profile_storage_policy_is_persisted_and_bidirectional() -> None:
    model = read('app/models/tenant.py')
    migration = read('migrations/versions/20261001_profile_storage_policy.py')
    service = tenant_service_source()
    provisioning = read('app/kubernetes/tenant/provisioning.py')
    observation = read('app/kubernetes/tenant/allocation_observation.py')
    cutover = read('app/kubernetes/tenant/allocation_cutover.py')
    drift = read('app/kubernetes/tenant/allocation_drift.py')
    adoption = tenant_discovery_source()
    form = read('app/templates/kubernetes/tenant/partials/_resource_profile_form.html')
    dialogs = read('app/templates/kubernetes/tenant/partials/_resource_profile_management_dialogs.html')

    assert 'storage_policy_json: Mapped[dict]' in model
    assert 'allocation_storage_policy_json: Mapped[dict | None]' in model
    assert "'storage_policy_json'" in migration
    assert "'allocation_storage_policy_json'" in migration

    assert 'def _storage_policy_values(' in service
    assert 'profile.storage_policy_json = storage_policy' in service
    assert 'storage_policy=storage_policy' in service
    assert "'storage_policy': getattr(profile, 'storage_policy_json', {}) or {}" in service

    assert "type='PersistentVolumeClaim'" in provisioning
    assert "'storage_policy': normalized_storage" in provisioning
    assert 'record.allocation_storage_policy_json = normalized_storage' in provisioning

    assert "'storage_policy': storage_policy" in observation
    assert "f'pvc.{field}.storage is defined by multiple LimitRange sources" in observation
    assert "payload = {'quota': quota, 'limits': limits, 'storage_policy': storage_policy}" in observation

    assert 'def _storage_policy_equal(' in cutover
    assert 'not _storage_policy_equal' in cutover
    assert 'record.allocation_storage_policy_json = prepared.storage' in cutover

    assert 'dict(record.allocation_storage_policy_json or {})' in drift
    assert 'storage_policy=dict(record.allocation_storage_policy_json or {})' in drift
    assert 'record.allocation_storage_policy_json = storage_policy' in drift

    assert 'def _create_adopted_baseline_profile(' not in adoption
    assert 'record.allocation_storage_policy_json' in adoption
    assert 'def _materialize_adopted_baseline_profile(' in service
    assert "profile_selector == 'adopted_baseline'" in service
    assert 'profile.storage_policy_json = dict(record.allocation_storage_policy_json or {})' in service

    for label in ('Basic Resources', 'Storage Guardrails', 'Object Limits', 'Container Defaults'):
        assert label in form
        assert label in dialogs


def test_resource_profile_copy_is_compact_and_version_intent_remains_clear() -> None:
    dialogs = read('app/templates/kubernetes/tenant/partials/_resource_profile_management_dialogs.html')
    adoption = read('app/templates/kubernetes/tenant/partials/_tenant_adoption_preflight.html')

    assert (
        'Preset sizing stays fixed. Control changes create a new version; Namespace snapshots stay pinned until rollout.'
        in dialogs
    )
    assert 'sizing stays canonical.' in dialogs
    assert (
        'Control changes create v{{ (profile.version or 1) + 1 }}; Namespace snapshots stay pinned until rollout.'
        in dialogs
    )
    assert 'Managed takeover where authority exists; provider-owned constraints stay mirrored.' not in adoption
    assert 'Adopt managed authority; keep provider constraints mirrored.' in adoption
    assert 'Result: Adopted / Observed.' in adoption


def test_namespace_allocation_preview_is_snapshot_not_fake_form() -> None:
    namespace_form = read('app/templates/kubernetes/tenant/partials/_namespace_form.html')
    script = read('app/static/js/tenant_resource_profile_presets.js')

    assert 'Effective Allocation Preview' in namespace_form
    assert 'Effective allocation summary' in namespace_form
    assert 'Quota &amp; Default Details' in namespace_form
    assert 'data-tenant-value-display' in namespace_form
    assert 'data-tenant-namespace-advanced-preview' in namespace_form
    assert "if ('value' in target)" in script
    assert "target.textContent = value || '—'" in script
