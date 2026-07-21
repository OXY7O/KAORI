from app.integrations.prometheus.query_profiles.audit import PromQLProfileAuditor


class FakeClient:
    def query(self, expression):
        if 'node_filesystem_' in expression:
            metric = {'node': 'worker-01', 'mountpoint': '/var', 'fstype': 'ext4'}
            return {'status': 'success', 'data': {'result': [{'metric': metric, 'value': [1, '100']}]}}
        if 'kubelet_volume_stats_used_bytes' in expression:
            metric = {'namespace': 'default', 'persistentvolumeclaim': 'data'}
            return {'status': 'success', 'data': {'result': [{'metric': metric, 'value': [1, '10']}]}}
        return {'status': 'success', 'data': {'result': []}}


def test_filesystem_contract_uses_exact_query_result_not_series_schema():
    auditor = PromQLProfileAuditor(FakeClient())
    result = auditor._filesystem_contract('node_filesystem_size_bytes')
    assert result['passed'] is True
    assert result['nodes'] == {'worker-01'}
    assert result['series_count'] == 1


def test_query_contract_reports_usable_pvc_series():
    auditor = PromQLProfileAuditor(FakeClient())
    result = auditor._query_contract(
        'sum by (namespace, persistentvolumeclaim) (kubelet_volume_stats_used_bytes)',
        required_labels={'namespace', 'persistentvolumeclaim'},
    )
    assert result['passed'] is True
    assert result['series_count'] == 1
