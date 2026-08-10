from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding='utf-8')


def test_capability_view_more_uses_native_top_layer_dialog() -> None:
    capability = read('app/templates/integrations/kubernetes/partials/_capability_workspace.html') + read(
        'app/templates/integrations/kubernetes/partials/_capability_registry.html'
    )
    modal = read('app/templates/integrations/components/_record_detail_modal.html')
    actions = read('app/templates/integrations/components/_record_actions.html')

    assert 'data-kaori-capability-native-dialogs' in capability
    assert 'record_actions.view_more(' in capability
    assert "'capability-detail-modal-' ~ loop.index" in capability
    assert "role='capability'" in capability
    assert 'data-kaori-dialog-open' in actions
    assert 'data-dialog-target="{{ dialog_target }}"' in actions
    assert 'aria-haspopup="dialog"' in actions
    assert '{% import "components/table.html" as table_ui %}' in actions
    assert '{{ table_ui.action_classes() }}' in actions
    assert 'data-lucide="chevron-right"' in actions
    assert 'data-lucide="panel-top-open"' not in actions
    assert 'h-9 items-center' not in actions
    assert 'data-kaori-record-action' in actions
    assert 'record_detail_modal.render(' in capability

    assert '<dialog id="{{ modal_id }}"' in modal
    assert 'data-kaori-native-dialog' in modal
    assert 'method="dialog"' in modal
    assert 'onclick=' not in modal
    assert 'data-kaori-dialog-close' in modal
    assert 'kaori-native-dialog' in modal
    assert 'backdrop:bg-slate-950/70' not in modal

    assert 'x-teleport="body"' not in modal
    assert 'x-show=' not in modal
    assert 'detailOpen' not in modal
    assert 'selectedDetail' not in modal
    assert 'openDetail(key)' not in capability
    assert 'detailOpen: false' not in capability
    assert 'selectedDetail: null' not in capability


def test_capability_dialog_uses_compact_professional_decision_layout() -> None:
    capability = read('app/templates/integrations/kubernetes/partials/_capability_workspace.html') + read(
        'app/templates/integrations/kubernetes/partials/_capability_registry.html'
    )
    modal = read('app/templates/integrations/components/_record_detail_modal.html')

    for marker in (
        'data-kaori-capability-modal-v2',
        'data-kaori-capability-modal-v3',
        'data-kaori-capability-decision-summary',
        'data-kaori-capability-contract-snapshot',
        'data-kaori-capability-validation-evidence',
        'data-kaori-capability-operational-decision',
        'data-kaori-capability-governance-boundary',
        'data-kaori-capability-verification-command',
    ):
        assert marker in capability

    for label in (
        'Capability Decision',
        'Contract Snapshot',
        'Validation Evidence',
        'Operational Decision',
        'Operational Impact',
        'Recommended Action',
        'Governance Boundary',
        'Verification Command',
        'Copy Script',
    ):
        assert label in capability

    # The modal is a single reading flow, not a wall of nested evidence cards.
    assert 'lg:grid-cols-4' in capability
    assert 'lg:grid-cols-3' in capability
    assert 'lg:grid-cols-2' in capability
    assert 'data-kaori-capability-validation-scope' not in capability
    assert 'data-kaori-capability-operational-guidance' not in capability
    assert 'data-kaori-capability-verification-script' not in capability
    assert 'Independent Verification' not in capability
    assert 'Execution Context' not in capability

    assert "size='standard'" in capability
    assert 'technical_check.render(' not in capability
    assert 'Kubernetes API and RBAC Check' not in capability
    assert 'data-kaori-dialog-size="{{ size }}"' in modal
    assert "size='wide'" in modal
    assert 'max-w-5xl' in modal
    assert 'max-h-[calc(100dvh-1rem)]' in modal
