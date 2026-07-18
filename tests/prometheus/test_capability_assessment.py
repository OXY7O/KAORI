from app.prometheus.capabilities import definition


def test_storage_identity_capability_has_actionable_remediation():
    item = definition('node_filesystem_identity')
    assert item is not None
    assert 'node' in item.recommendation
    assert item.source_owner
    assert item.validation_query


def test_pvc_capability_names_expected_metrics():
    item = definition('pvc_usage')
    assert item is not None
    assert 'kubelet_volume_stats_used_bytes' in item.expected_signals
