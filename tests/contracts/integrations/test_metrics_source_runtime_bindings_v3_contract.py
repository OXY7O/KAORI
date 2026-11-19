from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_metrics_source_runtime_matches_kubernetes_layout_and_filtered_history() -> None:
    detail = read('app/templates/integrations/observability/metrics_source/partials/_detail_runtime.html')
    runtime = read('app/templates/integrations/observability/metrics_source/partials/_runtime_panel.html')

    assert 'runtime_history_filters_enabled=true' in detail
    assert 'runtime_history_endpoint="metrics.instance_runtime_history"' in detail
    assert 'data-kaori-provider-runtime-kubernetes-pattern' in runtime
    assert 'integrations/components/_runtime_decision.html' in runtime
    assert 'runtime_decision.render(' in runtime
    assert "runtime_identity ~ ' · Readiness ' ~ runtime_state.readiness_label ~ '.'" in runtime
    assert "'metrics-source-runtime-primary-finding-info'" not in runtime
    assert "'Primary Finding context'" not in runtime
    assert 'runtime_primary_finding_info' not in runtime
    assert 'Runtime Evidence' in runtime
    assert 'data-kaori-metrics-source-runtime-evidence' in runtime
    assert 'step.summary' in runtime
    assert 'step.detail' not in runtime
    assert 'step.recommendation' not in runtime
    assert 'lg:sticky' not in runtime
    assert 'xl:sticky' not in runtime
    assert 'workspace_summary_card' not in detail


def test_metrics_bindings_use_kaori_table_and_native_create_dialog() -> None:
    template = read('app/templates/integrations/observability/metrics_source/partials/_detail_scope.html')
    registry = read('app/templates/integrations/observability/metrics_source/partials/_binding_registry.html')
    modal = read('app/templates/integrations/components/_observability_binding_modal.html')

    assert 'Bindings &amp; Consumers' in template
    assert 'Consumer Bindings' in template
    assert 'Effective Consumer Resolution' in template
    assert 'Binding Decision' in template
    assert "identity_copy='Stable selectors isolate consumer evidence.'" in template
    assert '_binding_registry_layout.html' in registry
    assert 'binding_registry_layout.table_classes()' in registry
    assert "integration_status(row.validation_status, display='indicator')" in registry
    assert 'observability_binding_modal.render("metrics-source-create-binding-dialog"' in template
    assert 'data-kaori-dialog-open' in template
    assert 'data-dialog-target="metrics-source-create-binding-dialog"' in template
    assert '<dialog id="{{ dialog_id }}"' in modal
    assert 'm-auto w-[calc(100vw-1rem)] max-w-5xl sm:w-[calc(100vw-2rem)]' in modal


def test_metrics_source_runtime_history_filters_are_server_side() -> None:
    routes = read('app/integrations/observability/metrics_source/application/routes.py')
    presentation = read('app/integrations/observability/metrics_source/application/presentation.py')

    for token in ['history_trigger', 'history_health', 'history_readiness']:
        assert token in routes
        assert token in presentation
    assert 'trigger_type=history_trigger' in routes
    assert 'health_status=history_health' in routes
    assert 'readiness=history_readiness' in routes


def test_runtime_history_presentation_exposes_posture_counts() -> None:
    presentation = read('app/integrations/runtime/presentation.py')

    assert "posture_counts = {'ready': 0, 'attention': 0, 'blocked': 0, 'not_observed': 0}" in presentation
    assert "'posture_counts': posture_counts" in presentation


def test_runtime_decision_primary_finding_is_plain_and_metrics_copy_is_concise() -> None:
    decision = read('app/templates/integrations/components/_runtime_decision.html')
    validation = read(
        'app/templates/integrations/observability/metrics_source/partials/_detail_validation_content.html'
    )

    assert 'components/info_tip.html' not in decision
    assert 'primary_finding_info_title' not in decision
    assert 'info_tip.render(' not in decision
    assert 'Primary Finding' in decision
    assert (
        'Validate compatibility and Prometheus/PromQL core; consumer contracts stay in Bindings & Consumers.'
        in validation
    )


def test_metrics_source_degraded_runtime_uses_compatibility_guidance() -> None:
    runtime = read('app/templates/integrations/observability/metrics_source/partials/_runtime_panel.html')

    assert "runtime_state.readiness == 'degraded'" in runtime
    validation = read(
        'app/templates/integrations/observability/metrics_source/partials/_detail_validation_content.html'
    )
    assert 'Source remains usable with degraded compatibility.' in runtime
    assert 'Upgrade or qualify its release, then rerun Full Validation.' in runtime
    assert 'Source remains usable with degraded compatibility.' in validation
    assert 'Upgrade or qualify its release, then rerun Full Validation.' in validation


def test_binding_technical_queries_reuse_global_copy_without_new_scripts() -> None:
    """Each query owns a visibly separate code surface and delegated Copy."""

    from jinja2 import Environment

    template = read('app/templates/integrations/components/_binding_validation_result.html')
    Environment().parse(template)
    clipboard = read('app/static/js/clipboard.js')
    for marker in (
        'data-kaori-copy-root',
        'data-kaori-copy-button',
        'data-kaori-copy-source',
        'data-kaori-copy-label',
        'data-kaori-copy-icon',
        'data-kaori-binding-query',
        'data-copy-label="Copy"',
        'data-copied-label="Copied"',
        'type="button"',
        'font-mono',
        'overflow-x-auto',
    ):
        assert marker in template

    assert 'check.get("query")' in template
    assert "item.get('technical_checks')" in template
    assert 'data-kaori-copy-button' in clipboard
    assert 'source?.textContent?.trim()' in clipboard
    assert 'clipboard.writeText(text)' in clipboard
    assert '<script' not in template
    assert 'onclick=' not in template


def test_effective_consumer_resolution_uses_compact_capabilities_and_source_rows() -> None:
    """Keep every candidate decision while removing the empty left-column card."""

    from jinja2 import Environment

    template = read('app/templates/integrations/observability/metrics_source/partials/_detail_scope.html')
    Environment().parse(template)
    assert 'data-kaori-consumer-resolution-full-width' in template
    assert 'data-kaori-resolution-capability-contract' in template
    assert 'data-kaori-resolution-candidates' in template
    assert 'data-kaori-resolution-candidate-row' in template
    assert 'for capability in consumer.required_capabilities' in template
    assert 'for candidate in consumer.candidates' in template
    assert 'candidate.instance_name' in template
    assert 'candidate.binding_role|title' in template
    assert 'candidate.priority' in template
    assert 'candidate.decision_reason' in template
    assert 'candidate.is_selected' in template
    assert 'candidate.eligible' in template
    assert "'Selected' if candidate.is_selected else ('Eligible' if candidate.eligible else 'Skipped')" in template
    assert 'candidate.missing_capability_labels or candidate.missing_binding_capabilities' in template
    assert 'No candidate source is registered for this consumer asset.' in template
    assert 'lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]' not in template
    assert 'consumer.required_capabilities|join(' not in template
    assert 'data-kaori-binding-details-row' in read(
        'app/templates/integrations/observability/metrics_source/partials/_binding_registry.html'
    )
