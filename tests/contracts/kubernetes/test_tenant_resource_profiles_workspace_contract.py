import re
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
    assert 'components/states/_empty_state.html' in template
    assert 'macro footer(' in registry

    # Decision Allow/Block is a distinct authoritative fact from capacity
    # state, and full profile/namespace identities are available on demand.
    assert 'decision.decision|title, decision_tone' in template
    assert 'decision.capacity_state, state_tone' in template
    assert "decision_tone = 'normal' if decision.decision == 'allow' else 'critical'" in template
    assert 'title="{{ decision.namespace }}"' in template
    assert 'title="{{ profile_name }}"' in template
    assert 'decision.resource_profile_version or row.profile.version' in template
    assert "decision.operation|replace('_', ' ') |title" in template

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
    for key in ('reason', 'allocation_scope', 'capacity_source', 'snapshot_id', 'snapshot_state'):
        assert key in template
    assert 'decision.evidence_json or {}' in template
    assert 'evidence.get("reason") or \'No committed explanation recorded.\'' in template
    assert 'whitespace-pre-line break-words text-sm' in template
    assert 'row.created_at_label' in template
    assert 'row.data_cutoff_label' in template
    assert 'decision.correlation_id' in template
    assert 'Blocked preflight does not authorize provider allocation mutation.' in template
    assert '<details class="group border-t border-outline-subtle">' in template
    assert 'id="{{ dialog_id }}-admission-title"' in template
    assert 'id="{{ dialog_id }}-contract-title"' in template
    assert 'id="{{ dialog_id }}-record-title"' in template
    assert 'aria-labelledby="{{ dialog_id }}-admission-title"' in template
    assert '{{ target_display }}' in template
    assert '{{ profile_display }}' in template
    assert 'hx-post' not in template
    assert '<form method="post"' not in template
    assert 'class TenantCapacityDecision(db.Model)' in model
    assert 'evidence_json: Mapped[dict]' in model


def test_capacity_decision_compact_names_preserve_canonical_identity_and_distinctions() -> None:
    from jinja2 import Environment

    source = read('app/templates/kubernetes/tenant/partials/_capacity_decisions.html')
    # Exercise the exact display-only Jinja transformations, not a duplicate
    # Python abbreviation algorithm that could drift from the rendered table.
    start = source.index("{% set target_parts = decision.namespace.split(':') %}")
    end = source.index("{% set dialog_id = 'tenant-capacity-decision-' ~ decision.id %}", start)
    view = Environment(autoescape=True).from_string(source[start:end] + '{{ target_display }}||{{ profile_display }}')

    def names(target: str, profile: str) -> tuple[str, str]:
        rendered = view.render(decision={'namespace': target}, profile_name=profile)
        first, second = rendered.split('||')
        return first.strip(), second.strip()

    assert names('gajah', 'Platform Medium') == ('gajah', 'Platform Medium')
    assert names('tenant-uat-demo', 'Adopted tenant-uat-demo Baseline · 4') == (
        'tenant-uat-demo',
        'tenant-uat-demo Baseline 4',
    )
    assert names('tenant-uat-demo', 'Adopted tenant-uat-demo Baseline · 3') == (
        'tenant-uat-demo',
        'tenant-uat-demo Baseline 3',
    )
    assert names(
        '@tenant:kaori-demo:resource-quotas',
        'Adopted kaori-demo Allocation · e36817ba-f3d5-433b-a26e-e8106bf28abb',
    ) == ('kaori-demo · Resource Quotas', 'kaori-demo Allocation · e36817ba')
    assert names('@tenant:kaori-demo:other', 'Platform Small')[0] == '@tenant:kaori-demo:other'
    long_label, long_profile = names('x' * 80, 'Unrecognized contract ' + 'y' * 80)
    assert len(long_label) <= 34
    assert len(long_profile) <= 36

    # Full canonical values remain available without any new provider lookup.
    assert 'title="{{ decision.namespace }}"' in source
    assert 'title="{{ profile_name }}"' in source
    assert '{{ decision.namespace }}</h2>' in source
    assert re.search(r'{{\s*profile_name\s*}}\s*</dd>', source)
    assert 'decision.resource_profile_version or row.profile.version' in source
    assert 'data-kaori-native-dialog' in source
    assert "registry_ui.footer('tenant.namespace_provisioning'" in source


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
    assert (
        dialog.index('id="{{ dialog_id }}-admission-title"')
        < dialog.index('id="{{ dialog_id }}-contract-title"')
        < dialog.index('id="{{ dialog_id }}-record-title"')
        < dialog.index('>Traceability</span>')
    )
    assert dialog.count('border-t border-outline-subtle px-4 py-4 sm:px-5') == 2

    # Keep the decision distinct from state, the full reason (no indentation),
    # the pinned contract, cutoff and correlation in source-owned evidence.
    assert 'decision.decision|title, decision_tone' in dialog
    assert 'decision.capacity_state, state_tone' in dialog
    assert 'evidence.get("reason") or \'No committed explanation recorded.\'' in dialog
    assert 'whitespace-pre-line break-words text-sm' in dialog
    assert 'decision.resource_profile_version or row.profile.version' in dialog
    assert 'evidence.get("allocation_scope")' in dialog
    # Full-width canonical Resource Profile is the first row; Operation and
    # Allocation Scope share the following row, never compressing its width.
    contract = dialog.split('id="{{ dialog_id }}-contract-title"', 1)[1].split('id="{{ dialog_id }}-record-title"', 1)[
        0
    ]
    assert 'dl class="mt-3 grid grid-cols-2 gap-x-4 gap-y-3"' in contract
    assert '<div class="col-span-2 min-w-0">' in contract
    assert 'sm:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)]' not in contract
    assert contract.index('Resource Profile</dt>') < contract.index('Operation</dt>')
    assert contract.index('Resource Profile</dt>') < contract.index('Allocation Scope</dt>')
    # Keep the full-width, wrapped profile binding without depending on
    # djLint's placement of the variable on the next source line.
    assert re.search(
        r'<dd\s+class="mt-1 break-words text-sm font-semibold leading-5 text-content-primary">\s*'
        r'\{\{\s*profile_name\s*\}\}\s*</dd>',
        contract,
    )
    assert 'row.created_at_label' in dialog
    assert 'row.data_cutoff_label' in dialog
    assert 'capacity_source.get("snapshot_state")' in dialog
    assert 'decision.correlation_id' in dialog
    assert "capacity_source.get('snapshot_id')" in dialog

    # Traceability is a native, default-closed keyboard disclosure at the bottom,
    # not another large inner card, and no modal action mutates providers.
    assert '<details class="group border-t border-outline-subtle">' in dialog
    assert (
        'open>'
        not in dialog.split('<details class="group border-t border-outline-subtle">', 1)[1].split('<summary', 1)[0]
    )
    assert 'group-open:rotate-180' in dialog
    assert 'px-4 py-3 text-left focus-visible:' in dialog

    # The fixed footer follows the scrollable evidence body and reuses the
    # native dialog Close action, independent of committed Allow/Block state.
    assert 'min-h-0 flex-1 overflow-y-auto bg-surface-page' in dialog
    assert 'aria-label="Admission Evidence dialog actions"' in dialog
    assert dialog.index('</header>') < dialog.index('min-h-0 flex-1 overflow-y-auto') < dialog.index('<footer')
    footer = dialog.split('<footer', 1)[1].split('</footer>', 1)[0]
    assert 'border-t border-outline-subtle bg-surface-card' in footer
    assert 'justify-end' in footer
    assert 'data-kaori-dialog-close' in footer
    assert 'type="button"' in footer
    assert 'class="{{ table_ui.action_classes() }}"' in footer
    assert re.search(r'>\s*Close\s*</button>', footer)
    assert dialog.count('data-kaori-dialog-close') == 2
    assert 'hx-post' not in dialog
    assert '<form' not in dialog


def test_namespace_registry_uses_compact_rows_and_committed_read_only_detail_dialog() -> None:
    template = read('app/templates/kubernetes/tenant/partials/_namespace_registry.html')
    model = read('app/models/tenant.py')
    primitives = read('app/templates/components/table_primitives.html')
    native = read('app/templates/components/status_detail_dialog.html')

    # The canonical registry contract (filters, default-five pagination, shared
    # table and empty/loading states) stays in charge of the list surface.
    assert 'Namespace Provisioning Registry' in template
    assert 'registry_ui.filter_form(' in template
    assert 'registry_ui.clear_filters_link(' in template
    assert "registry_ui.footer('tenant.namespace_provisioning'" in template
    assert "table_ui.table_classes('min-w-[1080px] !table-fixed')" in template
    assert 'namespace_pagination.per_page' in template
    for name in ('namespace_tenant_id', 'namespace_environment', 'namespace_status', 'namespace_search'):
        assert name in template
    for title, width in (
        ('Namespace', 25),
        ('Tenant / Environment', 18),
        ('Allocation', 32),
        ('State', 15),
        ('Details', 10),
    ):
        assert f'w-[{width}%]">{title}</th>' in template
    assert 'colspan="5"' in template
    assert 'components/states/_empty_state.html' in template

    # Full profile names and reconciliation messages belong in the modal,
    # not in a text-clipped status cell or a sixth authority column.
    assert 'profile_display|truncate(42, True' in template
    assert 'title="{{ profile_name }}"' in template
    assert '{{ profile_display }}</p>' in template
    assert 'Control: {{ control_label }}' in template
    assert 'title="Control: {{ control_label }}"' in template
    assert (
        "table_label.status_label(item.ownership_status|replace('_', ' ') |title, 'normal' if item.ownership_status == 'managed' else 'info')"
        in template
    )
    assert 'Gen {{ item.generation }}' in template
    assert (
        "'Snapshot v' ~ item.resource_profile_version if item.resource_profile_version else 'No pinned snapshot'"
        in template
    )
    assert 'No pinned snapshot' in template
    assert 'item.provisioning_message or' in template
    assert 'max-w-full truncate" title="{{ item.provisioning_message' not in template
    assert 'item.ownership_status' in template
    assert 'item.resource_profile_version' in template
    assert 'item.environment.tenant.provider_key' in template
    assert 'item.environment.tenant.reconciliation_authority' in template
    assert 'provider_mirrored_policy' in template
    assert 'adopted_observed' in template
    assert 'KAORI Managed' in template

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

    # All six primary ResourceQuota dimensions use committed Namespace
    # snapshot values, not mutable profiles or Container LimitRange defaults.
    for label, key in (
        ('CPU Requests', 'requests.cpu'),
        ('CPU Limits', 'limits.cpu'),
        ('Memory Requests', 'requests.memory'),
        ('Memory Limits', 'limits.memory'),
        ('Pod Slots', 'pods'),
        ('Logical Storage', 'requests.storage'),
    ):
        assert f"('{label}', quota.get('{key}'))" in template
    assert 'Frozen Namespace ResourceQuota · Not live utilization' in template
    assert 'grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3' in template
    assert "('CPU Limit', (limit_defaults.get('default') or {}).get('cpu'))" in template
    assert "('Memory Limit', (limit_defaults.get('default') or {}).get('memory'))" in template
    assert 'item.allocation_quota_json or {}' in template
    assert 'item.allocation_limit_defaults_json or {}' in template
    assert 'item.allocation_storage_policy_json or {}' in template
    assert 'item.allocation_customized' in template
    assert 'item.provisioning_message' in template
    assert 'item.last_reconciled_at' in template
    assert 'Quota &amp; LimitRange Details' in template
    # Alignment and semantics: indentation in the Jinja source must not
    # appear as literal leading spaces in provider reconciliation messages.
    assert 'p-0 text-left shadow-2xl' in template
    assert 'bg-surface-page p-4 text-left sm:p-5' in template
    assert (
        '<p class="whitespace-pre-line break-words text-sm leading-6 text-content-secondary">{{ item.provisioning_message or'
        in template
    )
    assert 'whitespace-pre-wrap break-words text-sm leading-6 text-content-secondary' not in template
    assert 'aria-label="Namespace identity and authority"' in template
    assert 'Source Profile</p>' in template
    assert 'Effective Snapshot</p>' in template
    assert 'border-l-2 border-kaori-primary/30 pl-3 text-left' in template
    assert (
        template.index('Committed Allocation</h3>')
        < template.index('Reconciliation</h3>')
        < template.index('Quota &amp; LimitRange Details')
    )
    assert 'Not declared' in template
    assert 'Provider Mirrored' in template
    assert 'Control Unavailable' in template
    assert 'allocation_quota_json: Mapped[dict | None]' in model
    assert 'allocation_limit_defaults_json: Mapped[dict | None]' in model
    assert 'allocation_storage_policy_json: Mapped[dict | None]' in model


def test_namespace_provisioning_rows_separate_identity_allocation_and_state() -> None:
    template = read('app/templates/kubernetes/tenant/partials/_namespace_registry.html')
    source = template.split('{% for item in namespaces %}', 1)[1].split('<dialog id="{{ dialog_id }}"', 1)[0]

    # Operator scanning: identity + ownership/generation; pinned source/provider;
    # canonical state + existing control distinction. No clipped provider message.
    assert source.count('title="{{ item.namespace }}"') == 1
    assert "item.ownership_status == 'managed'" in source
    assert 'table_label.status_label(item.ownership_status' in source
    assert 'Gen {{ item.generation }}' in source
    assert 'profile_display' in source
    assert 'title="{{ profile_name }}"' in source
    assert "item.resource_profile_version else 'No pinned snapshot'" in source
    assert '{{ provider_name }}' in source
    assert 'title="Control: {{ control_label }}"' in source
    assert 'table_label.status_label(item.provisioning_status' in source
    assert 'provisioning_message' not in source

    # The rest of the modal is still authoritative for full allocation,
    # reconciliation explanation and provider identity; no new mutation path.
    assert 'data-kaori-native-dialog' in template
    assert '{{ profile_name }}</p>' in template
    assert 'item.provisioning_message or' in template
    assert 'item.allocation_quota_json or {}' in template
    assert "registry_ui.footer('tenant.namespace_provisioning'" in template
    assert 'registry_ui.filter_form(' in template
    assert 'hx-post' not in template


def test_namespace_allocation_dialog_renders_resourcequota_limits_not_container_defaults() -> None:
    import re

    from jinja2 import Environment

    source = read('app/templates/kubernetes/tenant/partials/_namespace_registry.html')
    marker = '<dl class="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3">'
    begin = source.index(marker)
    end = source.index('</dl>', begin) + len('</dl>')
    render = Environment(autoescape=True).from_string(source[begin:end]).render

    observed = render(
        quota={
            'limits.cpu': '4',
            'limits.memory': '8Gi',
            'pods': '10',
            'requests.storage': '1Gi',
        },
        limit_defaults={'default': {'cpu': '250m', 'memory': '512Mi'}},
    )
    expected = (
        ('CPU Requests', 'Not declared'),
        ('CPU Limits', '4'),
        ('Memory Requests', 'Not declared'),
        ('Memory Limits', '8Gi'),
        ('Pod Slots', '10'),
        ('Logical Storage', '1Gi'),
    )
    for label, value in expected:
        pattern = rf'>{re.escape(label)}</dt>\s*<dd[^>]*>\s*{re.escape(value)}\s*</dd>'
        assert re.search(pattern, observed)

    # Container default LimitRange values must not appear as quota limits.
    assert '250m' not in observed
    assert '512Mi' not in observed
    empty = render(quota={})
    assert empty.count('Not declared') == 6


def test_namespace_registry_uses_existing_compact_profile_naming_rules() -> None:
    from jinja2 import Environment

    source = read('app/templates/kubernetes/tenant/partials/_namespace_registry.html')
    start = source.index("{% set adopted_prefix = profile_name.startswith('Adopted ') %}")
    end = source.index('{% set quota = item.allocation_quota_json or {} %}', start)
    snippet = Environment(autoescape=True).from_string(
        source[start:end] + '{{ profile_display }}||{{ control_label or "None" }}'
    )

    def display(
        name: str,
        *,
        control: str | None = 'kaori_managed',
        mirrored: bool = False,
        observed: bool = False,
    ) -> tuple[str, str]:
        rendered = snippet.render(
            profile_name=name,
            provider_mirrored=mirrored,
            adopted_observed=observed,
            allocation_control=control,
        )
        first, second = rendered.split('||')
        return first.strip(), second.strip()

    assert display('Platform Medium') == ('Platform Medium', 'KAORI Managed')
    assert display('Adopted tenant-uat-demo Baseline · 4')[0] == 'tenant-uat-demo Baseline 4'
    assert display('Adopted tenant-uat-demo Baseline · 3')[0] == 'tenant-uat-demo Baseline 3'
    assert (
        display('Adopted kaori-demo Allocation · e36817ba-f3d5-433b-a26e-e8106bf28abb')[0]
        == 'kaori-demo Allocation · e36817ba'
    )
    assert display('Adopted kaori-demo/kaori-demo-dev Policy · None', mirrored=True)[1] == ('Provider Mirrored')
    assert display('Imported Provider Baseline', observed=True, control=None)[1] == ('Awaiting Takeover')
    assert display('No profile', control=None) == ('No profile', 'None')
    long_name, _ = display('Unrecognized profile ' + 'x' * 100)
    assert len(long_name) <= 42

    # Compact name and authority are display-only, never replacing full
    # committed identity/effective evidence in the read-only modal.
    assert 'title="{{ profile_name }}"' in source
    assert '{{ profile_name }}</p>' in source
    assert 'item.allocation_quota_json or {}' in source
    assert 'item.provisioning_message or' in source
    assert 'data-kaori-native-dialog' in source
    assert "registry_ui.footer('tenant.namespace_provisioning'" in source


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
        summary = section.split('</summary>', 1)[0]
        assert "variant='guide'" in summary
        assert 'info_tip.render(' in summary
        assert 'Section help' not in section
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
    assert 'syncManagedState()' in script
    assert 'data-tenant-advanced-controls' in controls
    assert '<details ' in controls


def test_resource_profile_registry_offline_css_covers_both_layout_modes() -> None:
    source = read('frontend/styles.css')
    compiled = read('app/static/css/output.css')
    # Tailwind's production minifier can remove selector quotes and CSS whitespace.
    # Check the same scoped behavior in both authored and compiled CSS.
    for css in (source, compiled):
        compact = re.sub(r'\s+', '', css).replace("'", '').replace('"', '')
        assert '[data-kaori-responsive-registry=resource-profiles]' in compact
        assert 'display:table-header-group' in compact
        assert 'display:table-row-group' in compact
        assert 'grid-template-columns:repeat(2,minmax(0,1fr))' in compact
        assert 'data-kaori-registry-empty' in compact
        assert re.search(r'@media\([^)]*639px[^)]*\)', compact) is not None


def test_resource_profile_registry_reflows_without_forced_horizontal_scrolling() -> None:
    registry = read('app/templates/kubernetes/tenant/partials/_resource_profile_registry.html')
    assert 'data-kaori-responsive-registry="resource-profiles"' in registry
    assert 'overflow-x-auto' not in registry
    assert 'min-w-[1150px]' not in registry
    assert "table_ui.table_classes('block w-full xl:table xl:!table-fixed')" in registry
    assert 'hidden xl:table-header-group' in registry
    assert 'xl:table-row-group' in registry
    assert 'grid min-w-0 grid-cols-1' in registry
    assert 'sm:grid-cols-2 xl:table-row' in registry
    assert 'col-span-full min-w-0' in registry
    assert registry.count('xl:table-cell') >= 6
    for label in ('Contract', 'Allocation', 'Usage'):
        assert f'xl:hidden">{label}</span>' in registry
    assert 'data-dialog-target="resource-profile-manage-{{ profile.id }}"' in registry
    # The desktop Manage action follows the same 16px right inset as the
    # shared Kubernetes Inventory action column and this table's Action header.
    action_cell = registry.split('<td class="{{ table_ui.cell_classes(action=true) }}', 1)[1].split('</td>', 1)[0]
    assert 'xl:!px-4' in action_cell
    assert 'xl:!px-2' not in action_cell
    assert 'colspan="5" class="block p-0 xl:table-cell"' in registry
    assert 'data-kaori-registry-empty' in registry
    assert registry.count('data-kaori-profile-column-label') == 3


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
    assert "table_ui.table_classes('block w-full xl:table xl:!table-fixed')" in registry
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
    assert 'profile.name[8:] if adopted_baseline else profile.name' in registry
    assert "registry_name.rsplit(' · ', 1)" in registry
    assert 'name_parts[1][:8]' in registry
    assert "registry_name|truncate(44, True, '…')" in registry
    assert "('Adopted baseline' if adopted_baseline else 'Profile') ~ ' · #' ~ profile.id" in registry
    assert "table_ui.title_cell(registry_name, registry_meta, 'layers-3')" in registry
    assert 'table_ui.title_cell(profile.name, profile.description' not in registry
    assert "profile.description or 'Reusable allocation contract'" not in registry
    assert 'aria-label="Manage Resource Profile {{ profile.name }}"' in registry

    # Shared table geometry, HTMX, default pagination and actual Manage action stay intact.
    assert "title_cell(name, supporting_text='', icon='', supporting_content=None)" in table
    assert 'table_primitives.title_cell(name, supporting_text, icon, supporting_content)' in table
    assert "table_ui.table_classes('block w-full xl:table xl:!table-fixed')" in registry
    assert 'registry_ui.footer' in registry
    assert 'data-dialog-target="resource-profile-manage-{{ profile.id }}"' in registry

    # Modal is the full authority for both editable Custom and locked KAORI presets.
    assert 'id="resource-profile-manage-{{ profile.id }}-title"' in dialogs
    assert 'title="{{ profile.name }}">{{ profile.name }}</h3>' in dialogs
    assert 'aria-label="Resource Profile description"' in dialogs
    assert (
        '<p class="whitespace-pre-wrap break-words text-sm leading-6 text-content-secondary">{{ profile.description }}</p>'
        in dialogs
    )
    assert '<textarea name="profile_description"' in dialogs
    assert "{{ profile.description or '' }}</textarea>" in dialogs
    assert 'value="{{ profile.description or \'\' }}"' in dialogs
    assert 'data-kaori-native-dialog' in dialogs


def test_resource_profile_workspace_redesign_preserves_governance_and_modal_workflow() -> None:
    registry = read('app/templates/kubernetes/tenant/partials/_resource_profile_registry.html')
    dialogs = read('app/templates/kubernetes/tenant/partials/_resource_profile_management_dialogs.html')

    # One coherent fixed-column contract; no truncated resource evidence.
    for label, width in [('Profile', 28), ('Contract', 19), ('Allocation', 25), ('Usage', 16), ('Action', 12)]:
        assert f'w-[{width}%]">{label}' in registry
    assert "table_ui.table_classes('block w-full xl:table xl:!table-fixed')" in registry
    assert 'grid grid-cols-2 gap-x-3 gap-y-2' in registry
    assert "('CPU', profile.quota_hard_json.get('requests.cpu') or 'Not Managed')" in registry
    assert "('Memory', profile.quota_hard_json.get('requests.memory') or 'Not Managed')" in registry
    assert "('Pods', profile.quota_hard_json.get('pods') or 'Not Managed')" in registry
    assert "('Storage', profile.quota_hard_json.get('requests.storage') or 'Not Managed')" in registry
    assert 'registry_ui.footer' in registry
    assert 'data-kaori-dialog-open' in registry

    # Actual full identity is a managed detail surface, not a repeated header wall.
    assert "Manage Resource Profile' if editable else 'Resource Profile Details" in dialogs
    assert 'aria-label="Resource Profile identity"' in dialogs
    assert 'title="{{ profile.name }}">{{ profile.name }}</h3>' in dialogs
    assert '<textarea name="profile_description"' in dialogs
    assert 'sm:col-span-2' in dialogs
    assert 'Profile Configuration' in dialogs
    assert 'Namespace References' in dialogs
    assert 'Capacity Decisions' in dialogs

    # Native progressive disclosures and original form contracts apply to both
    # editable Custom profiles and fixed built-in presets.
    assert dialogs.count('Namespace quotas and PVC limits') == 2
    assert dialogs.count('Services, ConfigMaps and Secrets') == 2
    assert dialogs.count('LimitRange request and limit defaults') == 2
    assert dialogs.count('<details class="group overflow-hidden rounded-xl') == 6
    assert dialogs.count('id="resource-profile-update-form-{{ profile.id }}"') == 2
    assert dialogs.count('advanced_profile_controls.render(') == 2
    assert 'name="control_contract_present"' in dialogs
    assert 'name="advanced_control_contract_present"' in dialogs

    # Rollout remains an explicit, Tenant-scoped POST with separate eligibility.
    assert 'aria-labelledby="resource-profile-rollout-{{ profile.id }}-heading"' in dialogs
    assert re.search(r'<select name="tenant_id"\s+required', dialogs)
    assert "target.provider_key != 'native_kubernetes'" in dialogs
    assert 'How rollout is applied' in dialogs
    assert 'One Tenant at a time' in dialogs
    assert 'form="resource-profile-update-form-{{ profile.id }}"' in dialogs
    assert "url_for('tenant.rollout_resource_profile_route', profile_id=profile.id)" in dialogs


def test_profile_manage_modal_copy_and_grouped_summary_remain_bounded() -> None:
    dialogs = read('app/templates/kubernetes/tenant/partials/_resource_profile_management_dialogs.html')

    # Status and lineage are rendered through canonical labels, not standalone prose.
    assert "table_label.status_label('Editable' if editable else 'Versioned Controls'" in dialogs
    assert (
        "table_label.metadata_label('Independent Custom · Operator-managed values', 'layers-3', wrap=true)" in dialogs
    )
    assert "table_label.metadata_label('Canonical KAORI preset · Fixed values', 'lock-keyhole', wrap=true)" in dialogs

    # Two intentional groups replace unstructured, widely separated figures.
    summary = dialogs
    assert 'aria-label="Profile contract and usage summary"' in summary
    assert 'sm:grid-cols-2 sm:divide-x sm:divide-y-0' in summary
    assert '<h3 class="text-xs font-semibold text-content-secondary">Contract</h3>' in summary
    assert '<h3 class="text-xs font-semibold text-content-secondary">Usage</h3>' in summary
    for metric in ('Class', 'Version', 'Namespace References', 'Capacity Decisions'):
        assert f'>{metric}</dt>' in summary

    # Legacy descriptions are presentation-shortened, never overwritten in forms.
    assert "profile.description.startswith('Explicit governance-cutover profile materialized" in dialogs
    assert 'Adopted baseline profile; no provider value changes requested.' in dialogs
    assert '<textarea name="profile_description"' in dialogs
    assert "{{ profile.description or '' }}</textarea>" in dialogs
    assert 'value="{{ profile.description or \'\' }}"' in dialogs

    # Governance boundary still explicitly covers committed version, admission and read-back.
    assert (
        'Existing Namespace allocations stay unchanged; edits affect future allocations until explicitly applied.'
        in dialogs
    )
    assert 'Each Namespace is admitted, applied, and verified separately.' in dialogs
    assert 'Blocked Namespaces retain their prior committed version.' in dialogs
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
    assert 'capacity_budget_bars.get(item.cluster.id|string, [])' in capacity
    assert 'sm:grid-cols-[minmax(11rem,1.4fr)_repeat(3,minmax(0,1fr))]' in capacity
    assert 'col-span-3 min-w-0 sm:col-span-1' in capacity
    assert 'lg:grid-cols-3' not in capacity
    assert 'bar.budget' in capacity
    assert 'bar.committed' in capacity
    assert 'bar.headroom' in capacity
    assert '{{ bar.percent }}% used' in capacity
    assert '{{ bar.free_percent }}% left' in capacity
    assert 'components/progress_bar.html' in capacity
    assert 'progress_bar.stacked_bar(bar.percent,' in capacity
    assert 'bar.free_percent,' in capacity
    assert 'style="width: {{ bar.percent }}%"' not in capacity
    assert 'style="width: {{ bar.free_percent }}%"' not in capacity
    progress = read('app/templates/components/progress_bar.html')
    assert 'macro stacked_bar(' in progress
    assert 'role="progressbar"' in progress
    assert 'aria-valuenow="{{ safe_primary_value }}"' in progress
    assert 'data-progress="{{ safe_secondary_value }}"' in progress
    assert 'Percentage unavailable · {{ bar.state }}' in capacity
    assert 'Over budget by {{ bar.shortfall }}' in capacity
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
    assert 'placeholder="Enter GiB amount"' in capacity
    assert 'placeholder="2048"' not in capacity
    assert 'for="tenant-storage-budget-gib"' in capacity
    assert 'id="tenant-storage-budget-gib"' in capacity
    assert 'aria-describedby="tenant-storage-budget-help"' not in capacity
    assert 'tenant-storage-budget-help' not in capacity
    assert 'Blank means Not Governed.' in capacity
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
    assert (
        "'Compute budget available' if item.budget else ('Capacity policy required' if not item.policy else 'Compute evidence required')"
        in capacity
    )
    assert 'Capacity policy required' in capacity
    assert "item.snapshot_state == 'current' else 'Compute evidence required'" not in capacity
    assert "'Compute budget available' if item.snapshot_state" not in capacity
    assert 'Logical storage governed' in capacity
    for column, percent in [('Cluster', 28), ('Evidence', 39), ('State', 17), ('Details', 16)]:
        assert f'w-[{percent}%]">{column}</th>' in capacity
    assert "table_ui.table_classes('min-w-[980px] !table-fixed')" in capacity
    assert 'table_ui.action_classes()' in capacity
    assert 'data-kaori-native-dialog' in capacity
    assert 'data-kaori-dialog-open' in capacity
    # Action cells are deliberately text-right for the registry button, but the
    # nested native dialog must explicitly break text-align inheritance.
    primitives = read('app/templates/components/table_primitives.html')
    assert "{{ 'text-right' if action else 'text-left' }}" in primitives
    modal = capacity.split('<dialog id="{{ dialog_id }}"', 1)[1].split('</dialog>', 1)[0]
    assert 'p-0 text-left shadow-2xl' in modal
    assert 'bg-surface-card px-4 py-4 text-left sm:gap-4' in modal
    assert 'bg-surface-page p-4 text-left sm:p-5' in modal
    assert 'registry_ui.footer' in capacity
    assert 'macro cluster_identity(' in table  # Reuse the existing identity primitive.

    # Canonical committed budget percentages are supplied by existing presentation bars,
    # never recomputed or inferred from formatted display strings in the template.
    dialog = capacity.split('aria-label="Resource allocation comparison"', 1)[1].split('</section>', 1)[0]
    assert 'capacity_budget_bars.get(item.cluster.id|string, [])' in dialog
    assert 'grid grid-cols-3 gap-x-4 gap-y-3' in dialog
    assert 'col-span-3 min-w-0 sm:col-span-1' in dialog
    assert 'sm:sr-only' in dialog
    assert 'bar.label' in dialog
    assert 'bar.budget' in dialog
    assert 'bar.committed' in dialog
    assert 'bar.headroom' in dialog
    assert '{{ bar.percent }}% used' in dialog
    assert '{{ bar.free_percent }}% left' in dialog
    assert 'progress_bar.stacked_bar(bar.percent,' in dialog
    assert "label=bar.label ~ ': ' ~ bar.percent ~ ' percent committed, '" in dialog
    assert "bar.free_percent ~ ' percent remaining'" in dialog
    progress = read('app/templates/components/progress_bar.html')
    assert 'role="progressbar"' in progress
    assert 'aria-label="{{ label }}"' in progress
    assert 'Percentage unavailable · {{ bar.state }}' in dialog
    assert 'Over budget by {{ bar.shortfall }}' in dialog
    assert 'overflow-x-auto' not in dialog
    assert 'data-kaori-dialog-close' in capacity
    assert 'Storage is logical admission capacity.' in capacity
    assert 'Allocation Budget registry and detail visual hierarchy' in docs


def test_capacity_commitment_excludes_deprovisioned_history_and_preserves_unknowns() -> None:
    governance = capacity_governance_source()

    assert 'TenantNamespace.provisioning_status.notin_(' in governance
    assert 'TenantNamespaceProvisioningStatus.DEPROVISIONED.value' in governance
    assert 'TenantNamespaceProvisioningStatus.RELEASED.value' in governance
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
    rollout_context = read('app/kubernetes/tenant/resource_profile_rollout_context.py')
    facade = read('app/kubernetes/tenant/service.py')
    assert 'def _resource_profile_rollout_targets(' in rollout_context
    assert '_resource_profile_rollout_targets = _registry_context._resource_profile_rollout_targets' in facade
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
    assert 'Each Namespace is admitted, applied, and verified separately.' in dialogs
    assert 'Blocked Namespaces retain their prior committed version.' in dialogs
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

    assert 'Update reusable intent; Namespace snapshots stay pinned.' in dialogs
    assert 'sizing stays canonical.' in dialogs
    assert (
        'Control changes create v{{ (profile.version or 1) + 1 }}; Namespace snapshots stay pinned until rollout.'
        in dialogs
    )
    assert 'Managed takeover where authority exists; provider-owned constraints stay mirrored.' not in adoption
    assert 'Adopt with governed provider cutover and equivalent allocation values.' in adoption
    assert 'Attach to the existing Capsule Tenant; keep provider constraints mirrored.' in adoption
    assert 'Adopted / Managed.' in adoption
    assert 'Namespace Attached · Managed Allocation.' in adoption
    assert 'Adopted / Provider Mirrored' in adoption


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
    capacity_scope = read('app/kubernetes/tenant/capacity_allocation_state.py')

    assert 'kubernetes/tenant/partials/_tenant_allocation_overview.html' in parent
    assert parent.index('kubernetes/tenant/partials/_tenant_allocation_overview.html') < parent.index(
        '<section id="{{ capacity_registry_id }}"'
    )
    assert 'Tenant Allocation Overview' in overview
    assert 'allocation_cluster_id' in overview
    assert 'hx-target="#{{ overview_id }}"' in overview
    assert 'hx-select="#{{ overview_id }}"' in overview
    assert 'aria-label="Tenant Contributions evidence footer"' in overview
    assert 'Read-only committed allocation evidence' in overview
    assert 'Scroll to view all' in overview
    assert 'registry_ui.footer' not in overview
    assert 'allocation_tenant_pagination' not in overview
    assert 'row.namespaces' in overview
    assert 'selected.snapshot_state' in overview
    assert 'selected.state' in overview
    assert 'bar.shortfall' in overview
    assert 'bar.known' in overview
    assert "url_for('analytics.capacity')" in overview
    assert "current_user.has_permission('analytics.view')" in overview
    assert 'not actual workload utilization or physical reservations' in overview
    assert 'Operator-governed requests.storage ceiling; not backend physical free space.' in overview

    assert 'build_tenant_allocation_bars(selected)' in routes
    assert "build_tenant_contribution_rows(str(selected['cluster'].id))" in routes
    assert "context['allocation_tenant_total'] = len(tenant_rows)" in routes
    assert 'filter_tenant_contribution_rows(tenant_rows, allocation_search)' in routes
    assert "context['allocation_tenant_matches'] = len(tenant_rows)" in routes
    assert "'allocation_page'" not in routes
    assert "'allocation_per_page'" not in routes
    assert "if active_view == 'capacity' and selected is not None:" in routes
    assert 'get_resource_profile_workspace_context()' in routes
    assert 'build_capacity_governance_summaries' in capacity

    # Reuse #654's exact shared-quota selection, committed aggregation, and
    # committed-state read path. Do not introduce provider calls on navigation.
    assert '_canonical_shared_allocation_quota(cluster_id)' in projection
    assert '_aggregate_committed_allocation(' in projection
    # Allocation visibility uses the same committed scope as admission. Both
    # released and deprovisioned histories are excluded, never live-read.
    assert '_active_namespace_allocation_query()' in projection
    assert '_TERMINAL_NAMESPACE_ALLOCATION_STATUSES' in projection
    assert 'TenantNamespace.provisioning_status.notin_(_TERMINAL_NAMESPACE_ALLOCATION_STATUSES)' in capacity_scope
    assert 'TenantNamespaceProvisioningStatus.DEPROVISIONED.value' in capacity_scope
    assert 'TenantNamespaceProvisioningStatus.RELEASED.value' in capacity_scope
    assert 'allocation_quota_json' not in overview
    assert 'build_client(' not in projection
    assert 'read_namespace(' not in projection
    assert 'requests.get(' not in projection
    assert "('capacity', 'Capacity Governance', 'gauge'" in page


def test_tenant_operations_empty_registries_keep_canonical_pagination_without_horizontal_scroll() -> None:
    from jinja2 import Environment

    # The #959 footer must survive zero results; no phantom wide table headers,
    # redundant "No Data" badge or minimum-width horizontal scrollbar at zero.
    registry_specs = (
        ('_operations_evidence_registry.html', 'operations_evidence_rows'),
        ('_capsule_tenant_quota_drift.html', 'capsule_tenant_quota_drifted'),
        ('_capsule_shared_allocation_drift.html', 'capsule_shared_drift_intents'),
        ('_operations_drift_registry.html', 'operations_drift_rows'),
        ('_operations_access_reconciliation_registry.html', 'operations_access_rows'),
        ('_operations_provider_registry.html', 'operations_provider_rows'),
    )
    for filename, rows in registry_specs:
        template = read('app/templates/kubernetes/tenant/partials/' + filename)
        Environment().parse(template)
        assert f"if {rows} else '!table-fixed'" in template
        assert f'{{% if {rows} %}}' in template
        assert template.index(f'{{% if {rows} %}}') < template.index('<thead')
        # Quote style is formatter-owned; the empty state configuration,
        # zero-result geometry and canonical pagination must stay unchanged.
        normalized_empty_state = template.replace('"', "'")
        assert "{% set empty_state_label = '' %}" in normalized_empty_state
        assert "{% set empty_state_min_height = 'min-h-[128px]' %}" in normalized_empty_state
        assert "{% set empty_state_container_class = '!py-5' %}" in normalized_empty_state
        assert 'components/states/_empty_state.html' in template
        assert "registry_ui.footer('tenant.operations'" in template
        assert 'table_ui.table_classes(' in template
        assert 'overflow-x-auto' in template

    # Data-empty must not globally disable the canonical shared table/footer.
    table = read('app/templates/components/table.html')
    footer = read('app/templates/components/table_registry.html')
    assert 'macro table_classes' in table
    assert 'macro footer(' in footer
    assert 'data-kaori-canonical-registry-rows' in footer


def test_tenant_operations_provider_authority_remains_optional_without_nested_card() -> None:
    from jinja2 import Environment

    page = read('app/templates/kubernetes/tenant/operations.html')
    provider = read('app/templates/kubernetes/tenant/partials/_operations_provider_registry.html')
    access = read('app/templates/kubernetes/tenant/partials/_operations_access_reconciliation_registry.html')

    for src in (page, provider, access):
        Environment().parse(src)

    # #960 owns one Operations primary tab row, and keeps authority as an
    # optional, explanatory reference rather than another visible drift queue.
    assert 'data-tenant-provider-authority-disclosure' in page
    assert 'Provider Authority Reference' in page
    assert 'Reference only—not a drift finding.' in page
    assert 'View Records' in page
    assert '{% set provider_authority_embedded = true %}' in page
    assert '_operations_provider_registry.html" %}' in page
    assert 'View Provider Authority' not in page
    assert 'open>' not in page.split('data-tenant-provider-authority-disclosure', 1)[1].split('<summary', 1)[0]
    assert 'group-open:rotate-180' in page

    # The existing authoritative per-Tenant registry is still present and
    # filterable. Embedded mode removes only its duplicate shell/header; no
    # endpoint, query scope, pagination or provider metadata is discarded.
    assert 'provider_authority_embedded|default(false)' in provider
    assert 'if provider_authority_embedded' in provider
    assert '{% else %}' in provider
    assert "table_ui.inventory_block_header('shield-check'" in provider
    assert "href=\"{{ url_for('tenant.tenants', section='registry') }}\"" in provider
    assert 'registry_ui.filter_form(' in provider
    assert "registry_ui.footer('tenant.operations'" in provider
    assert 'operations_provider_pagination' in provider
    assert 'operations_provider_rows' in provider
    assert 'min-w-[980px] !table-fixed' in provider
    assert 'w-[23%]">Tenant</th>' in provider
    assert 'w-[28%]">Cluster / Environment</th>' in provider
    assert 'w-[31%]">Provider / Authority</th>' in provider
    assert 'w-[18%]">Lifecycle</th>' in provider
    assert 'colspan="4"' in provider
    assert 'tenant.provider_state' in provider
    assert 'tenant.reconciliation_authority' in provider
    assert 'tenant.provider_key' in provider
    assert 'tenant.lifecycle_status' in provider
    assert 'data-kaori-canonical-registry-rows' in read('app/templates/components/table_registry.html')

    # Similar Tenant name/slug pairs are shown once; distinct identifiers
    # remain visible, so this is display-only.
    assert 'grant.tenant.slug|lower != grant.tenant.name|lower' in access
    assert 'title="{{ grant.tenant.slug }}"' in access
    assert 'grant.tenant.name' in access
    assert 'grant.reconciliation_status' in access
    assert "registry_ui.footer('tenant.operations'" in access


def test_allocation_change_all_title_info_tips_are_adjacent_not_corner_actions() -> None:
    """#1179: mirror the canonical Allocation Change heading grammar."""
    templates = (
        ('_allocation_change.html', 'Allocation Change', 'namespace-allocation-change-tip'),
        ('_allocation_cutover.html', 'Adopted Native Governance Cutover', 'allocation-cutover-tip'),
        ('_capsule_tenant_quota_cutover.html', 'Capsule Tenant Quota Governance', 'capsule-tenant-quota-tip'),
        (
            '_capsule_shared_allocation_cutover.html',
            'Capsule Shared Allocation Governance',
            'capsule-shared-cutover-tip',
        ),
    )
    for filename, title, tip_id in templates:
        template = read('app/templates/kubernetes/tenant/partials/' + filename)
        header = template.split('<header', 1)[1].split('</header>', 1)[0]
        assert 'info_tip.render(' in header, filename
        assert header.count('info_tip.render(') == 1, filename
        assert header.count(tip_id) == 1, filename
        assert 'inline-flex' in header, filename
        assert "placement='right'" in header, filename
        assert header.index(title) < header.index('info_tip.render('), filename
        # The header tip must be inside the title's adjacent wrapper, before any badge.
        assert 'items-center gap-1.5' in header, filename
        if filename != '_allocation_change.html':
            assert header.index('info_tip.render(') < header.index('table_label.special_label'), filename
            assert 'items-start justify-between gap-4' not in header, filename
        assert template.count('name="csrf_token"') >= 1, filename
        assert template.count('type="submit"') >= 1, filename


def test_adoption_and_legacy_cutover_guidance_match_approved_current_authority() -> None:
    """#2481: do not conflate #777 Managed-on-Adopt with legacy #762 cutover."""
    from jinja2 import Environment

    templates = {
        '_allocation_cutover.html': (
            'For legacy Adopted / Observed allocation only',
            'Native ResourceQuota / LimitRange',
        ),
        '_capsule_tenant_quota_cutover.html': (
            'For legacy Adopted / Observed allocation only',
            'Tenant.spec.resourceQuotas',
        ),
        '_capsule_shared_allocation_cutover.html': (
            'For legacy Adopted / Observed Capsule allocation only',
            'GlobalResourceQuota',
        ),
    }
    for filename, (legacy_copy, provider_authority) in templates.items():
        source = read('app/templates/kubernetes/tenant/partials/' + filename)
        Environment(autoescape=True).parse(source)
        assert legacy_copy in source, filename
        assert provider_authority in source, filename
        assert 'Managed-on-Adopt' in source, filename
        assert source.count('info_tip.render(') == 1, filename
        assert source.count('name="csrf_token"') >= 1, filename
        assert source.count('type="submit"') >= 1, filename

    operator = read('app/kubernetes/tenant/README.md')
    architecture = read('docs/architecture/kubernetes-tenant-domain.md')
    assert '### Managed Adoption and Legacy Allocation Governance Cutover' in operator
    assert '## Tenant Adoption vs Allocation Cutover — Current Authority' in architecture
    assert '**Adopt & Manage**' in operator
    assert 'New human-confirmed adoption uses **Adopt & Manage**' in operator
    for authority in (
        'capsule_tenant_resource_quotas',
        'Tenant.spec.resourceQuotas',
        'GlobalResourceQuota',
        'native_namespaced',
        'Adopted / Observed',
        'KAORI Managed',
        'Drift & Reconcile',
    ):
        assert authority in operator
        assert authority in architecture
    assert 'The primary action is **Adopt as Observed**' not in operator
    assert 'Submit **Adopt as Observed**' not in operator
    assert 'Tenant.spec.resourceQuotas` and ambiguous/unsupported Capsule authority remain' not in operator
    assert 'Capsule Tenant Quota Governance' in operator
    assert 'Capsule Shared Allocation Governance' in operator
    assert 'Adopted Native Governance Cutover' in operator


def test_adopted_native_cutover_reuses_committed_allocation_comparison() -> None:
    from jinja2 import Environment

    template = read('app/templates/kubernetes/tenant/partials/_allocation_cutover.html')
    script = read('app/static/js/tenant_resource_profile_presets.js')
    Environment(autoescape=True).parse(template)

    assert 'Adopted Native Governance Cutover' in template
    assert 'Adopted Baseline · Observed' in template
    assert 'KAORI Managed · Only after verified cutover' in template
    assert 'Managed Contract Comparison' in template
    assert 'Change Highlights' in template
    assert "('current', 'Observed Baseline', 'Adopted · Provider evidence')" in template
    assert "('proposed', 'Proposed Governed Contract', 'Pending · Explicit cutover')" in template
    for key in ('requests.cpu', 'limits.cpu', 'requests.memory', 'limits.memory', 'pods', 'requests.storage'):
        assert f"'{key}'" in template
    assert "('Min PVC Size', 'min')" in template
    assert "('Max PVC Size', 'max')" in template
    assert 'data-tenant-allocation-metric-side="{{ side }}"' in template
    assert re.search(r'data-tenant-allocation-highlight-count\s+aria-live="polite"', template)
    assert 'data-tenant-allocation-highlight-item' in template
    assert 'data-tenant-allocation-change-namespace' in template
    assert 'data-tenant-allocation-change-profile' in template
    assert "url_for('tenant.cutover_namespace_allocation_route')" in template
    assert 'namespace_cutover_state.get(item.id|string)' in template
    assert 'not can_manage or not namespace_cutover_supported or not profiles' in template
    assert 'name="csrf_token"' in template
    assert 'Cut Over Governance' in template
    assert 'renderContractPreview(current, proposed)' in script
    assert 'renderAdvancedComparison(current, proposed' in script


def test_allocation_comparison_uses_calm_dual_panels_without_metric_card_stacks() -> None:
    from jinja2 import Environment

    template = read('app/templates/kubernetes/tenant/partials/_allocation_change.html')
    script = read('app/static/js/tenant_resource_profile_presets.js')

    Environment(autoescape=True).parse(template)
    assert 'Managed Contract Comparison' in template
    assert "('current', 'Current Contract', 'Active · Frozen evidence')" in template
    assert "('proposed', 'Proposed Contract', 'Pending · Profile intent')" in template
    assert 'data-tenant-allocation-profile="{{ side }}"' in template
    assert '[data-tenant-allocation-profile="current"]' in script
    assert '[data-tenant-allocation-profile="proposed"]' in script
    assert 'data-tenant-allocation-metric-side="{{ side }}"' in template
    assert 'data-tenant-allocation-metric-source="{{ source }}"' in template
    assert 'data-tenant-allocation-metric-key="{{ key }}"' in template
    assert 'border-b border-outline-subtle py-3' in template
    assert re.search(r'data-tenant-allocation-highlight-count\s+aria-live="polite"', template)
    assert re.search(r'data-tenant-allocation-highlight-item\s+hidden', template)
    assert re.search(r'data-tenant-allocation-highlight-more\s+hidden', template)
    assert 'data-tenant-allocation-change-summary' not in template
    assert 'data-tenant-allocation-diff-panel' not in template
    assert 'view_more_content.render(' not in template
    assert "form.querySelectorAll('[data-tenant-allocation-metric-side]')" in script
    assert "if (proposedProfile) proposedProfile.textContent = proposed ? proposedLabel : '—'" in script
    assert 'renderContractPreview(current, proposed)' in script

    # Mutating form, permissions and all three original gates remain untouched.
    assert "url_for('tenant.change_namespace_allocation_route')" in template
    assert 'name="csrf_token"' in template
    assert 'data-tenant-allocation-change-namespace' in template
    assert 'data-tenant-allocation-change-profile' in template
    assert 'Preflight &amp; Apply' in template
    assert 'Governance Gates' in template
    assert 'Capacity Admission' in template
    assert 'Provider Reconcile' in template
    assert 'Read-back & Commit' in template
    assert 'not can_manage or not namespace_allocation_options or not profiles' in template


def test_allocation_comparison_preserves_all_sixteen_frozen_and_proposed_dimensions() -> None:
    """Native allocation and adopted cutover use all sixteen governed profile fields."""
    from jinja2 import Environment

    template = read('app/templates/kubernetes/tenant/partials/_allocation_change.html')
    cutover = read('app/templates/kubernetes/tenant/partials/_allocation_cutover.html')
    shared = read('app/templates/kubernetes/tenant/partials/_resource_profile_coverage_comparison.html')
    script = read('app/static/js/tenant_resource_profile_presets.js')
    registry = read('app/kubernetes/tenant/registry_context.py')
    for source in (template, cutover, shared):
        Environment(autoescape=True).parse(source)

    assert 'coverage_comparison.native_sections(resource_profile_advanced_controls)' in template
    assert 'coverage_comparison.native_sections(resource_profile_advanced_controls)' in cutover
    for name, path in (
        ('CPU Requests', 'quota.requests.cpu'),
        ('CPU Limits', 'quota.limits.cpu'),
        ('Memory Requests', 'quota.requests.memory'),
        ('Memory Limits', 'quota.limits.memory'),
        ('Pods', 'quota.pods'),
        ('PVCs', 'quota.persistentvolumeclaims'),
        ('Total Storage', 'quota.requests.storage'),
        ('Min PVC Size', 'storage_policy.min'),
        ('Max PVC Size', 'storage_policy.max'),
        ('Services', 'quota.services'),
        ('ConfigMaps', 'quota.configmaps'),
        ('Secrets', 'quota.secrets'),
        ('Default CPU Request', 'limits.default_request.cpu'),
        ('Default CPU Limit', 'limits.default.cpu'),
        ('Default Memory Request', 'limits.default_request.memory'),
        ('Default Memory Limit', 'limits.default.memory'),
    ):
        assert f"('{name}', '{path}')" in shared
    assert 'data-tenant-allocation-tech-current="{{ path }}"' in shared
    assert 'data-tenant-allocation-tech-proposed="{{ path }}"' in shared
    assert 'const current = namespaces[namespaceSelect?.value] || null' in script
    assert "profileSelect?.value === 'adopted_baseline' ? current" in script
    assert 'const after = contractValue(proposed, source, key)' in script
    assert "'persistentvolumeclaims'" in script
    assert "'secrets'" in script
    assert "'quota': record.allocation_quota_json or {}" in registry
    assert "'limits': record.allocation_limit_defaults_json or {}" in registry
    assert "'storage_policy': record.allocation_storage_policy_json or {}" in registry
    assert "'quota': profile.quota_hard_json or {}" in registry
    assert "'limits': profile.limit_defaults_json or {}" in registry
    assert "'storage_policy': getattr(profile, 'storage_policy_json', {}) or {}" in registry

def test_allocation_technical_details_use_canonical_accessible_expandables() -> None:
    """#2985 supersedes obsolete vertical tabs with existing Native disclosure."""
    from jinja2 import Environment

    template = read('app/templates/kubernetes/tenant/partials/_allocation_change.html')
    cutover = read('app/templates/kubernetes/tenant/partials/_allocation_cutover.html')
    shared = read('app/templates/kubernetes/tenant/partials/_resource_profile_coverage_comparison.html')
    script = read('app/static/js/tenant_resource_profile_presets.js')
    for source in (template, cutover, shared):
        Environment(autoescape=True).parse(source)
    assert 'components/view_more_content.html' in shared
    assert "data-tenant-profile-coverage=\"native_kubernetes\"" in shared
    for label in ('Basic Resources', 'Storage Guardrails', 'Object Limits', 'Container Defaults', 'Advanced Controls'):
        assert f"'{label}'" in shared
    assert 'data-tenant-allocation-advanced-row="{{ control_key }}"' in shared
    assert 'data-tenant-allocation-advanced-empty' in shared
    assert "data-tenant-allocation-detail-tab" not in template
    assert "const detailTabs" not in script
    assert "selectDetail('objects')" not in script
    assert 'data-tenant-allocation-tech-proposed="{{ path }}"' in shared
    assert 'data-tenant-allocation-change-namespace' in template
    assert "data-tenant-allocation-change-profile" in template
    assert 'data-tenant-allocation-highlight-count' in template
    assert 'data-tenant-allocation-highlight-count' in cutover

def test_allocation_comparison_keeps_advanced_execution_evidence_boundaries() -> None:
    template = read('app/templates/kubernetes/tenant/partials/_allocation_change.html')
    script = read('app/static/js/tenant_resource_profile_presets.js')
    registry = read('app/kubernetes/tenant/registry_context.py')
    page = read('app/templates/kubernetes/tenant/namespace_provisioning.html')
    service = read('app/kubernetes/tenant/service.py')

    assert 'Placement capability preflight; not verified provider execution.' in read('app/templates/kubernetes/tenant/partials/_resource_profile_coverage_comparison.html')
    assert 'This preview never approves or applies changes.' in template
    assert "recorded.get('source_profile_id') != record.resource_profile.public_id" in registry
    assert "recorded.get('source_profile_version') != record.resource_profile_version" in registry
    assert "'resource_profile_advanced_controls': RESOURCE_PROFILE_ADVANCED_CONTROLS" in registry
    assert "'namespace_allocation_advanced_preflight':" in registry
    assert 'tenant-namespace-allocation-advanced-preflight' in page
    assert 'advancedPreflight[namespaceId]?.[profileId]' in script
    assert 'Supported · Preflight' in script
    assert 'Unavailable · Preflight' in script
    assert 'Not recorded' in script
    assert 'Same as current · Not verified' in script
    assert 'if (list) list.hidden = visible === 0' in script
    assert 'attachment_controls = _validate_resource_profile_attachment_controls(' in service


def test_allocation_highlights_are_bounded_conservative_and_selection_sensitive() -> None:
    script = read('app/static/js/tenant_resource_profile_presets.js')

    assert 'const parsedQuantity = (raw) => {' in script
    assert 'const classifyChange = (before, after) => {' in script
    assert "return 'Now defined'" in script
    assert "return 'No longer defined'" in script
    assert "return right > left ? 'Increased' : 'Reduced'" in script
    assert "return prior === next ? null : 'Changed'" in script
    assert 'return Number.isFinite(value) ? value : null' in script
    assert 'const highlightDimensions = [' in script
    assert "['CPU Limits', 'quota', 'limits.cpu']" in script
    assert "['Memory Limits', 'quota', 'limits.memory']" in script
    assert "['Total Storage', 'quota', 'requests.storage']" in script
    assert re.search(r'const changed =\s*current && proposed\s*\? highlightDimensions\.flatMap', script)
    assert "form.querySelectorAll('[data-tenant-allocation-highlight-item]')" in script
    assert 'row.hidden = !diff' in script
    assert 'const extra = Math.max(0, changed.length - rows.length)' in script
    assert 'renderContractPreview(current, proposed)' in script
    assert 'renderAdvancedComparison(current, proposed' in script
    assert "namespaceSelect?.addEventListener('change'," in script
    assert "profileSelect?.addEventListener('change', () => renderAllocationChange())" in script


def test_allocation_full_width_technical_workspace_and_readable_comparison() -> None:
    """#2985 one shared 5-group disclosure serves both Native workspaces."""
    from jinja2 import Environment

    template = read('app/templates/kubernetes/tenant/partials/_allocation_change.html')
    cutover = read('app/templates/kubernetes/tenant/partials/_allocation_cutover.html')
    shared = read('app/templates/kubernetes/tenant/partials/_resource_profile_coverage_comparison.html')
    script = read('app/static/js/tenant_resource_profile_presets.js')
    for source in (template, cutover, shared):
        Environment(autoescape=True).parse(source)
    assert 'mx-auto max-w-5xl' not in template
    assert 'coverage_comparison.native_sections(resource_profile_advanced_controls)' in template
    assert 'coverage_comparison.native_sections(resource_profile_advanced_controls)' in cutover
    assert "open_by_default=key == 'basic'" in shared
    assert "aria_label='Native ' ~ label ~ ' comparison'" in shared
    assert 'min-w-[27rem]' in shared
    assert 'data-tenant-allocation-tech-proposed="{{ path }}"' in shared
    assert 'data-tenant-allocation-advanced-row="{{ control_key }}"' in shared
    assert re.search(r'data-tenant-allocation-highlight-item\\s+hidden', template)
    assert 'border-l-2 border-kaori-primary/20 pl-3' in template
    assert 'data-tenant-allocation-change-namespace' in template
    assert 'renderContractPreview(current, proposed)' in script
    assert "cell.classList.toggle('text-kaori-primary', differs)" in script
    assert 'Read-only comparison. Capacity admission' in shared

def test_allocation_change_section_heading_icons_follow_kaori_hierarchy() -> None:
    from jinja2 import Environment

    template = read('app/templates/kubernetes/tenant/partials/_allocation_change.html')
    Environment(autoescape=True).parse(template)

    # Every major section uses the existing 9x9 KAORI Violet soft icon
    # surface; nested Change Highlights uses an 8x8 icon surface.
    major_sections = (
        ('allocation-change-target-heading', 'crosshair'),
        ('allocation-comparison-heading', 'git-compare-arrows'),
        ('allocation-change-gates-heading', 'shield-check'),
    )
    for heading_id, icon in major_sections:
        section = template.split(f'aria-labelledby="{heading_id}"', 1)[1]
        next_heading = section.split('</section>', 1)[0]
        assert f'data-lucide="{icon}"' in next_heading
        assert 'h-9 w-9 shrink-0' in next_heading
        assert 'bg-kaori-soft text-kaori-primary' in next_heading
        assert 'aria-hidden="true"' in next_heading
        assert f'id="{heading_id}"' in next_heading

    highlight = template.split('aria-labelledby="allocation-change-highlights-heading"', 1)[1]
    assert 'data-lucide="chart-no-axes-column-increasing"' in highlight
    assert 'h-8 w-8 shrink-0' in highlight
    assert 'id="allocation-change-highlights-heading"' in highlight

    detail = template.split('>Technical Details</h4>', 1)[0].rsplit('<div class="border-t border-outline-subtle', 1)[1]
    assert 'data-lucide="sliders-horizontal"' in detail
    assert 'h-9 w-9 shrink-0' in detail

    # Icons convey navigation hierarchy only; the governed contract is still
    # read from the same frozen and versioned quota bindings.
    assert 'data-tenant-allocation-metric-side="{{ side }}"' in template
    assert 'data-tenant-allocation-tech-proposed="{{ path }}"' in read('app/templates/kubernetes/tenant/partials/_resource_profile_coverage_comparison.html')
    assert "url_for('tenant.change_namespace_allocation_route')" in template
    assert 'name="csrf_token"' in template
    assert 'Preflight &amp; Apply' in template
    assert 'grid gap-4 p-4 sm:p-5 lg:grid-cols-2' in template
    assert '<p class="mt-3 text-sm font-semibold text-content-primary">{{ title }}</p>' in template


def test_capacity_operator_limit_exposure_remains_separate_from_request_commitment() -> None:
    from jinja2 import Environment

    form = read('app/templates/kubernetes/tenant/partials/_capacity_governance.html')
    overview = read('app/templates/kubernetes/tenant/partials/_tenant_allocation_overview.html')
    script = read('app/static/js/tenant_resource_profile_presets.js')
    backend = read('app/kubernetes/tenant/capacity_governance.py')
    policy = read('app/kubernetes/tenant/capacity_governance_support.py')
    model = read('app/models/tenant.py')
    migration = read('migrations/versions/20261013_limit_exposure.py')

    Environment(autoescape=True).parse(form)
    Environment(autoescape=True).parse(overview)

    for key, default in (
        ('limit_exposure_mode', 'observe'),
        ('cpu_limit_ratio', '1.50'),
        ('memory_limit_ratio', '1.00'),
    ):
        assert f'name="{key}"' in form
        assert f'data-capacity-policy-field="{key}"' in form
        assert f'data-default-value="{default}"' in form
        assert f"'{key}':" in policy
        assert key in model
        assert key in migration

    assert '<option value="observe">Observe · Planning only</option>' in form
    assert '<option value="enforce">Enforce · Additional admission gate</option>' in form
    assert 'tenant-limit-exposure-policy-tip' in form
    assert 'data-capacity-policy-cluster' in form
    assert 'name="csrf_token"' in form
    assert "url_for('tenant.update_capacity_policy_route')" in form
    assert "const policies = readJson('tenant-capacity-policy-state')" in script
    assert 'input.value = policy?.[name] ?? fallback' in script
    assert 'CPU &amp; Memory Limit Exposure' in overview
    assert 'Maximum declared ResourceQuota limits' in overview
    assert 'selected.limit_exposure' in overview
    assert "exposure.display[field ~ '_committed']" in overview
    assert "exposure.display[field ~ '_threshold']" in overview
    assert "exposure.mode == 'enforce'" in overview
    assert "exposure.state == 'Overcommitted'" in overview
    assert 'Request Commitment above remains the admission baseline.' in overview
    assert "limit_mode == 'enforce'" in backend
    assert 'replace_namespace=request.replacement_namespace' in backend
    assert 'quota_vector_factory=quota_limit_vector' in backend
    assert 'def _operator_limit_ratio(' in backend
    assert "down_revision = '20261012_capsule_handback_guard'" in migration


def test_capacity_policy_reuses_info_tips_without_inline_helper_copy() -> None:
    from jinja2 import Environment

    form = read('app/templates/kubernetes/tenant/partials/_capacity_governance.html')
    Environment(autoescape=True).parse(form)

    for help_id in (
        'tenant-cpu-limit-ratio-help',
        'tenant-memory-limit-ratio-help',
        'tenant-storage-budget-help',
    ):
        assert help_id not in form

    for input_name in ('cpu_limit_ratio', 'memory_limit_ratio', 'tenant_storage_budget_gib'):
        assert f'name="{input_name}"' in form
        assert f'data-capacity-policy-field="{input_name}"' in form

    assert 'tenant-limit-exposure-policy-tip' in form
    assert 'tenant-capacity-storage-budget-tip' in form
    assert 'Blank means Not Governed.' in form
    assert 'CPU ratio multiplies the governed Tenant CPU budget' in form
    assert 'Memory defaults to 1.00' in form
    assert 'Logical budget only.' in form
    assert 'name="csrf_token"' in form


def test_tenant_allocation_guidance_has_single_title_tip_and_budget_formula() -> None:
    from jinja2 import Environment

    overview = read('app/templates/kubernetes/tenant/partials/_tenant_allocation_overview.html')
    Environment(autoescape=True).parse(overview)

    exposure = overview.split('id="tenant-limit-exposure-heading"', 1)[1].split('</section>', 1)[0]
    assert 'components/info_tip.html' in overview
    assert '<section class="overflow-visible rounded-xl' in overview
    assert exposure.count('info_tip.render(') == 1
    assert "'tenant-limit-exposure-guide-tip'" in exposure
    assert exposure.count("placement='right', variant='guide'") == 1
    assert exposure.index('CPU &amp; Memory Limit Exposure') < exposure.index('info_tip.render(')
    assert exposure.index('info_tip.render(') < exposure.index('<div class="overflow-x-auto">')
    assert 'tenant-limit-exposure-assessment-tip' not in exposure
    assert 'tenant-limit-exposure-governance-boundary-tip' not in exposure
    assert 'Exposure assessment</span>' not in exposure
    assert 'Governance boundary</span>' not in exposure
    assert 'exposure.reason,' in exposure  # Tooltip displays actual committed reasoning.
    assert '{{ exposure.reason }}' in exposure  # Only risk reasons remain persistent.
    assert "exposure.state in ['Unknown', 'Near Capacity', 'Overcommitted']" in exposure
    assert 'role="status"' in exposure
    assert 'operational_callout.semantic_border_classes(exposure_tone' in exposure
    assert 'bg-status-critical-soft text-status-critical-text' in exposure
    assert 'bg-status-warning-soft text-status-warning-text' in exposure
    assert "exposure.mode == 'observe'" in exposure
    assert 'Observe never blocks Resource Profile admission.' in exposure
    assert 'Enforce adds a Limits admission check.' in exposure
    assert 'Request Commitment above remains the admission baseline.' in exposure
    assert 'Ratios multiply the governed Tenant budget' in exposure
    assert 'grid gap-3 border-t' not in exposure
    assert 'sm:grid-cols-2' not in exposure

    budget = overview.split('How allocation budgets work', 1)[1].split('</details>', 1)[0]
    assert budget.index('Request budget formula') < budget.index('Logical storage policy')
    assert budget.index('Logical storage policy') < budget.index('ResourceQuota boundary')
    assert 'tenant-allocation-budget-formula-heading' in budget
    assert 'data-lucide="calculator"' in budget
    assert 'font-mono' in budget
    assert 'border-kaori-primary/15 bg-kaori-soft' in budget
    for term in (
        'Tenant Budget',
        'Ready-worker allocatable',
        'platform reserve',
        'safety headroom',
        'unmanaged commitment',
    ):
        assert term in budget
    assert 'Operator-governed requests.storage ceiling; not backend physical free space.' in budget
    assert 'ResourceQuota enforces limits but does not reserve resources on Kubernetes nodes.' in budget
    assert 'data-lucide="database"' in budget
    assert 'sm:grid-cols-2' in budget
    assert 'group-open:rotate-180' in overview
    assert 'allocation_overview.bars' in overview
    assert "exposure.display[field ~ '_committed']" in overview
    assert "exposure.display[field ~ '_threshold']" in overview


def test_capsule_tenant_quota_comparison_discloses_all_ten_managed_dimensions() -> None:
    """#2986: both Capsule authorities disclose full quota and excluded controls."""
    from jinja2 import Environment

    tenant = read('app/templates/kubernetes/tenant/partials/_capsule_tenant_quota_cutover.html')
    shared = read('app/templates/kubernetes/tenant/partials/_capsule_shared_allocation_cutover.html')
    comparison = read('app/templates/kubernetes/tenant/partials/_resource_profile_coverage_comparison.html')
    for source in (tenant, shared, comparison):
        Environment(autoescape=True).parse(source)
    assert tenant.count("coverage_comparison.capsule_sections('capsule_tenant_resource_quotas'") == 2
    assert shared.count("coverage_comparison.capsule_sections('capsule_global_resource_quota'") == 1
    assert "{% macro capsule_sections(authority, advanced_controls={})" in comparison
    for category in ('Basic Resources', 'Storage Guardrails', 'Object Limits',
                     'Per-PVC Policy', 'Container Defaults', 'Advanced Controls'):
        assert f"'{category}'" in comparison
    for key in (
        'requests.cpu', 'limits.cpu', 'requests.memory', 'limits.memory',
        'pods', 'requests.storage', 'persistentvolumeclaims', 'services',
        'configmaps', 'secrets',
    ):
        assert f"'{key}'" in comparison
    assert 'data-tenant-quota-metric-side="{{ side }}"' in comparison
    assert 'data-tenant-quota-metric-key="{{ quota_key }}"' in comparison
    assert 'data-tenant-capsule-external-source="{{ source }}"' in comparison
    assert 'data-tenant-capsule-advanced-preview="{{ control_key }}"' in comparison
    assert 'This quota workflow has no admitted write/read-back authority' in comparison
    assert 'fail closed before mutation' in comparison
    assert tenant.count('data-tenant-capsule-coverage-alert') == 2
    assert tenant.count('data-tenant-capsule-apply-button') == 2
    assert 'data-tenant-capsule-coverage-alert' in shared
    assert 'data-tenant-capsule-apply-button' in shared
    assert tenant.count('name="csrf_token" value="{{ csrf_token() }}"') == 2
    assert shared.count('name="csrf_token" value="{{ csrf_token() }}"') == 1
    macro = comparison.split('{% macro capsule_sections(', 1)[1].split('{%- endmacro %}', 1)[0]
    assert '<form' not in macro and 'hx-post' not in macro
    assert 'data-tenant-quota-managed-form' in tenant
    assert 'data-tenant-quota-allocation-form' in tenant


def test_capsule_quota_highlights_compare_ten_dimensions_not_just_six() -> None:
    """#2980: committed-vs-profile PVC/object changes and absent quota remain visible."""
    js = read('app/static/js/tenant_resource_profile_presets.js')
    start = js.index('const renderCapsuleQuotaPreview = (form, current, proposed) => {')
    end = js.index('const initSharedAllocationForm = (form) => {', start)
    preview = js[start:end]
    dimension_block = preview.split('const dimensions = [', 1)[1].split('        ]', 1)[0]
    entries = re.findall(r"^\s*\['([^']+)', '([^']+)'\],?$", dimension_block, re.MULTILINE)
    assert [key for key, _label in entries] == [
        'requests.cpu', 'limits.cpu', 'requests.memory', 'limits.memory',
        'pods', 'requests.storage', 'persistentvolumeclaims', 'services',
        'configmaps', 'secrets',
    ]
    assert "form.querySelectorAll('[data-tenant-quota-metric-side]')" in preview
    assert 'cell.dataset.tenantQuotaMetricKey' in preview
    assert "form.querySelector('[data-tenant-quota-change-detail]')" in preview
    assert 'changed = comparisonDimensions.filter(([key]) => !equivalent(key, current, proposed))' in preview
    assert 'quota dimensions differ · Read only' in preview
    assert 'const comparisonDimensions = dimensions' in preview
    assert 'dimensions.slice(0, 6)' not in preview
    assert 'const renderCapsuleProfileCoverage = (form, profile) => {' in preview
    assert 'data-tenant-capsule-external-source' in preview
    assert 'data-tenant-capsule-advanced-preview' in preview
    assert 'data-tenant-capsule-coverage-alert' in preview
    assert 'kaoriInitiallyDisabled' in preview
    assert 'comparisonDimensions.length' in preview
    assert 'of 6 quota dimensions differ' not in preview
    assert "a === 'Unbounded' || b === 'Unbounded'" in preview
    assert 'const numericQuantity = (key, value) =>' in preview
    assert 'Number.isFinite(result)' in preview
    assert '.slice(0, 3)' in preview
    assert 'changed.length - 3' in preview
    assert 'highlights.hidden = true' in preview
    assert "highlights.textContent = ''" in preview
    assert 'fetch(' not in preview
    assert '.submit(' not in preview


def test_shared_native_capsule_profile_coverage_matches_canonical_contract() -> None:
    """#2987: the displayed comparison must cover every backend Resource Profile dimension."""
    import ast

    contracts = ast.parse(read('app/kubernetes/tenant/service_contracts.py'))
    symbols = {}
    for stmt in contracts.body:
        if isinstance(stmt, (ast.Assign, ast.AnnAssign)):
            targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id in (
                    '_PROFILE_QUOTA_FIELDS', '_PROFILE_LIMIT_FIELDS', '_PROFILE_STORAGE_FIELDS'
                ):
                    symbols[target.id] = ast.literal_eval(stmt.value)

    quota = set(symbols['_PROFILE_QUOTA_FIELDS'].values())
    limit_fields = {
        'limits.' + '.'.join(parts)
        for parts in symbols['_PROFILE_LIMIT_FIELDS'].values()
    }
    storage_fields = {'storage_policy.' + key for key in symbols['_PROFILE_STORAGE_FIELDS'].values()}
    assert len(quota) == 10 and len(limit_fields) == 4 and len(storage_fields) == 2

    shared = read('app/templates/kubernetes/tenant/partials/_resource_profile_coverage_comparison.html')
    native = shared.split('{% macro native_sections(', 1)[1].split('{%- endmacro %}', 1)[0]
    capsule = shared.split('{% macro capsule_sections(', 1)[1].split('{%- endmacro %}', 1)[0]
    for key in quota:
        assert f"'quota.{key}'" in native
        assert f"'{key}'" in capsule
    for key in limit_fields | storage_fields:
        assert f"'{key}'" in native
    for key in ('persistentvolumeclaims', 'services', 'configmaps', 'secrets'):
        assert f"'{key}'" in capsule
    assert 'data-tenant-capsule-external-source="storage_policy"' in capsule
    assert "'limits', 'Container Defaults'" in capsule
    for label in ('Basic Resources', 'Storage Guardrails', 'Object Limits', 'Container Defaults', 'Advanced Controls'):
        assert f"'{label}'" in native and f"'{label}'" in capsule

    js = read('app/static/js/tenant_resource_profile_presets.js')
    for key in quota:
        assert f"'{key}'" in js
    for key in ('storage_policy', 'limits', 'advanced_controls'):
        assert key in js


def test_capsule_profile_unsupported_mutation_guard_is_not_just_copy() -> None:
    """#2986: selectable UI and both provider write entrypoints must fail closed."""
    js = read('app/static/js/tenant_resource_profile_presets.js')
    tenant_governance = read('app/kubernetes/tenant/capsule_tenant_quota_governance.py')
    grq_governance = read('app/kubernetes/tenant/capsule_allocation_governance.py')
    controls = read('app/kubernetes/tenant/resource_profile_controls.py')
    assert 'const renderCapsuleProfileCoverage = (form, profile) => {' in js
    assert "requestedUnsupported.push('Container Defaults')" in js
    assert "requestedUnsupported.push('Per-PVC Policy')" in js
    assert "apply.disabled = blocked" in js
    assert 'kaoriInitiallyDisabled' in js
    assert js.count('renderCapsuleProfileCoverage(form, proposed)') == 3
    assert tenant_governance.count('_validate_resource_profile_base_controls(profile, tenant)') == 2
    assert grq_governance.count('_validate_resource_profile_base_controls(profile, tenant)') == 1
    assert "'capsule': {" in controls
    assert "'container_defaults': False" in controls
    assert "'pvc_storage_policy': False" in controls
    assert '_validate_resource_profile_attachment_controls(profile, tenant)' in tenant_governance
    assert '_validate_resource_profile_attachment_controls(profile, tenant)' in grq_governance
