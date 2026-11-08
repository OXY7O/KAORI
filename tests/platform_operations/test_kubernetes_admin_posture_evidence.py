"""Configured Kubernetes Reveal controls never imply live RBAC/namespace proof."""

from app.platform_operations.kubernetes.presentation import _administration_posture


def _status(*, clusters=1, ready=1, enabled=1, eligible=1, gate=True):
    return _administration_posture(
        cluster_count=clusters,
        ready_cluster_count=ready,
        enabled_namespace_count=enabled,
        eligible_policy_count=eligible,
        global_reveal_enabled=gate,
    )[0]


def test_admin_posture_requires_policy_on_canonical_ready_cluster():
    assert _status(clusters=0, ready=0, enabled=0) == 'Setup Required'
    assert _status(gate=False) == 'Global Gate Disabled'
    assert _status(ready=0) == 'Readiness Review'
    assert _status(clusters=2, ready=1) == 'Partial Readiness'
    assert _status(enabled=0, eligible=0) == 'Policy Required'
    assert _status(eligible=0) == 'Policy Scope Review'
    assert _status(eligible=1) == 'Verification Required'


def test_configured_policy_does_not_claim_live_operational_evidence():
    assert _status(eligible=1) != 'Operational'


def test_admin_overview_projects_only_real_controls_and_committed_evidence(monkeypatch):
    from flask import Flask

    from app.platform_operations.kubernetes import presentation

    counts = {
        'cluster_count': 2,
        'ready_cluster_count': 1,
        'enabled_namespace_count': 2,
        'eligible_policy_count': 1,
    }
    monkeypatch.setattr(presentation, 'administration_counts', lambda: counts)
    app = Flask(__name__)
    app.config['KUBERNETES_SECRET_REVEAL_ENABLED'] = True

    with app.app_context():
        summary = presentation.build_kubernetes_administration_summary()

    assert summary['administration_control_count'] == len(summary['administration_controls']) == 1
    control = summary['administration_controls'][0]
    assert control['key'] == 'secret-reveal'
    assert control['workspace_tab'] == 'secret-reveal'
    assert control['status_label'] == summary['administration_status_label'] == 'Partial Readiness'
    assert control['status_tone'] == summary['administration_status_tone'] == 'warning'
    assert control['metrics'][0][2] == '1 / 2'
    assert control['metrics'][1][2] == '1 / 2'
    assert summary['enabled_namespace_count'] == 2
    assert 'runtime authorization' in control['evidence_label']


def test_admin_overview_retains_no_live_proof_when_all_configuration_exists(monkeypatch):
    from flask import Flask

    from app.platform_operations.kubernetes import presentation

    monkeypatch.setattr(
        presentation,
        'administration_counts',
        lambda: {
            'cluster_count': 1,
            'ready_cluster_count': 1,
            'enabled_namespace_count': 1,
            'eligible_policy_count': 1,
        },
    )
    app = Flask(__name__)
    app.config['KUBERNETES_SECRET_REVEAL_ENABLED'] = True
    with app.app_context():
        summary = presentation.build_kubernetes_administration_summary()

    assert summary['administration_status_label'] == 'Verification Required'
    assert summary['administration_controls'][0]['status_label'] == 'Verification Required'
    assert summary['administration_controls'][0]['metrics'][1][2] == '1 / 1'
