from pathlib import Path


ROUTES = Path('app/prometheus/routes.py')
SERVICE = Path('app/prometheus/service.py')
REPOSITORY = Path('app/prometheus/repository.py')
DETAIL = Path('app/templates/prometheus/instance_detail.html')
BINDINGS = Path('app/templates/prometheus/instances.html')
FORM = Path('app/templates/prometheus/instance_form.html')
CONFIG = Path('app/templates/prometheus/config.html')
RUNTIME = Path('app/templates/prometheus/partials/_runtime_panel.html')
MODAL = Path('app/templates/prometheus/partials/_delete_confirmation_modal.html')
DOC = Path('app/prometheus/README.md')
AUDIT = Path('docs/design/audits/PROMETHEUS_STYLE_AND_LIFECYCLE_AUDIT_2026_07.md')


def test_prometheus_instance_delete_route_and_service_are_governed() -> None:
    routes = ROUTES.read_text(encoding='utf-8')
    service = SERVICE.read_text(encoding='utf-8')
    repository = REPOSITORY.read_text(encoding='utf-8')

    assert "endpoint='delete_instance'" in routes
    assert 'def delete_instance(instance_id: int)' in routes
    assert 'remove_prometheus_instance(instance)' in routes
    assert "event_type='prometheus_instance_deleted'" in routes
    assert "event_type='prometheus_instance_delete_rejected'" in routes
    assert 'def remove_prometheus_instance(instance: PrometheusInstance)' in service
    assert "Remove all scope bindings before deleting this Prometheus instance." in service
    assert 'IntegrationBinding.query.filter_by' in service
    assert 'db.session.get(IntegrationInstance' in service
    assert 'db.session.delete(instance)' in service
    assert 'db.session.delete(canonical)' in service
    assert 'enabled_only: bool = False' in repository
    assert 'enabled_only=True' in repository


def test_prometheus_delete_action_is_contextual_and_blocked_by_bindings() -> None:
    detail = DETAIL.read_text(encoding='utf-8')

    required = (
        'Instance Lifecycle &amp; Deletion',
        'data-prometheus-delete-button',
        'data-delete-url="{{ delete_instance_url }}"',
        '{% if delete_instance_url %}',
        '{% if bindings %}disabled{% endif %}',
        'Deletion Is Blocked While Bindings Remain',
        'Historical runtime observations and Activity Audit records are retained after deletion.',
    )
    missing = [fragment for fragment in required if fragment not in detail]
    assert not missing, f'Prometheus deletion workspace is incomplete: {missing}'


def test_prometheus_destructive_actions_use_shared_modal_not_browser_confirm() -> None:
    modal = MODAL.read_text(encoding='utf-8')
    all_prometheus_templates = '\n'.join(
        path.read_text(encoding='utf-8')
        for path in Path('app/templates/prometheus').rglob('*.html')
    )

    required = (
        'id="prometheus-delete-modal"',
        'role="dialog"',
        'aria-modal="true"',
        'data-prometheus-delete-close',
        'data-prometheus-delete-button',
        "event.key === 'Escape'",
        'trigger?.focus()',
    )
    missing = [fragment for fragment in required if fragment not in modal]
    assert not missing, f'Prometheus delete modal is incomplete: {missing}'
    assert 'confirm(' not in all_prometheus_templates
    assert "{% include 'prometheus/partials/_delete_confirmation_modal.html' %}" in DETAIL.read_text(encoding='utf-8')
    assert "{% include 'prometheus/partials/_delete_confirmation_modal.html' %}" in BINDINGS.read_text(encoding='utf-8')


def test_prometheus_workspaces_reuse_global_style_components() -> None:
    detail = DETAIL.read_text(encoding='utf-8')
    form = FORM.read_text(encoding='utf-8')
    config = CONFIG.read_text(encoding='utf-8')
    runtime = RUNTIME.read_text(encoding='utf-8')

    assert detail.count('workspace_summary_card.render') >= 12
    assert config.count('workspace_summary_card.render') >= 9
    assert 'info_flow.render' in detail
    assert 'info_flow.render' in form
    assert 'info_flow.render' in config
    assert 'health_interpretation.render' in runtime
    assert 'stroke-dashoffset' not in runtime
    assert '<svg' not in runtime
    assert 'context_guidance_card.render' not in detail
    assert 'context_guidance_card.render' in form
    assert "'After Registration'" in form
    assert 'context_guidance_card.render' not in config


def test_prometheus_audit_and_module_contract_document_lifecycle() -> None:
    module_doc = DOC.read_text(encoding='utf-8')
    audit = AUDIT.read_text(encoding='utf-8')

    required_doc = (
        'Prometheus Manage UI and lifecycle contract',
        'Instance deletion',
        'Every provider-neutral scope binding must be removed first',
        'Historical runtime observations and Activity Audit records remain available.',
        'registered as reusable provider instances',
    )
    missing = [fragment for fragment in required_doc if fragment not in module_doc]
    assert not missing, f'Prometheus module lifecycle documentation is incomplete: {missing}'
    assert 'rather than managed as a free-standing provider instance' not in module_doc

    required_audit = (
        'Prometheus Style and Lifecycle Audit',
        'Registered instances had no governed delete lifecycle',
        'Scope & Resolution → Instance Lifecycle & Deletion',
        'deletion has no live Prometheus or Thanos dependency',
    )
    missing = [fragment for fragment in required_audit if fragment not in audit]
    assert not missing, f'Prometheus audit is incomplete: {missing}'


def test_prometheus_title_case_and_full_validation_wording_are_consistent() -> None:
    templates = "\n".join(
        path.read_text(encoding="utf-8")
        for base in (Path("app/templates/prometheus"), Path("app/templates/integrations/prometheus"))
        for path in base.rglob("*.html")
    )
    templates += "\n" + Path("app/templates/integrations/prometheus.html").read_text(encoding="utf-8")

    prohibited = (
        "Run Validation",
        "100-record Retention",
        "Prometheus-compatible API",
        "Capability-aware validation",
        "Register before validation",
        "Revalidate after changes",
        "Needs review",
        "Detected version",
        "Query profile",
        "Historical coverage",
        "Not detected",
        "Not assigned",
    )
    present = [fragment for fragment in prohibited if fragment in templates]
    assert not present, f"Stale Prometheus casing or validation wording remains: {present}"
