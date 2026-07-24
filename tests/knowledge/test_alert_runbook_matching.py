from types import SimpleNamespace

import pytest

from app.knowledge.matching import RunbookMatchError, match_alert_to_runbook


def _binding(key='pod-restart', priority=10, required=None):
    runbook = SimpleNamespace(runbook_key='kubernetes.pod.restart')
    revision = SimpleNamespace(
        publication_status='published', public_id='rev-1', version='1.0.0', content_hash='a' * 64,
        action_key='kubernetes.pod.restart', resolver_key='kubernetes.pod.restart',
        approval_policy='needs_approval', required_evidence_json=['cluster_id', 'namespace', 'pod_name'], runbook=runbook,
    )
    return SimpleNamespace(
        binding_key=key, lifecycle_status='active', priority=priority, rule_key='kubernetes.pod.unhealthy_phase',
        alertname='KubePodNotReady', cluster_id=None, namespace=None,
        required_labels_json=required or {'severity': 'critical'},
        evidence_mapping_json={'pod_name': 'pod'}, revision=revision,
    )


def _alert():
    return {'rule_key': 'kubernetes.pod.unhealthy_phase', 'fingerprint': 'fp-1', 'labels': {
        'alertname': 'KubePodNotReady', 'severity': 'critical', 'cluster_id': 'cluster-1',
        'namespace': 'payments', 'pod': 'api-123',
    }}


def test_match_produces_non_executable_candidate_with_locked_revision():
    candidate = match_alert_to_runbook(_alert(), [_binding()])
    assert candidate.executable is False
    assert candidate.runbook_revision_id == 'rev-1'
    assert candidate.evidence['pod_name'] == 'api-123'
    with pytest.raises(TypeError):
        candidate.evidence['pod_name'] = 'changed'


def test_equal_priority_matches_are_rejected_as_ambiguous():
    with pytest.raises(RunbookMatchError, match='Ambiguous'):
        match_alert_to_runbook(_alert(), [_binding('a'), _binding('b')])


def test_missing_required_evidence_is_rejected():
    binding = _binding()
    binding.evidence_mapping_json = {}
    with pytest.raises(RunbookMatchError, match='pod_name'):
        match_alert_to_runbook(_alert(), [binding])
