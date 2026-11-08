from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = (
    ROOT
    / 'app/templates/integrations/orchestration/container_orchestrator/providers'
    / 'kubernetes/partials/_runtime_workspace.html'
)


def _source() -> str:
    return TEMPLATE.read_text(encoding='utf-8')


def test_primary_finding_is_compact_and_nonduplicative() -> None:
    source = _source()

    assert 'data-kaori-runtime-primary-finding' in source
    assert 'Primary Finding' in source
    assert "(' Finding' if runtime_state.attention_factors|length == 1 else ' Findings')" in source
    assert '{{ runtime_primary_finding }}' in source
    assert 'components/info_tip.html' not in source
    assert 'kubernetes-runtime-primary-finding-info' not in source
    assert 'Lifecycle and capability detail' not in source
    assert 'data-kaori-runtime-response' in source
    assert 'Operational Response' in source
    assert 'data-kaori-runtime-next-action-card' in source
    assert 'data-kaori-runtime-evidence-handoff' in source
    finding = source.split('data-kaori-runtime-primary-finding', 1)[1].split('runtime-next-action-title', 1)[0]
    assert 'runtime_state.summary' not in finding
    assert 'info_tip.render' not in finding
    assert 'uppercase tracking-wide' in finding
    assert 'truncate' not in finding
    assert 'rounded-xl border border-outline-subtle bg-surface-card p-4 shadow-sm' not in finding


def test_current_page_defers_long_diagnostic_detail_to_runtime_observation_modal() -> None:
    source = _source()

    diagnostic = source.split('data-kaori-runtime-diagnostic-list', 1)[1].split(
        'data-kaori-runtime-observation-boundary', 1
    )[0]
    assert '{{ item.summary }}' in diagnostic
    assert 'Full Validation readiness remains independently evaluated.' in source
    assert '{{ item.detail }}' not in diagnostic
    assert '{{ item.recommendation }}' not in diagnostic
    assert 'Detailed evidence and remediation are available from Recent Runtime Observations.' in source


def test_runtime_copy_and_extended_lifecycle_summary_are_compact() -> None:
    source = _source()
    messages = (
        ROOT / 'app/integrations/orchestration/container_orchestrator/adapters/kubernetes_api/messages.py'
    ).read_text(encoding='utf-8')

    assert 'Review persisted runtime health, diagnostics, lifecycle context, and validation boundaries.' in source
    assert (
        'Runtime health gates current operation; Full Validation readiness remains independently evaluated.'
    ) in source
    assert 'uses KAORI Extended support. Upgrade recommended.' in messages
    assert "return 'Optional gaps do not affect core readiness.'" in messages

    presentation = (ROOT / 'app/integrations/runtime/presentation.py').read_text(encoding='utf-8')
    assert 'def _compact_kubernetes_extended_summary(' in presentation
    assert "return f'{subject} uses KAORI Extended support. Upgrade recommended.'" in presentation

    primary_summary = presentation.split('def _runtime_primary_summary(', 1)[1].split(
        'def _runtime_decision_summary(', 1
    )[0]
    decision_summary = presentation.split('def _runtime_decision_summary(', 1)[1].split(
        'def _message_repeats_diagnostic(', 1
    )[0]
    assert '_compact_kubernetes_extended_summary(summary)' in primary_summary
    assert '_compact_kubernetes_extended_summary(detail)' in decision_summary
