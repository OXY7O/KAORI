from __future__ import annotations

import json
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MATRIX_PATH = ROOT / 'docs' / 'architecture' / 'functional-capability-audit-matrix.json'

CANONICAL_BEHAVIOR_DIMENSIONS = {
    'normal_flow',
    'authorization',
    'validation_dependency',
    'persistence',
    'async_job',
    'export_publication',
    'failure_recovery',
}
VALID_BEHAVIOR_STATES = {'covered', 'bounded_gap', 'not_applicable'}
REQUIRED_EXECUTION_AUTHORITIES = {
    'scripts/quality_gate.sh',
    'scripts/verify_feature_test_coverage.py',
    'scripts/verify_test_domain_architecture.py',
    'tests/contracts',
    'tests/e2e',
}
RESOLVED_PRIMARY_FLOW_EVIDENCE = {
    ('intelligence', 'recommendations'): 'tests/contracts/intelligence/test_recommendations_audit_20260815_contract.py',
    ('intelligence', 'alert_intelligence'): 'tests/contracts/intelligence/test_alert_operations_lifecycle_contract.py',
    ('intelligence', 'rule_catalog'): 'tests/contracts/intelligence/test_rule_catalog_review_20260815_contract.py',
    (
        'notifications',
        'inbox',
    ): 'tests/contracts/platform_operations/notifications/test_activity_notification_center_contract.py',
    (
        'notifications',
        'activity',
    ): 'tests/contracts/platform_operations/notifications/test_activity_notification_center_contract.py',
}
AUTHENTICATION_SECONDARY_EVIDENCE = {
    ('login', 'authorization'): 'tests/security/access/authentication/test_authentication_security.py',
    ('login', 'validation_dependency'): 'tests/access/authentication/test_login_characterization.py',
    ('login', 'failure_recovery'): 'tests/ui/test_runtime_state_responsiveness.py',
    ('logout', 'authorization'): 'tests/security/access/authentication/test_authentication_security.py',
    ('session', 'validation_dependency'): 'tests/unit/access/authentication/test_auth_session_policy.py',
    ('readiness', 'failure_recovery'): 'tests/ui/test_runtime_state_responsiveness.py',
}
NOTIFICATION_SECONDARY_EVIDENCE = {
    (
        'notification_center',
        'authorization',
    ): 'tests/contracts/platform_operations/notifications/test_notification_center_final_lock_contract.py',
    (
        'notification_center',
        'validation_dependency',
    ): 'tests/contracts/platform_operations/notifications/test_notification_center_final_lock_contract.py',
    (
        'notification_center',
        'persistence',
    ): 'tests/contracts/platform_operations/notifications/test_notification_center_final_lock_contract.py',
    (
        'notification_center',
        'failure_recovery',
    ): 'tests/contracts/platform_operations/notifications/test_activity_notification_center_contract.py',
    (
        'inbox',
        'authorization',
    ): 'tests/contracts/platform_operations/notifications/test_notification_center_final_lock_contract.py',
    (
        'inbox',
        'persistence',
    ): 'tests/contracts/platform_operations/notifications/test_notification_center_final_lock_contract.py',
    (
        'activity',
        'authorization',
    ): 'tests/contracts/platform_operations/notifications/test_notification_center_final_lock_contract.py',
    (
        'read_state_refresh',
        'persistence',
    ): 'tests/contracts/platform_operations/notifications/test_activity_notification_center_contract.py',
    (
        'read_state_refresh',
        'failure_recovery',
    ): 'tests/contracts/platform_operations/notifications/test_activity_notification_center_contract.py',
}
KUBERNETES_OPERATIONS_SECONDARY_EVIDENCE = {
    ('configmap_management', 'authorization'): 'tests/kubernetes/operations/test_route_authorization_characterization.py',
    ('configmap_management', 'validation_dependency'): 'tests/kubernetes/operations/test_configmap_validation_contract.py',
    ('configmap_management', 'persistence'): 'tests/kubernetes/operations/test_configmap_mutation_workflow.py',
    ('configmap_management', 'failure_recovery'): 'tests/kubernetes/operations/test_configmap_mutation_workflow.py',
    ('secret_management', 'authorization'): 'tests/kubernetes/operations/test_route_authorization_characterization.py',
    ('secret_management', 'validation_dependency'): 'tests/kubernetes/operations/test_secret_mutation_workflow.py',
    ('secret_management', 'persistence'): 'tests/kubernetes/operations/test_secret_mutation_workflow.py',
    ('secret_management', 'failure_recovery'): 'tests/kubernetes/operations/test_secret_mutation_workflow.py',
}


def _assert_paths_exist(paths: list[str], *, context: str) -> None:
    assert paths, f'{context}: evidence paths must not be empty'
    missing = [path for path in paths if not (ROOT / path).exists()]
    assert not missing, f'{context}: missing evidence paths: {missing}'


def test_functional_capability_audit_matrix_is_fail_closed() -> None:
    assert MATRIX_PATH.exists(), (
        'Functional capability audit matrix is missing; #225 requires every active release surface '
        'and capability behavior to have executable evidence or explicit disposition.'
    )

    payload = json.loads(MATRIX_PATH.read_text(encoding='utf-8'))
    assert payload['version'] == 1
    assert payload['phase'] == 'inventory'
    assert payload['source_registry'] == 'scripts/release_surface_registry.py'
    assert set(payload['execution_authorities']) == REQUIRED_EXECUTION_AUTHORITIES
    _assert_paths_exist(payload['execution_authorities'], context='execution authorities')
    assert set(payload['behavior_dimensions']) == CANONICAL_BEHAVIOR_DIMENSIONS

    registry = runpy.run_path(str(ROOT / 'scripts' / 'release_surface_registry.py'))
    surfaces = {surface.key: surface for surface in registry['SURFACES']}
    matrix = payload['surfaces']
    assert set(matrix) == set(surfaces), (
        f'functional audit coverage must exactly match release authority; '
        f'missing={sorted(set(surfaces) - set(matrix))}, extra={sorted(set(matrix) - set(surfaces))}'
    )

    for key, surface in surfaces.items():
        entry = matrix[key]
        expected_classification = 'system_non_ui' if key == 'health' else 'active_ui'
        assert entry['classification'] == expected_classification
        assert entry['title'] == surface.title
        assert entry['entrypoints'] == list(surface.navigation_endpoints)

        release_evidence = entry['release_evidence']
        assert set(surface.verifiers).issubset(release_evidence['verifiers'])
        assert set(surface.contract_paths).issubset(release_evidence['contracts'])
        if release_evidence['verifiers']:
            _assert_paths_exist(release_evidence['verifiers'], context=f'{key} release verifiers')
        _assert_paths_exist(release_evidence['contracts'], context=f'{key} release contracts')

        capabilities = entry['capabilities']
        assert capabilities, f'{key}: at least one capability is required'
        for capability_key, capability in capabilities.items():
            assert capability['state'] == 'active', f'{key}.{capability_key}: capability must be active'
            behaviors = capability['behaviors']
            assert behaviors, f'{key}.{capability_key}: at least one behavior is required'
            assert set(behaviors).issubset(CANONICAL_BEHAVIOR_DIMENSIONS)

            for behavior_key, behavior in behaviors.items():
                assert behavior['state'] in VALID_BEHAVIOR_STATES
                state = behavior['state']
                if state == 'covered':
                    evidence = behavior['evidence']
                    _assert_paths_exist(evidence, context=f'{key}.{capability_key}.{behavior_key}')
                    assert not any(path.startswith('tests/debug') for path in evidence)
                    assert 'reason' not in behavior
                    assert 'tracking_issue' not in behavior
                elif state == 'bounded_gap':
                    assert behavior['reason'].strip()
                    assert isinstance(behavior['tracking_issue'], int) and behavior['tracking_issue'] > 0
                    assert not behavior.get('evidence')
                else:
                    assert behavior['reason'].strip()
                    assert not behavior.get('evidence')
                    assert 'tracking_issue' not in behavior


def test_resolved_primary_flow_findings_bind_narrow_executable_evidence() -> None:
    payload = json.loads(MATRIX_PATH.read_text(encoding='utf-8'))

    for (surface_key, capability_key), evidence_path in RESOLVED_PRIMARY_FLOW_EVIDENCE.items():
        behavior = payload['surfaces'][surface_key]['capabilities'][capability_key]['behaviors']['normal_flow']
        assert behavior['state'] == 'covered', f'{surface_key}.{capability_key}.normal_flow must be covered'
        assert behavior['evidence'] == [evidence_path]
        _assert_paths_exist(behavior['evidence'], context=f'{surface_key}.{capability_key}.normal_flow')


def test_authentication_secondary_behaviors_bind_narrow_executable_evidence() -> None:
    payload = json.loads(MATRIX_PATH.read_text(encoding='utf-8'))
    capabilities = payload['surfaces']['authentication']['capabilities']

    for (capability_key, behavior_key), evidence_path in AUTHENTICATION_SECONDARY_EVIDENCE.items():
        behavior = capabilities[capability_key]['behaviors'][behavior_key]
        assert behavior['state'] == 'covered', f'authentication.{capability_key}.{behavior_key} must be covered'
        assert behavior['evidence'] == [evidence_path]
        _assert_paths_exist(
            behavior['evidence'],
            context=f'authentication.{capability_key}.{behavior_key}',
        )


def test_notification_secondary_behaviors_bind_narrow_executable_evidence() -> None:
    payload = json.loads(MATRIX_PATH.read_text(encoding='utf-8'))
    capabilities = payload['surfaces']['notifications']['capabilities']

    for (capability_key, behavior_key), evidence_path in NOTIFICATION_SECONDARY_EVIDENCE.items():
        behavior = capabilities[capability_key]['behaviors'][behavior_key]
        assert behavior['state'] == 'covered', f'notifications.{capability_key}.{behavior_key} must be covered'
        assert behavior['evidence'] == [evidence_path]
        _assert_paths_exist(
            behavior['evidence'],
            context=f'notifications.{capability_key}.{behavior_key}',
        )


def test_kubernetes_operations_secondary_behaviors_bind_narrow_executable_evidence() -> None:
    payload = json.loads(MATRIX_PATH.read_text(encoding='utf-8'))
    capabilities = payload['surfaces']['kubernetes_operations']['capabilities']

    for (capability_key, behavior_key), evidence_path in KUBERNETES_OPERATIONS_SECONDARY_EVIDENCE.items():
        behavior = capabilities[capability_key]['behaviors'][behavior_key]
        assert behavior['state'] == 'covered', f'kubernetes_operations.{capability_key}.{behavior_key} must be covered'
        assert behavior['evidence'] == [evidence_path]
        _assert_paths_exist(
            behavior['evidence'],
            context=f'kubernetes_operations.{capability_key}.{behavior_key}',
        )
