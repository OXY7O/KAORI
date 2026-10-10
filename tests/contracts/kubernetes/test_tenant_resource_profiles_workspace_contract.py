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


def test_capacity_decisions_registry_is_compact_and_exposes_read_only_evidence() -> None:
    template = read('app/templates/kubernetes/tenant/partials/_capacity_decisions.html')
    model = read('app/models/tenant.py')
    registry = read('app/templates/components/table_registry.html')
    primitives = read('app/templates/components/table_primitives.html')

    # Preserve the approved canonical inventory, five-row HTMX, filter and
    # empty/loading contracts. Detail is bounded to visible paginated records.
    assert 'Capacity Decisions' in template
    assert 'registry_ui.filter_form(' in template
    assert 'registry_ui.clear_filters_link(' in template
    assert "registry_ui.footer('tenant.namespace_provisioning'" in template
    assert "table_ui.table_classes('min-w-[1060px] !table-fixed')" in template
    assert 'capacity_decision_pagination.per_page' in template
    assert "page_param='decision_page'" in template
    assert "per_page_param='decision_per_page'" in template
    assert 'decision_search' in template
    assert 'decision_result' in template
    for name, width in (
        ('Target', 24),
        ('Contract', 27),
        ('Admission', 22),
        ('Recorded', 17),
        ('Details', 10),
    ):
        assert f'w-[{width}%]">{name}</th>' in template
    assert 'colspan="5"' in template
    assert "components/states/_empty_state.html" in template
    assert 'macro footer(' in registry

    # Decision Allow/Block is a distinct authoritative fact from capacity
    # state, and full profile/namespace identities are available on demand.
    assert "decision.decision|title, decision_tone" in template
    assert "decision.capacity_state, state_tone" in template
    assert "decision_tone = 'normal' if decision.decision == 'allow' else 'critical'" in template
    assert 'title="{{ decision.namespace }}"' in template
    assert 'title="{{ profile_name }}"' in template
    assert "decision.resource_profile_version or row.profile.version" in template
    assert "decision.operation|replace('_', ' ')|title" in template

    # Reuse native KAORI dialogs with stable decision-ID identities and explicit
    # text-left reset from the shared Action cell's inherited text-right.
    assert "dialog_id = 'tenant-capacity-decision-' ~ decision.id" in template
    assert 'data-kaori-dialog-open' in template
    assert 'data-dialog-target="{{ dialog_id }}"' in template
    assert 'data-kaori-native-dialog' in template
    assert 'aria-labelledby="{{ dialog_id }}-title"' in template
    assert 'aria-describedby="{{ dialog_id }}-description"' in template
    assert 'data-kaori-dialog-close' in template
    assert 'p-0 text-left shadow-2xl' in template
    assert "{{ 'text-right' if action else 'text-left' }}" in primitives

    # Read-only committed reason/cutoff, capacity snapshot state and correlation
    # are not live provider diagnostics or newly computed capacity admission.
    for key in ("reason", "allocation_scope", "capacity_source", "snapshot_id", "snapshot_state"):
        assert key in template
    assert "decision.evidence_json or {}" in template
    assert "evidence.get('reason') or 'No committed explanation recorded.'" in template
    assert 'whitespace-pre-line break-words text-sm' in template
    assert 'row.created_at_label' in template
    assert 'row.data_cutoff_label' in template
    assert 'decision.correlation_id' in template
    assert "Blocked preflight does not authorize provider allocation mutation." in template
    assert '<details class="group border-t border-outline-subtle">' in template
    assert 'id="{{ dialog_id }}-admission-title"' in template
    assert 'id="{{ dialog_id }}-contract-title"' in template
    assert 'id="{{ dialog_id }}-record-title"' in template
    assert 'aria-labelledby="{{ dialog_id }}-admission-title"' in template
    assert "template"  # Existing committed read-only detail contract
    assert 'hx-post' not in template
    assert '<form method="post"' not in template
    assert 'class TenantCapacityDecision(db.Model)' in model
    assert "evidence_json: Mapped[dict]" in model


def test_capacity_decision_modal_uses_single_evidence_surface_and_quiet_traceability() -> None:
    template = read('app/templates/kubernetes/tenant/partials/_capacity_decisions.html')
    start = template.index('<dialog id="{{ dialog_id }}"')
    end = template.index('</dialog>', start)
    dialog = template[start:end]

    # Keep the native header clear of status/table-cell alignment inheritance.
    assert 'p-0 text-left shadow-2xl' in dialog
    assert 'bg-surface-card px-4 py-4 text-left sm:px-6' in dialog
    assert 'bg-surface-page p-4 text-left sm:p-5' in dialog
    assert 'Admission Evidence' in dialog
    assert 'id="{{ dialog_id }}-title"' in dialog
    assert 'id="{{ dialog_id }}-description"' in dialog
    assert 'data-kaori-dialog-close' in dialog

    # One bordered reading surface, rather than nested independent cards.
    assert dialog.count('overflow-hidden rounded-xl border border-outline-subtle bg-surface-card') == 1
    for heading in ('Admission', 'Target &amp; Contract', 'Committed Evidence'):
        assert heading in dialog
    assert dialog.index('id="{{ dialog_id }}-admission-title"') < dialog.index(
        'id="{{ dialog_id }}-contract-title"'
    ) < dialog.index('id="{{ dialog_id }}-record-title"') < dialog.index('>Traceability</span>')
    assert dialog.count('border-t border-outline-subtle px-4 py-4 sm:px-5') == 2

    # Keep the decision distinct from state, the full reason (no indentation),
    # the pinned contract, cutoff and correlation in source-owned evidence.
    assert 'decision.decision|title, decision_tone' in dialog
    assert 'decision.capacity_state, state_tone' in dialog
    assert 'evidence.get(\'reason\') or \'No committed explanation recorded.\'' in dialog
    assert 'whitespace-pre-line break-words text-sm' in dialog
    assert 'decision.resource_profile_version or row.profile.version' in dialog
    assert "evidence.get('allocation_scope')" in dialog
    assert 'row.created_at_label' in dialog
    assert 'row.data_cutoff_label' in dialog
    assert "capacity_source.get('snapshot_state')" in dialog
    assert 'decision.correlation_id' in dialog
    assert "capacity_source.get('snapshot_id')" in dialog

    # Traceability is a native, default-closed keyboard disclosure at the bottom,
    # not another large inner card, and no modal action mutates providers.
    assert '<details class="group border-t border-outline-subtle">' in dialog
    assert 'open>' not in dialog.split('<details class="group border-t border-outline-subtle">', 1)[1].split(
        '<summary', 1
    )[0]
    assert 'group-open:rotate-180' in dialog
    assert 'px-4 py-3 text-left focus-visible:' in dialog
    assert 'hx-post' not in dialog
    assert '<form' not in dialog


def test_namespace_registry_uses_compact_rows_and_committed_read_only_detail_dialog() -> None:
    template = read('app/templates/kubernetes/tenant/partials/_namespace_registry.html')
    model = read('app/models/tenant.py')
    primitives = read('app/templates/components/table_primitives.html')
    native = read('app/templates/components/status_detail_dialog.html')

    # The canonical registry contract (filters, default-five pagination, shared
    # table and empty/loading states) stays in charge of the list surface.
    assert 'Namespace Registry' in template
    assert "registry_ui.filter_form(" in template
    assert "registry_ui.clear_filters_link(" in template
    assert "registry_ui.footer('tenant.namespace_provisioning'" in template
    assert "table_ui.table_classes('min-w-[1080px] !table-fixed')" in template
    assert "namespace_pagination.per_page" in template
    for name in ("namespace_tenant_id", "namespace_environment", "namespace_status", "namespace_search"):
        assert name in template
    for title, width in (
        ("Namespace", 23),
        ("Tenant / Environment", 20),
        ("Allocation", 33),
        ("State", 14),
        ("Details", 10),
    ):
        assert f'w-[{width}%]">{title}</th>' in template
    assert 'colspan="5"' in template
    assert "components/states/_empty_state.html" in template

    # Full profile names and reconciliation messages belong in the modal,
    # not in a text-clipped status cell or a sixth authority column.
    assert 'profile_name|truncate(45, True' in template
    assert 'title="{{ profile_name }}"' in template
    assert 'item.provisioning_message or' in template
    assert "max-w-full truncate\" title=\"{{ item.provisioning_message" not in template
    assert "item.ownership_status" in template
    assert "item.resource_profile_version" in template
    assert "item.environment.tenant.provider_key" in template
    assert "item.environment.tenant.reconciliation_authority" in template
    assert "provider_mirrored_policy" in template
    assert "adopted_observed" in template
    assert "KAORI Managed" in template

    # Native-dialog identity is per committed Namespace ID; status detail is
    # informational only and cannot invoke a provider or a mutation endpoint.
    assert "dialog_id = 'tenant-namespace-evidence-' ~ item.id" in template
    assert 'data-kaori-dialog-open' in template
    assert 'data-dialog-target="{{ dialog_id }}"' in template
    assert 'aria-haspopup="dialog"' in template
    assert 'data-kaori-native-dialog' in template
    assert 'aria-labelledby="{{ dialog_id }}-title"' in template
    assert 'aria-describedby="{{ dialog_id }}-description"' in template
    assert 'data-kaori-dialog-close' in template
    assert 'kaori-native-dialog' in template
    assert "text-right' if action else 'text-left'" in primitives
    assert 'p-0 text-left shadow-2xl' in template
    assert 'bg-surface-page p-4 text-left sm:p-5' in template
    assert 'data-status-detail-dialog' in native
    assert 'hx-post' not in template
    assert '<form method="post"' not in template

    # The four request dimensions read frozen Namespace quota, never current
    # reusable profile values or raw provider JSON.
    for key in ("requests.cpu", "requests.memory", "pods", "requests.storage"):
        assert f"quota.get('{key}')" in template
    assert 'item.allocation_quota_json or {}' in template
    assert 'item.allocation_limit_defaults_json or {}' in template
    assert 'item.allocation_storage_policy_json or {}' in template
    assert "item.allocation_customized" in template
    assert "item.provisioning_message" in template
    assert "item.last_reconciled_at" in template
    assert 'Quota &amp; LimitRange Details' in template
    # Alignment and semantics: indentation in the Jinja source must not
    # appear as literal leading spaces in provider reconciliation messages.
    assert 'p-0 text-left shadow-2xl' in template
    assert 'bg-surface-page p-4 text-left sm:p-5' in template
    assert '<p class="whitespace-pre-line break-words text-sm leading-6 text-content-secondary">{{ item.provisioning_message or' in template
    assert 'whitespace-pre-wrap break-words text-sm leading-6 text-content-secondary' not in template
    assert 'aria-label="Namespace identity and authority"' in template
    assert 'Source Profile</p>' in template
    assert 'Effective Snapshot</p>' in template
    assert 'border-l-2 border-kaori-primary/30 pl-3 text-left' in template
    assert template.index('Committed Allocation</h3>') < template.index('Reconciliation</h3>') < template.index('Quota &amp; LimitRange Details')
    assert 'Not declared' in template
    assert 'Provider Mirrored' in template
    assert 'Control Unavailable' in template
    assert "allocation_quota_json: Mapped[dict | None]" in model
    assert "allocation_limit_defaults_json: Mapped[dict | None]" in model
    assert "allocation_storage_policy_json: Mapped[dict | None]" in model



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


def test_create_profile_resource_sections_are_collapsed_native_disclosures() -> None:
    form = read('app/templates/kubernetes/tenant/partials/_resource_profile_form.html')
    controls = read('app/templates/kubernetes/tenant/partials/_resource_profile_advanced_controls.html')
    script = read('app/static/js/tenant_resource_profile_presets.js')

    # The visible first-open experience is Identity & Lineage; all four core
    # resource groups begin closed, matching existing native Advanced Controls.
    assert 'Identity &amp; Lineage' in form
    assert form.index('resource-profile-identity-heading') < form.index('resource-profile-compute-heading')
    marker = '<details class="group overflow-hidden rounded-xl border border-outline-subtle bg-surface-card transition"'
    sections = form.split(marker)[1:]
    assert len(sections) == 4
    for section, title, heading in zip(
        sections,
        ('Basic Resources', 'Storage Guardrails', 'Object Limits', 'Container Defaults'),
        (
            'resource-profile-compute-heading',
            'resource-profile-storage-heading',
            'resource-profile-object-heading',
            'resource-profile-container-heading',
        ),
        strict=True,
    ):
        opening = section.split('>', 1)[0]
        assert ' open' not in opening
        assert 'data-tenant-resource-section' in opening
        assert f'aria-labelledby="{heading}"' in opening
        assert '<summary ' in section
        assert section.index('<summary ') < section.index('Section help')
        assert f'id="{heading}"' in section
        assert f'>{title}</h3>' in section
        assert 'group-open:rotate-180' in section
        assert 'border-t border-outline-subtle' in section
        assert '</details>' in section

    # Moving form controls into closed details must not alter submitted intent,
    # preset switching, or the canonical Managed / Unmanaged ownership mask.
    assert form.count('data-tenant-resource-field-wrap') == 5
    assert form.count('data-tenant-resource-field="{{ field }}"') == 5
    assert form.count('data-tenant-resource-control="{{ field }}"') == 5
    assert 'name="control_contract_present"' in form
    assert 'name="advanced_control_contract_present"' in form
    assert 'name="profile_class"' in form
    assert 'name="base_preset_class"' in form
    assert 'data-tenant-resource-profile-form' in form
    assert "scope.querySelectorAll('[data-tenant-resource-profile-form]').forEach(initProfileForm)" in script
    assert "form.querySelector('[data-tenant-profile-class]')" in script
    assert "collectFields(form, 'data-tenant-resource-field')" in script
    assert "collectFields(form, 'data-tenant-resource-control')" in script
    assert "syncManagedState()" in script
    assert 'data-tenant-advanced-controls' in controls
    assert '<details ' in controls



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


def test_resource_profile_registry_shows_compact_identity_and_full_detail_in_manage() -> None:
    registry = read('app/templates/kubernetes/tenant/partials/_resource_profile_registry.html')
    dialogs = read('app/templates/kubernetes/tenant/partials/_resource_profile_management_dialogs.html')
    table = read('app/templates/components/table.html')

    # Display-only abbreviations never modify persisted names or descriptions.
    assert "profile.name.startswith('Adopted ')" in registry
    assert "profile.name[8:] if adopted_baseline else profile.name" in registry
    assert "registry_name.rsplit(' · ', 1)" in registry
    assert "name_parts[1][:8]" in registry
    assert "registry_name|truncate(44, True, '…')" in registry
    assert "('Adopted baseline' if adopted_baseline else 'Profile') ~ ' · #' ~ profile.id" in registry
    assert "table_ui.title_cell(registry_name, registry_meta, 'layers-3')" in registry
    assert "table_ui.title_cell(profile.name, profile.description" not in registry
    assert "profile.description or 'Reusable allocation contract'" not in registry
    assert "aria-label=\"Manage Resource Profile {{ profile.name }}\"" in registry

    # Shared table geometry, HTMX, default pagination and actual Manage action stay intact.
    assert "title_cell(name, supporting_text='', icon='')" in table
    assert "table_ui.table_classes('min-w-[1150px] !table-fixed')" in registry
    assert "registry_ui.footer" in registry
    assert 'data-dialog-target="resource-profile-manage-{{ profile.id }}"' in registry

    # Modal is the full authority for both editable Custom and locked KAORI presets.
    assert 'id="resource-profile-manage-{{ profile.id }}-title"' in dialogs
    assert 'title="{{ profile.name }}">{{ profile.name }}</h3>' in dialogs
    assert 'aria-label="Resource Profile description"' in dialogs
    assert '<p class="whitespace-pre-wrap break-words text-sm leading-6 text-content-secondary">{{ profile.description }}</p>' in dialogs
    assert '<textarea name="profile_description"' in dialogs
    assert "{{ profile.description or '' }}</textarea>" in dialogs
    assert "value=\"{{ profile.description or '' }}\"" in dialogs
    assert "data-kaori-native-dialog" in dialogs


def test_resource_profile_workspace_redesign_preserves_governance_and_modal_workflow() -> None:
    registry = read('app/templates/kubernetes/tenant/partials/_resource_profile_registry.html')
    dialogs = read('app/templates/kubernetes/tenant/partials/_resource_profile_management_dialogs.html')

    # One coherent fixed-column contract; no truncated resource evidence.
    for label, width in [('Profile', 29), ('Contract', 21), ('Allocation', 26), ('Usage', 15), ('Action', 9)]:
        assert f'w-[{width}%]">{label}' in registry
    assert "table_ui.table_classes('min-w-[1150px] !table-fixed')" in registry
    assert 'grid grid-cols-2 gap-x-3 gap-y-2' in registry
    assert "('CPU', profile.quota_hard_json.get('requests.cpu') or 'Not Managed')" in registry
    assert "('Memory', profile.quota_hard_json.get('requests.memory') or 'Not Managed')" in registry
    assert "('Pods', profile.quota_hard_json.get('pods') or 'Not Managed')" in registry
    assert "('Storage', profile.quota_hard_json.get('requests.storage') or 'Not Managed')" in registry
    assert "registry_ui.footer" in registry
    assert "data-kaori-dialog-open" in registry

    # Actual full identity is a managed detail surface, not a repeated header wall.
    assert "Manage Resource Profile' if editable else 'Resource Profile Details" in dialogs
    assert "aria-label=\"Resource Profile identity\"" in dialogs
    assert "title=\"{{ profile.name }}\">{{ profile.name }}</h3>" in dialogs
    assert "<textarea name=\"profile_description\"" in dialogs
    assert "sm:col-span-2" in dialogs
    assert "Profile Configuration" in dialogs
    assert "Namespace References" in dialogs
    assert "Capacity Decisions" in dialogs

    # Native progressive disclosures and original form contracts apply to both
    # editable Custom profiles and fixed built-in presets.
    assert dialogs.count("Namespace quotas and PVC limits") == 2
    assert dialogs.count("Services, ConfigMaps and Secrets") == 2
    assert dialogs.count("LimitRange request and limit defaults") == 2
    assert dialogs.count('<details class="group overflow-hidden rounded-xl') == 6
    assert dialogs.count('id="resource-profile-update-form-{{ profile.id }}"') == 2
    assert dialogs.count('advanced_profile_controls.render(') == 2
    assert "name=\"control_contract_present\"" in dialogs
    assert "name=\"advanced_control_contract_present\"" in dialogs

    # Rollout remains an explicit, Tenant-scoped POST with separate eligibility.
    assert 'aria-labelledby="resource-profile-rollout-{{ profile.id }}-heading"' in dialogs
    assert 'name="tenant_id" required' in dialogs
    assert "target.provider_key != 'native_kubernetes'" in dialogs
    assert 'How rollout is applied' in dialogs
    assert 'One Tenant at a time' in dialogs
    assert "form=\"resource-profile-update-form-{{ profile.id }}\"" in dialogs
    assert "url_for('tenant.rollout_resource_profile_route', profile_id=profile.id)" in dialogs


def test_profile_manage_modal_copy_and_grouped_summary_remain_bounded() -> None:
    dialogs = read('app/templates/kubernetes/tenant/partials/_resource_profile_management_dialogs.html')

    # Status and lineage are rendered through canonical labels, not standalone prose.
    assert "table_label.status_label('Editable' if editable else 'Versioned Controls'" in dialogs
    assert "table_label.metadata_label('Independent Custom · Operator-managed values', 'layers-3', wrap=true)" in dialogs
    assert "table_label.metadata_label('Canonical KAORI preset · Fixed values', 'lock-keyhole', wrap=true)" in dialogs

    # Two intentional groups replace unstructured, widely separated figures.
    summary = dialogs
    assert 'aria-label="Profile contract and usage summary"' in summary
    assert 'sm:grid-cols-2 sm:divide-x sm:divide-y-0' in summary
    assert '<h3 class="text-xs font-semibold text-content-secondary">Contract</h3>' in summary
    assert '<h3 class="text-xs font-semibold text-content-secondary">Usage</h3>' in summary
    for metric in ("Class", "Version", "Namespace References", "Capacity Decisions"):
        assert f">{metric}</dt>" in summary

    # Legacy descriptions are presentation-shortened, never overwritten in forms.
    assert "profile.description.startswith('Explicit governance-cutover profile materialized" in dialogs
    assert "Adopted baseline profile; no provider value changes requested." in dialogs
    assert '<textarea name="profile_description"' in dialogs
    assert "{{ profile.description or '' }}</textarea>" in dialogs
    assert 'value="{{ profile.description or \'\' }}"' in dialogs

    # Governance boundary still explicitly covers committed version, admission and read-back.
    assert "Existing Namespace allocations stay unchanged; edits affect future allocations until explicitly applied." in dialogs
    assert "Each Namespace is admitted, applied, and verified separately." in dialogs
    assert "Blocked Namespaces retain their prior committed version." in dialogs
    assert "url_for('tenant.rollout_resource_profile_route', profile_id=profile.id)" in dialogs


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
    assert 'aria-label="Resource allocation comparison"' in capacity
    assert "capacity_budget_bars.get(item.cluster.id|string, [])" in capacity
    assert 'sm:grid-cols-[minmax(11rem,1.4fr)_repeat(3,minmax(0,1fr))]' in capacity
    assert 'col-span-3 min-w-0 sm:col-span-1' in capacity
    assert 'lg:grid-cols-3' not in capacity
    assert "bar.budget" in capacity
    assert "bar.committed" in capacity
    assert "bar.headroom" in capacity
    assert "{{ bar.percent }}% used" in capacity
    assert "{{ bar.free_percent }}% left" in capacity
    assert 'style="width: {{ bar.percent }}%"' in capacity
    assert 'style="width: {{ bar.free_percent }}%"' in capacity
    assert "Percentage unavailable · {{ bar.state }}" in capacity
    assert "Over budget by {{ bar.shortfall }}" in capacity
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
    assert 'Logical storage governed' in capacity
    assert "bar.key == 'storage_bytes'" in capacity
    assert 'Storage is logical admission capacity.' in capacity
    assert 'Governed request budgets and remaining headroom.' in capacity
    assert capacity.count('Logical budget only.') == 1
    assert 'Physical and usable capacity remain separate Storage Analytics evidence.' in capacity
    assert 'min-h-10 w-full items-center' in capacity
    assert 'mt-2 grid items-start gap-3 lg:grid-cols-[minmax(14rem,22rem)_minmax(0,1fr)]' in capacity
    assert 'class="{{ form_field.input_classes() }} !mt-0 pr-14"' in capacity
    assert 'class="flex min-h-10 w-full items-center gap-2' in capacity
    assert 'name="tenant_storage_budget_gib"' in capacity
    assert "form_field.help('Enter GiB" not in capacity
    assert 'capacity_budget_bars.get(item.cluster.id|string, [])' in capacity
    assert 'bar.percent' in capacity
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
    assert "context['capacity_budget_bars'] = {" in routes
    assert "str(item['cluster'].id): build_tenant_allocation_bars(item)" in routes


def test_allocation_budget_registry_separates_snapshot_freshness_and_compute_budget() -> None:
    capacity = read('app/templates/kubernetes/tenant/partials/_capacity_governance.html')
    docs = read('docs/architecture/kubernetes-tenant-capacity-governance.md')
    table = read('app/templates/components/table.html')

    # Separate snapshot state from committed computed budget availability.
    assert "item.snapshot_state in ['current', 'fresh']" in capacity
    assert "'Compute budget available' if item.budget else ('Capacity policy required' if not item.policy else 'Compute evidence required')" in capacity
    assert 'Capacity policy required' in capacity
    assert "item.snapshot_state == 'current' else 'Compute evidence required'" not in capacity
    assert "'Compute budget available' if item.snapshot_state" not in capacity
    assert "Logical storage governed" in capacity
    for column, percent in [('Cluster', 28), ('Evidence', 39), ('State', 17), ('Details', 16)]:
        assert f'w-[{percent}%]">{column}</th>' in capacity
    assert "table_ui.table_classes('min-w-[980px] !table-fixed')" in capacity
    assert "table_ui.action_classes()" in capacity
    assert "data-kaori-native-dialog" in capacity
    assert "data-kaori-dialog-open" in capacity
    # Action cells are deliberately text-right for the registry button, but the
    # nested native dialog must explicitly break text-align inheritance.
    primitives = read('app/templates/components/table_primitives.html')
    assert "{{ 'text-right' if action else 'text-left' }}" in primitives
    modal = capacity.split('<dialog id="{{ dialog_id }}"', 1)[1].split('</dialog>', 1)[0]
    assert 'p-0 text-left shadow-2xl' in modal
    assert 'bg-surface-card px-4 py-4 text-left sm:gap-4' in modal
    assert 'bg-surface-page p-4 text-left sm:p-5' in modal
    assert "registry_ui.footer" in capacity
    assert 'macro cluster_identity(' in table  # Reuse the existing identity primitive.

    # Canonical committed budget percentages are supplied by existing presentation bars,
    # never recomputed or inferred from formatted display strings in the template.
    dialog = capacity.split('aria-label="Resource allocation comparison"', 1)[1].split('</section>', 1)[0]
    assert "capacity_budget_bars.get(item.cluster.id|string, [])" in dialog
    assert 'grid grid-cols-3 gap-x-4 gap-y-3' in dialog
    assert 'col-span-3 min-w-0 sm:col-span-1' in dialog
    assert 'sm:sr-only' in dialog
    assert "bar.label" in dialog
    assert "bar.budget" in dialog
    assert "bar.committed" in dialog
    assert "bar.headroom" in dialog
    assert "{{ bar.percent }}% used" in dialog
    assert "{{ bar.free_percent }}% left" in dialog
    assert 'role="img"' in dialog
    assert "Percentage unavailable · {{ bar.state }}" in dialog
    assert "Over budget by {{ bar.shortfall }}" in dialog
    assert 'overflow-x-auto' not in dialog
    assert "data-kaori-dialog-close" in capacity
    assert "Storage is logical admission capacity." in capacity
    assert "Allocation Budget registry and detail visual hierarchy" in docs


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


def test_capacity_governance_exposes_read_only_tenant_allocation_overview() -> None:
    page = read('app/templates/kubernetes/tenant/resource_profiles.html')
    parent = read('app/templates/kubernetes/tenant/partials/_capacity_governance.html')
    overview = read('app/templates/kubernetes/tenant/partials/_tenant_allocation_overview.html')
    routes = read('app/kubernetes/tenant/routes.py')
    projection = read('app/kubernetes/tenant/allocation_overview.py')
    capacity = read('app/kubernetes/tenant/capacity_governance.py')

    assert 'kubernetes/tenant/partials/_tenant_allocation_overview.html' in parent
    assert parent.index('kubernetes/tenant/partials/_tenant_allocation_overview.html') < parent.index(
        '<section id="{{ capacity_registry_id }}"'
    )
    assert 'Tenant Allocation Overview' in overview
    assert 'allocation_cluster_id' in overview
    assert 'hx-target="#{{ overview_id }}"' in overview
    assert 'hx-select="#{{ overview_id }}"' in overview
    assert 'registry_ui.footer' in overview
    assert 'allocation_tenant_pagination.allowed_per_page' in overview
    assert 'row.namespaces' in overview
    assert 'selected.snapshot_state' in overview
    assert 'selected.state' in overview
    assert 'bar.shortfall' in overview
    assert "bar.known" in overview
    assert "url_for('analytics.capacity')" in overview
    assert "current_user.has_permission('analytics.view')" in overview
    assert 'not actual workload utilization or physical reservations' in overview
    assert 'Storage is an explicitly governed logical ceiling' in overview

    assert 'build_tenant_allocation_bars(selected)' in routes
    assert 'build_tenant_contribution_rows(str(selected[\'cluster\'].id))' in routes
    assert "'allocation_page'" in routes
    assert "'allocation_per_page'" in routes
    assert "per_page=request.args.get('allocation_per_page', 5" in routes
    assert "if active_view == 'capacity' and selected is not None:" in routes
    assert "get_resource_profile_workspace_context()" in routes
    assert "build_capacity_governance_summaries" in capacity

    # Reuse #654's exact shared-quota selection, committed aggregation, and
    # committed-state read path. Do not introduce provider calls on navigation.
    assert '_canonical_shared_allocation_quota(cluster_id)' in projection
    assert '_aggregate_committed_allocation(' in projection
    assert 'TenantNamespaceProvisioningStatus.DEPROVISIONED.value' in projection
    assert 'allocation_quota_json' not in overview
    assert 'build_client(' not in projection
    assert 'read_namespace(' not in projection
    assert 'requests.get(' not in projection
    assert "('capacity', 'Capacity Governance', 'gauge'" in page
