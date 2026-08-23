from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def rules() -> dict[str, dict]:
    document = yaml.safe_load(read('app/definitions/catalogs/intelligence/rules.yaml'))
    return {row['rule_key']: row for row in document['rules']}


def test_risk_exception_is_definition_driven_and_visible_only_for_enabled_rules() -> None:
    catalog = rules()
    enabled = {
        key
        for key, row in catalog.items()
        if isinstance(row.get('risk_exception'), dict) and row['risk_exception'].get('enabled') is True
    }
    assert enabled == {
        'kubernetes.workload.missing_cpu_requests',
        'kubernetes.workload.missing_memory_requests',
        'kubernetes.workload.missing_memory_limits',
        'kubernetes.namespace.missing_quota',
        'kubernetes.tls_secret.expired',
        'kubernetes.tls_secret.expiring_soon',
        'object_storage.bucket.encryption_not_configured',
    }
    assert 'risk_exception' not in catalog['kubernetes.tls_secret.invalid']
    assert 'risk_exception' not in catalog['kubernetes.workload.latest_image_tag']

    detail = read('app/templates/intelligence/partials/_catalog_detail_content.html')
    service = read('app/intelligence/service.py')
    commands = read('app/intelligence/recommendation_alert_commands.py')
    assert '{% if item.risk_exception.enabled %}' in detail
    assert "if bool(exception_policy.get('enabled')):" in service
    assert "Accepted risk is not enabled for this Rule Catalog definition." in commands
    assert "The selected accepted-risk scope is not allowed by this Rule Catalog definition." in commands


def test_requested_exception_policies_are_iac_owned_in_rules_yaml() -> None:
    catalog = rules()
    for key in (
        'kubernetes.namespace.missing_quota',
        'kubernetes.workload.missing_cpu_requests',
        'kubernetes.workload.missing_memory_requests',
        'kubernetes.workload.missing_memory_limits',
        'kubernetes.tls_secret.expired',
        'kubernetes.tls_secret.expiring_soon',
        'object_storage.bucket.encryption_not_configured',
    ):
        policy = catalog[key]['risk_exception']
        assert policy['enabled'] is True
        assert policy['default_scope_mode'] in policy['allowed_scope_modes']
        assert policy['guidance']

    assert (
        catalog['object_storage.bucket.encryption_not_configured']['risk_exception']['default_scope_mode']
        == 'rule_asset'
    )
    assert catalog['kubernetes.namespace.missing_quota']['risk_exception']['default_scope_mode'] == 'finding_keys'
    assert 'kube-system' in catalog['kubernetes.namespace.missing_quota']['risk_exception']['guidance']
    assert 'vendor-managed TLS' in catalog['kubernetes.tls_secret.expired']['risk_exception']['guidance']
    assert catalog['kubernetes.tls_secret.expired']['alert_escalation']['grouping_mode'] == 'rule_asset_scope'
    assert catalog['kubernetes.tls_secret.expiring_soon']['alert_escalation']['grouping_mode'] == 'rule_asset_scope'


def test_tls_exceptions_target_specific_secrets_while_alerts_can_group_by_namespace() -> None:
    service = read('app/intelligence/service.py')
    exceptions = read('app/intelligence/rule_exceptions.py')

    assert "'rule_key': f'{source_rule_key}:{cluster_id}:{namespace}:{secret_name}'" in service
    assert "'secret_name': secret_name" in service
    assert "evidence.get('secret_name')" in exceptions
    assert "TLSCertificateInventory.status.in_(['expired', 'critical', 'warning', 'invalid'])" in service


def test_namespace_request_and_memory_limit_rules_have_concrete_inventory_findings() -> None:
    service = read('app/intelligence/service.py')
    collector = read('app/kubernetes/inventory/collectors/workloads.py')
    catalog = rules()

    assert '_build_namespace_quota_findings(rules)' in service
    assert '_build_workload_resource_governance_findings(rules)' in service
    assert "('kubernetes.workload.missing_cpu_requests', 'requests', 'cpu', 'CPU request')" in service
    assert "('kubernetes.workload.missing_memory_requests', 'requests', 'memory', 'memory request')" in service
    assert "('kubernetes.workload.missing_memory_limits', 'limits', 'memory', 'memory limit')" in service
    assert "'resources': {" in collector
    assert "'requests': {str(key): str(value)" in collector
    assert "'limits': {str(key): str(value)" in collector
    assert catalog['kubernetes.workload.missing_memory_limits']['status'] == 'available'
    assert catalog['kubernetes.workload.missing_memory_limits']['alert_escalation']['eligible'] is False


def test_rule_definition_row_uses_one_line_compact_iac_summary() -> None:
    records = read('app/templates/intelligence/partials/_catalog_records.html')
    service = read('app/intelligence/service.py')
    detail = read('app/templates/intelligence/partials/_catalog_detail_content.html')
    catalog = rules()

    assert 'mt-1 truncate text-xs leading-5 text-content-muted' in records
    assert 'line-clamp-2' not in records
    assert 'title="{{ item.table_summary or item.summary }}"' in records
    assert "item.get('catalog_summary') or item.get('summary')" in service
    assert 'limit=56' in service
    assert '{{ item.summary }}' in detail
    assert catalog['kubernetes.namespace.missing_quota']['catalog_summary'] == 'Flags namespaces without ResourceQuota.'
    assert (
        catalog['object_storage.bucket.encryption_not_configured']['catalog_summary']
        == 'Flags buckets without configured encryption.'
    )
