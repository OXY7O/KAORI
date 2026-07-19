import ast
from pathlib import Path


LANDING = Path('app/templates/integrations/alertmanager.html')
INSTANCE_FORM = Path('app/templates/alertmanager/instance_form.html')
INSTANCE_DETAIL = Path('app/templates/alertmanager/instance_detail.html')
DETAIL_CONFIGURATION = Path('app/templates/alertmanager/partials/_detail_configuration.html')
DETAIL_VALIDATION = Path('app/templates/alertmanager/partials/_detail_validation.html')
DETAIL_VALIDATION_CONTENT = Path('app/templates/alertmanager/partials/_detail_validation_content.html')
DETAIL_RUNTIME = Path('app/templates/alertmanager/partials/_detail_runtime.html')
DETAIL_SCOPE = Path('app/templates/alertmanager/partials/_detail_scope.html')
RUNTIME_PANEL = Path('app/templates/alertmanager/partials/_runtime_panel.html')
RUNTIME_RESPONSE = Path('app/templates/alertmanager/partials/_runtime_refresh_response.html')
RUNTIME_HISTORY = Path('app/templates/alertmanager/partials/_runtime_history.html')
FEEDBACK_OOB = Path('app/templates/alertmanager/partials/_operation_feedback_oob.html')
ROUTES = Path('app/alertmanager/routes.py')
REGISTRATION = Path('app/alertmanager/registration.py')
ALERTMANAGER_README = Path('app/alertmanager/README.md')
LEGACY_CONFIG = Path('app/templates/alertmanager/config.html')


def test_alertmanager_landing_hero_matches_kaori_violet_geometry() -> None:
    source = LANDING.read_text(encoding='utf-8')

    required_fragments = (
        'page_hero.shell_classes()',
        'page_hero.layout_classes()',
        'page_hero.content_classes()',
        "page_hero.intro('siren', 'Operational Integration', 'server-cog')",
        'font-medium leading-6 text-brand-foreground-muted sm:text-base',
        'Register, validate, and govern Alertmanager connections and scope bindings.',
        'page_hero.meta_label',
        'page_hero.aside_classes()',
        'flex h-full min-h-[12rem] flex-col justify-between rounded-xl',
        'Integration posture',
        'Connection readiness and bindings',
        'Ready</span>',
        'Bindings</span>',
        'Register Instance',
    )
    missing = [fragment for fragment in required_fragments if fragment not in source]
    assert not missing, f'Alertmanager landing hero contract is incomplete: {missing}'

    forbidden_fragments = (
        'page_hero.supporting_strip',
        'lg:grid-cols-[minmax(0,1fr)_20rem]',
        'Connect Alertmanager as a reusable operational source across infrastructure assets, services, domains, and workflows.',
        'bg-gradient-to-r',
        'from-blue-',
        'to-cyan-',
        'Configured connections ready for operational use',
        'Active source-to-scope mappings',
    )
    found = [fragment for fragment in forbidden_fragments if fragment in source]
    assert not found, f'Alertmanager landing still contains legacy hero patterns: {found}'


def test_alertmanager_instance_hero_uses_the_same_geometry() -> None:
    source = INSTANCE_FORM.read_text(encoding='utf-8')

    required_fragments = (
        'page_hero.shell_classes()',
        'page_hero.layout_classes()',
        'page_hero.content_classes()',
        "page_hero.intro('siren', 'Alertmanager Integration', 'server-cog')",
        'page_hero.aside_classes()',
        'flex h-full min-h-[12rem] flex-col rounded-xl',
        'Create a reusable Alertmanager connection and verify reachability before registration.',
        'Registration posture',
        'Pre-save requirements',
        'Back to Registry',
        'components/table_label.html',
    )
    missing = [fragment for fragment in required_fragments if fragment not in source]
    assert not missing, f'Alertmanager instance hero contract is incomplete: {missing}'

    forbidden_fragments = (
        'min-h-[13rem]',
        'Define a reusable Alertmanager connection for infrastructure assets, services, operational domains, and workflows',
        "('01', 'plug-zap', 'Test Connection'",
    )
    found = [fragment for fragment in forbidden_fragments if fragment in source]
    assert not found, f'Alertmanager instance hero still contains oversized workflow content: {found}'


def test_alertmanager_runtime_panel_uses_semantic_kaori_statuses_and_htmx_indicator() -> None:
    source = RUNTIME_PANEL.read_text(encoding='utf-8')
    history = RUNTIME_HISTORY.read_text(encoding='utf-8')

    required_fragments = (
        'components/table_label.html',
        'table_label.status_label',
        'id="alertmanager-runtime-loading"',
        'hx-indicator="#alertmanager-runtime-loading"',
        'absolute bottom-2 left-5 right-5 h-1 overflow-hidden rounded-full bg-kaori-soft',
        'notification-progress-indeterminate h-full rounded-full bg-kaori-primary',
        'grid gap-3 border-b border-outline-subtle bg-surface-hover',
        'sm:grid-cols-2 sm:p-5 xl:grid-cols-4',
        'Health Interpretation',
        'aria-label="Alertmanager health score',
        'stroke-dashoffset="{{ 100 - runtime_state.health_score }}"',
        'Contributing evidence',
        'Diagnostic Pipeline',
        'Ordered technical checks with evidence, duration, and the next corrective action.',
        '<th class="w-16 px-4 py-3">Step</th>',
        '<th class="min-w-64 px-4 py-3">Check</th>',
        'No action required.',
    )
    missing = [fragment for fragment in required_fragments if fragment not in source]
    assert not missing, f'Alertmanager runtime panel contract is incomplete: {missing}'

    forbidden_runtime_fragments = (
        'xl:grid-cols-6',
        'xl:col-span-5',
        'xl:col-span-7',
        'role="progressbar"',
        'Weighted factors',
        'Recommended fixing',
    )
    found = [fragment for fragment in forbidden_runtime_fragments if fragment in source]
    assert not found, f'Alertmanager runtime panel still uses wasteful legacy geometry: {found}'

    required_history_fragments = (
        'id="alertmanager-history-loading"',
        'absolute bottom-2 left-5 right-5 h-1 overflow-hidden rounded-full bg-kaori-soft',
        'KAORI retains the latest {{ runtime_history.pagination.retention_limit }} records per connection.',
        '{{ runtime_history.pagination.retention_limit }}-record retention',
        'aria-label="Runtime observations per page"',
        'hx-trigger="change"',
        'h-9 w-20 rounded-lg',
        'Showing <span class="font-semibold text-content-primary">',
        'Page {{ runtime_history.pagination.page }} / {{ runtime_history.pagination.total_pages }}',
    )
    missing = [fragment for fragment in required_history_fragments if fragment not in history]
    assert not missing, f'Alertmanager runtime history pagination contract is incomplete: {missing}'

    assert 'Items per page' not in history


def test_alertmanager_copy_is_global_and_has_no_future_product_positioning() -> None:
    landing = LANDING.read_text(encoding='utf-8')
    instance = INSTANCE_FORM.read_text(encoding='utf-8')
    inventory = Path(
        'app/templates/integrations/alertmanager/partials/_inventory_card.html'
    ).read_text(encoding='utf-8')
    combined = '\n'.join((landing, instance, inventory))

    required_fragments = (
        'Register, validate, and govern Alertmanager connections and scope bindings.',
        'multiple operational contexts through governed bindings',
        'systems, services, and workflows that use them',
        'infrastructure assets, services, operational domains, and workflows',
        'workflows, or global contexts through canonical bindings',
    )
    missing = [fragment for fragment in required_fragments if fragment not in combined]
    assert not missing, f'Alertmanager global integration wording is incomplete: {missing}'

    forbidden_fragments = (
        'Kubernetes or future infrastructure',
        'Server, HCI, or Storage',
        'as those asset registries are introduced',
        'future infrastructure scope',
        'Ready for downstream reads',
        'provider-owned',
    )
    found = [fragment for fragment in forbidden_fragments if fragment in combined]
    assert not found, f'Alertmanager still contains product/future positioning: {found}'


def test_register_alertmanager_instance_matches_informative_form_contract() -> None:
    source = INSTANCE_FORM.read_text(encoding='utf-8')

    required_fragments = (
        'id="alertmanager-instance-form"',
        'xl:col-span-8',
        'xl:col-span-4 xl:sticky xl:top-5',
        'Alertmanager Scope &amp; Workflow',
        'Connection Identity &amp; Contract',
        'Connection Type Guide',
        'Externally managed',
        'Shared service',
        'Managed for a specific scope',
        'After Registration',
        'Reusable connection identity',
        'Reachability test',
        'Validation and scope assignment',
        'Allow KAORI to use this connection',
        'maintenance or troubleshooting without deleting the instance',
        "url_for('alertmanager.test_new_instance_connection')",
        'hx-include="#alertmanager-instance-form"',
        'hx-target="#alertmanager-connection-test-result"',
        'Test Connection',
        'Register Instance',
        'focus:border-outline-focus focus:ring-2 focus:ring-outline-focus/20',
        'Register Instance becomes available only after the submitted values pass reachability verification.',
        'name="connection_test_proof"',
        'x-bind:disabled="!connectionVerified"',
        'x-on:alertmanager-connection-tested.window',
        'id="alertmanager-connection-test-loading"',
        'absolute bottom-2 left-4 right-4 h-1 overflow-hidden rounded-full bg-kaori-soft',
        'notification-progress-indeterminate h-full rounded-full bg-kaori-primary',
        "alertmanager/partials/_delete_confirmation_modal.html",
        'data-alertmanager-delete-button',
    )
    missing = [fragment for fragment in required_fragments if fragment not in source]
    assert not missing, f'Register Alertmanager form contract is incomplete: {missing}'

    forbidden_fragments = (
        'Integration Boundary',
        'Source Boundary',
        'font-mono',
        'focus:border-kaori-primary focus:ring-2 focus:ring-outline-focus',
        'Runtime source enabled',
        'Disabled sources are excluded from asset-scope resolution',
        'Instance not registered',
        'Connection not tested',
    )
    found = [fragment for fragment in forbidden_fragments if fragment in source]
    assert not found, f'Register Alertmanager form still contains legacy UI patterns: {found}'



def test_manage_alertmanager_detail_is_domain_tabbed_and_informative() -> None:
    detail = INSTANCE_DETAIL.read_text(encoding='utf-8')
    configuration = DETAIL_CONFIGURATION.read_text(encoding='utf-8')
    validation = '\n'.join((
        DETAIL_VALIDATION.read_text(encoding='utf-8'),
        DETAIL_VALIDATION_CONTENT.read_text(encoding='utf-8'),
    ))
    runtime = DETAIL_RUNTIME.read_text(encoding='utf-8')
    scope = DETAIL_SCOPE.read_text(encoding='utf-8')
    combined = '\n'.join((detail, configuration, validation, runtime, scope))

    required_detail_fragments = (
        'page_hero.shell_classes()',
        'page_hero.layout_classes()',
        'Manage the connection contract, validation evidence, runtime health, and governed scope resolution.',
        'id="alertmanager-detail-tabs"',
        "('configuration', 'Configuration', 'settings-2'",
        "('validation', 'Validation & Capabilities', 'scan-search'",
        "('runtime', 'Runtime & History', 'activity'",
        "('scope', 'Scope & Resolution', 'route'",
        "activeTab === 'configuration'",
        "activeTab === 'validation'",
        "activeTab === 'runtime'",
        "activeTab === 'scope'",
    )
    missing = [fragment for fragment in required_detail_fragments if fragment not in detail]
    assert not missing, f'Alertmanager detail tab workspace is incomplete: {missing}'

    required_domain_fragments = (
        'Connection contract',
        'Change impact',
        'Integration flow',
        'Configuration Flow',
        'What validation does',
        'Why it matters',
        'Operator flow',
        'alertmanager-validation-workspace',
        'id="alertmanager-validation-loading"',
        'absolute bottom-2 left-5 right-5 h-1 overflow-hidden rounded-full bg-kaori-soft',
        'notification-progress-indeterminate h-full rounded-full bg-kaori-primary',
        'Readiness versus health',
        'How monitoring works',
        'Resolver correlation',
        'Binding purpose',
        'Validation guardrails',
        'Resolver correlation',
        'Effective Source Resolution',
        'Instance Lifecycle &amp; Deletion',
    )
    missing = [fragment for fragment in required_domain_fragments if fragment not in combined]
    assert not missing, f'Alertmanager detail domain guidance is incomplete: {missing}'

    forbidden_fragments = (
        'rounded-2xl',
        'font-mono',
        'text-emerald-700',
        'text-red-700',
        'text-amber-700',
        'focus:border-kaori-primary focus:ring-2',
    )
    found = [fragment for fragment in forbidden_fragments if fragment in combined]
    assert not found, f'Alertmanager detail still contains legacy visual patterns: {found}'

    validation_content = DETAIL_VALIDATION_CONTENT.read_text(encoding='utf-8')
    assert 'validation_scope_oob' in validation_content
    assert "alertmanager/partials/_detail_scope.html" in validation_content
    assert 'id="alertmanager-scope-workspace"' in scope

    routes = ROUTES.read_text(encoding='utf-8')
    for fragment in ('#configuration', '#validation', '#scope'):
        assert fragment in routes

def test_alertmanager_validation_and_scope_workspaces_are_actionable() -> None:
    validation = DETAIL_VALIDATION_CONTENT.read_text(encoding='utf-8')
    scope = DETAIL_SCOPE.read_text(encoding='utf-8')
    documentation = ALERTMANAGER_README.read_text(encoding='utf-8')
    bindings = Path('app/alertmanager/bindings.py').read_text(encoding='utf-8')

    required_validation_fragments = (
        'Capability technical detail',
        'Technical probe',
        'Success criteria',
        'Required configuration',
        'Operational impact',
        'Recommended action',
        'Operational domain readiness',
        'Blocking gaps',
        'Enrichment gaps',
    )
    missing = [fragment for fragment in required_validation_fragments if fragment not in validation]
    assert not missing, f'Capability remediation workspace is incomplete: {missing}'

    required_scope_fragments = (
        'Create Binding',
        "hx-post=\"{{ url_for('alertmanager.create_binding', instance_id=instance.id) }}\"",
        'hx-target="#alertmanager-scope-workspace"',
        'hx-swap="outerHTML"',
        'bg-surface-card shadow-sm xl:col-span-5',
        '<h3 class="text-base font-semibold text-content-primary">Create Binding</h3>',
        'Scope identity',
        'Resolution preference',
        'mb-1.5 block text-sm font-semibold text-content-primary',
        'px-3.5 text-sm font-medium text-content-primary',
        'id="alertmanager-binding-loading"',
        'absolute bottom-2 left-4 right-4 h-1 overflow-hidden rounded-full bg-kaori-soft',
        'notification-progress-indeterminate h-full rounded-full bg-kaori-primary',
        'Duplicate instance-to-scope mappings are rejected.',
        'Existing mappings are rejected rather than overwritten silently.',
        'Pre-save validation',
        'Effective source:',
        'Required capabilities',
        'Current instance',
        'binding_feedback',
    )
    missing = [fragment for fragment in required_scope_fragments if fragment not in scope]
    assert not missing, f'Binding HTMX and validation contract is incomplete: {missing}'
    assert 'Add or Update Binding' not in scope
    assert 'class=\"relative self-start overflow-hidden rounded-xl border border-brand-outline bg-kaori-soft\"' not in scope
    assert 'text-[10px] font-semibold uppercase tracking-[0.12em] text-kaori-primary\">Create Binding' not in scope

    assert 'already bound to the selected scope' in bindings
    assert 'already has a primary Alertmanager binding through {provider.name}' in bindings

    required_doc_fragments = (
        '## Validation diagnostics contract',
        '## Runtime health and history contract',
        '## Scope binding contract',
        'duplicate submissions are rejected as **already exists**',
        'without a full-page reload',
    )
    missing = [fragment for fragment in required_doc_fragments if fragment not in documentation]
    assert not missing, f'Alertmanager operational documentation is incomplete: {missing}'


def test_alertmanager_connection_test_feedback_is_toast_only_and_unlocks_registration() -> None:
    partial = Path(
        'app/templates/alertmanager/partials/_connection_test_result.html'
    ).read_text(encoding='utf-8')
    form = INSTANCE_FORM.read_text(encoding='utf-8')
    routes = ROUTES.read_text(encoding='utf-8')
    registration = REGISTRATION.read_text(encoding='utf-8')
    documentation = ALERTMANAGER_README.read_text(encoding='utf-8')

    assert "alertmanager/partials/_operation_feedback_oob.html" in partial
    for forbidden in ('Reachable', 'Not reachable', 'Response time', 'Cluster status'):
        assert forbidden not in partial

    required_form_fragments = (
        'class="hidden" aria-hidden="true"',
        'name="connection_test_proof"',
        'x-bind:disabled="!connectionVerified"',
        'x-on:alertmanager-connection-tested.window',
        'invalidateConnectionTest($event)',
        'Register Instance becomes available only after the submitted values pass reachability verification.',
    )
    missing = [fragment for fragment in required_form_fragments if fragment not in form]
    assert not missing, f'Registration gating UI is incomplete: {missing}'
    assert 'Instance not registered' not in form
    assert 'Connection not tested' not in form

    required_route_fragments = (
        'verify_registration_proof(',
        'issue_registration_proof(',
        "'alertmanager-connection-tested'",
        "'registration_stage': 'connection_test_proof'",
        "'registration_stage': 'pre_save_recheck'",
    )
    missing = [fragment for fragment in required_route_fragments if fragment not in routes]
    assert not missing, f'Registration route contract is incomplete: {missing}'

    required_proof_fragments = (
        'REGISTRATION_PROOF_MAX_AGE_SECONDS = 600',
        'URLSafeTimedSerializer',
        '_form_fingerprint(form)',
        'hashlib.sha256',
        'It never',
    )
    missing = [fragment for fragment in required_proof_fragments if fragment not in registration]
    assert not missing, f'Registration proof contract is incomplete: {missing}'

    required_doc_fragments = (
        '## Registration contract',
        'Administrator clicks Test Connection',
        'Register Instance becomes available',
        'Any form change invalidates the proof',
        'the form does not render duplicate inline success or error panels',
        'POST /integrations/alertmanager/instances/test-connection',
        '`registration.py`',
    )
    missing = [fragment for fragment in required_doc_fragments if fragment not in documentation]
    assert not missing, f'Alertmanager registration documentation is incomplete: {missing}'


def test_alertmanager_delete_actions_use_kaori_confirmation_modal() -> None:
    source = '\n'.join((
        INSTANCE_FORM.read_text(encoding='utf-8'),
        INSTANCE_DETAIL.read_text(encoding='utf-8'),
        DETAIL_SCOPE.read_text(encoding='utf-8'),
    ))
    modal = Path(
        'app/templates/alertmanager/partials/_delete_confirmation_modal.html'
    ).read_text(encoding='utf-8')

    required_form_fragments = (
        'data-delete-title="Remove scope binding?"',
        'data-delete-title="Delete Alertmanager instance?"',
        'data-delete-action-label="Remove binding"',
        'data-delete-action-label="Delete instance"',
        "alertmanager/partials/_delete_confirmation_modal.html",
    )
    missing = [fragment for fragment in required_form_fragments if fragment not in source]
    assert not missing, f'Alertmanager delete triggers are incomplete: {missing}'

    required_modal_fragments = (
        'id="alertmanager-delete-modal"',
        'role="dialog"',
        'border-status-critical-border',
        'data-alertmanager-delete-close',
        'data-operation-submit',
        "closest('[data-alertmanager-delete-button]')",
        "event.key === 'Escape'",
    )
    missing = [fragment for fragment in required_modal_fragments if fragment not in modal]
    assert not missing, f'Alertmanager delete modal contract is incomplete: {missing}'


def test_alertmanager_htmx_actions_render_persistent_notification_toasts() -> None:
    runtime_response = RUNTIME_RESPONSE.read_text(encoding='utf-8')
    feedback_oob = FEEDBACK_OOB.read_text(encoding='utf-8')

    assert 'runtime_feedback' in runtime_response
    assert "alertmanager/partials/_operation_feedback_oob.html" in runtime_response
    assert 'toast_oob=true' in feedback_oob
    assert "components/navigation/_quick_sync_result.html" in feedback_oob
    assert 'notification_saved=operation_feedback.notification_saved' in feedback_oob


def test_every_alertmanager_mutation_route_records_operational_activity() -> None:
    tree = ast.parse(ROUTES.read_text(encoding='utf-8'))
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    action_functions = (
        'new_instance',
        'test_new_instance_connection',
        'instance_detail',
        'refresh_runtime',
        'validate_instance',
        'create_binding',
        'remove_binding',
        'delete_instance',
        'test_cluster_alertmanager',
    )

    missing_functions = [name for name in action_functions if name not in functions]
    assert not missing_functions, f'Alertmanager action routes are missing: {missing_functions}'

    missing_audit_calls = []
    for name in action_functions:
        has_activity_call = any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == 'record_instance_activity'
            for node in ast.walk(functions[name])
        )
        if not has_activity_call:
            missing_audit_calls.append(name)

    assert not missing_audit_calls, (
        'Every Alertmanager mutation must create persistent notification and Activity Audit feedback: '
        f'{missing_audit_calls}'
    )


def test_obsolete_cluster_configuration_template_is_removed() -> None:
    assert not LEGACY_CONFIG.exists(), (
        'The unreferenced blue-gradient Alertmanager cluster configuration template '
        'must not remain alongside the canonical instance workflow.'
    )
