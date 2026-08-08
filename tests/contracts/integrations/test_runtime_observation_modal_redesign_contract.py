from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_runtime_and_capability_use_one_view_more_action_contract() -> None:
    actions = read('app/templates/integrations/components/_record_actions.html')
    runtime = read('app/templates/integrations/partials/_runtime_history.html')
    capability = read('app/templates/integrations/kubernetes/partials/_capability_workspace.html') + read('app/templates/integrations/kubernetes/partials/_capability_registry.html')

    assert 'macro view_more(' in actions
    assert 'data-kaori-dialog-open' in actions
    assert 'data-dialog-target="{{ dialog_target }}"' in actions
    assert '{% import "components/table.html" as table_ui %}' in actions
    assert '{{ table_ui.action_classes() }}' in actions
    assert 'data-lucide="chevron-right"' in actions
    assert 'panel-top-open' not in actions
    assert 'h-9' not in actions
    assert 'data-kaori-record-action' in actions
    assert 'record_actions.view_more(' in runtime
    assert "role='runtime-observation'" in runtime
    assert 'record_actions.view_more(' in capability
    assert "role='capability'" in capability
    assert 'data-lucide="expand"' not in runtime


def test_recent_runtime_observations_use_professional_posture_strip_and_shared_actions() -> None:
    runtime = read('app/templates/integrations/partials/_runtime_history.html')

    assert 'data-kaori-runtime-history-posture-strip-v3' in runtime
    assert 'Observation Posture' in runtime
    assert 'Immutable evidence · newest observation first' in runtime
    assert "('ready', 'Ready', runtime_history.posture_counts.ready)" in runtime
    assert "('degraded', 'Attention', runtime_history.posture_counts.attention)" in runtime
    assert "('blocked', 'Blocked', runtime_history.posture_counts.blocked)" in runtime
    assert "('not_observed', 'Not Observed', runtime_history.posture_counts.not_observed)" in runtime
    assert 'action_button.classes()' in runtime
    assert 'inline-flex h-10 items-center justify-center gap-2 rounded-md' not in runtime


def test_runtime_observation_modal_is_decision_first_and_shared() -> None:
    modal = read('app/templates/integrations/components/_runtime_observation_modal.html')

    assert 'integrations/components/_record_detail_modal.html' in modal
    assert 'record_detail_modal.render(' in modal
    assert "size='standard'" in modal
    assert '<dialog' not in modal
    assert 'data-kaori-runtime-observation-dialog-v4' in modal
    assert 'data-kaori-runtime-observation-decision' in modal
    assert 'Observation Decision' in modal
    assert 'data-kaori-runtime-observation-context' in modal
    assert 'Observation Context' in modal
    assert 'data-kaori-runtime-observation-evidence-context' not in modal
    assert 'Evidence Context' not in modal
    assert 'Operational Reading' not in modal
    assert 'row.message' not in modal
    assert 'row.standalone_message' in modal
    assert 'data-kaori-runtime-observation-diagnostic-review' in modal
    assert 'Diagnostic Review' in modal
    assert 'Recommended Action' in modal
    assert 'h-[calc(100dvh' not in modal
    assert 'w-[min(68rem' not in modal
    assert '<details' not in modal


def test_runtime_modal_keeps_optional_lifecycle_and_capability_boundaries() -> None:
    modal = read('app/templates/integrations/components/_runtime_observation_modal.html')

    assert 'data-kaori-runtime-observation-lifecycle-boundary' in modal
    assert 'Kubernetes Lifecycle Boundary' in modal
    assert 'data-kaori-runtime-observation-capability-evidence' in modal
    assert 'Capability Evidence' in modal
    assert 'data-kaori-runtime-observation-capability-drift' in modal
    assert 'Added Capabilities' in modal
    assert 'Removed Capabilities' in modal
