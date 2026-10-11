from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3] / 'app/templates/kubernetes/inventory'


TABLE_TIPS = {
    'overview': ('Last Snapshot', 'Inventory Signals'),
    'nodes': ('Readiness', 'Capacity'),
    'namespaces': ('Resource Controls', 'Security Context'),
    'workloads': ('Managed Pods', 'Update Strategy'),
    'pods': ('Runtime State', 'Ownership & Activity'),
    'services': ('Access Model', 'Backend Registration'),
    'ingresses': ('TLS References', 'Routing'),
    'storage': ('Provisioning', 'Binding & Lifecycle'),
    'configuration': ('Key Index & Mutation', 'Current Pod References'),
}


def _table_source(resource: str) -> str:
    rel = (
        'overview/partials/_resources_by_cluster_content.html'
        if resource == 'overview'
        else f'{resource}/partials/_table_content.html'
    )
    return (ROOT / rel).read_text(encoding='utf-8')


def test_every_kubernetes_inventory_table_explains_technical_columns() -> None:
    ids: list[str] = []
    for resource, labels in TABLE_TIPS.items():
        template = _table_source(resource)
        assert '{% import "components/info_tip.html" as info_tip %}' in template
        assert template.count('info_tip.render(') == len(labels) + (resource == 'namespaces')
        assert '<thead' in template and '</thead>' in template
        assert '<tbody' in template and '</tbody>' in template
        for label in labels:
            assert f'>{label} {{{{ info_tip.render(' in template
        ids.extend(re.findall(r"info_tip.render\('(k8s-inventory-[^']+)'", template))

    assert len(ids) == len(set(ids)), 'Header tooltip IDs must be globally distinct.'


def test_namespace_psa_explains_enforcement_without_compliance_assumptions() -> None:
    source = _table_source('namespaces')
    assert 'PSA Enforce {{ info_tip.render(' in source
    assert "'k8s-namespace-psa-enforce-' ~ namespace.id" in source
    assert "'Pod Security Admission (PSA)'" in source
    assert 'Privileged, Baseline, and Restricted' in source
    assert 'does not prove the namespace is secure' in source


def test_topology_and_tls_inventory_tables_explain_technical_evidence() -> None:
    templates = ROOT.parents[0]
    topology = (ROOT / 'topology/partials/_workspace.html').read_text(encoding='utf-8')
    tls = (
        templates / 'governance/tls_certificates/partials/_table.html'
    ).read_text(encoding='utf-8')
    for source in (topology, tls):
        assert '{% import "components/info_tip.html" as info_tip %}' in source
    assert 'k8s-inventory-topology-status' in topology
    assert 'k8s-inventory-topology-relationships' in topology
    assert 'missing or filtered evidence' in topology
    assert 'k8s-inventory-tls-validity' in tls
    assert 'k8s-inventory-tls-host-coverage' in tls
    assert 'k8s-inventory-tls-ingress-usage' in tls
    assert 'not a live handshake test' in tls
    assert 'not proof of successful TLS termination' in tls


def test_shared_info_tip_supports_pointer_keyboard_touch_and_htmx() -> None:
    shared = (ROOT.parents[1] / 'components/info_tip.html').read_text(encoding='utf-8')
    js = (ROOT.parents[2] / 'static/js/info_tips.js').read_text(encoding='utf-8')
    assert 'data-kaori-info-tip-trigger' in shared
    assert 'aria-describedby=' in shared
    assert 'role="tooltip"' in shared
    for token in ("'pointerover'", "'focusin'", "'click'", "'keydown'", "'htmx:beforeSwap'"):
        assert token in js
