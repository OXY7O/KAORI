from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3] / 'app/templates/kubernetes/inventory'

TABLE_TERMS = {
    'overview': ('Last Snapshot', 'Inventory Signals'),
    'nodes': ('Readiness', 'Capacity'),
    'namespaces': ('Resource Controls', 'Security Context', 'Pod Security Admission (PSA)'),
    'workloads': ('Managed Pods', 'Update Strategy'),
    'pods': ('Runtime State', 'Ownership & Activity'),
    'services': ('Access Model', 'Backend Registration'),
    'ingresses': ('TLS References', 'Routing'),
    'storage': ('Provisioning', 'Binding & Lifecycle'),
    'configuration': ('Key Index & Mutation', 'Current Pod References'),
}


def _table_source(resource: str) -> str:
    path = (
        ROOT / 'overview/partials/_resources_by_cluster_content.html'
        if resource == 'overview'
        else ROOT / resource / 'partials/_table_content.html'
    )
    return path.read_text(encoding='utf-8')


def _title_source(resource: str) -> str:
    path = (
        ROOT / 'overview/partials/_resources_by_cluster.html'
        if resource == 'overview'
        else ROOT / resource / 'partials/_table_card.html'
    )
    return path.read_text(encoding='utf-8')


def test_kubernetes_inventory_help_is_on_table_titles_not_column_headers() -> None:
    ids = []
    for resource, terms in TABLE_TERMS.items():
        table = _table_source(resource)
        title = _title_source(resource)
        assert 'info_tip.render(' not in table
        assert 'components/info_tip.html' not in table
        assert 'components/info_tip.html' in title
        assert title.count('info_tip.render(') == 1
        assert 'items=[' in title
        for term in terms:
            assert term in title
        assert '<thead' in table and '</thead>' in table
        assert '<tbody' in table and '</tbody>' in table
        ids += re.findall(r"info_tip.render\('(k8s-inventory-[^']+)'", title)

    assert len(ids) == 9 and len(set(ids)) == len(ids)
    assert "'k8s-inventory-overview-title'" in _title_source('overview')
    assert "'k8s-inventory-nodes-title'" in _title_source('nodes')


def test_namespace_psa_remains_a_plain_column_value_with_title_guidance() -> None:
    table = _table_source('namespaces')
    title = _title_source('namespaces')
    assert '<span class="text-content-muted">PSA Enforce</span>' in table
    assert 'k8s-namespace-psa-enforce-' not in table
    assert 'Pod Security Admission (PSA)' in title
    assert 'Privileged, Baseline, and Restricted' in title
    assert 'does not prove the namespace is secure' in title


def test_topology_and_tls_help_are_at_the_respective_table_titles() -> None:
    topology = (ROOT / 'topology/partials/_workspace.html').read_text(encoding='utf-8')
    tls = (
        ROOT.parent / 'governance/tls_certificates/partials/_table.html'
    ).read_text(encoding='utf-8')
    for template in (topology, tls):
        assert template.count('info_tip.render(') == 1
        header = template.split('<thead', 1)[1].split('</thead>', 1)[0]
        assert 'info_tip.render(' not in header

    assert '<h3 class="text-sm font-semibold text-content-primary">Resource List</h3>' in topology
    assert "'k8s-inventory-topology-title'" in topology
    assert 'missing or filtered evidence' in topology
    assert "title_extra=info_tip.render('k8s-inventory-tls-title'" in tls
    assert 'not a live handshake test' in tls


def test_shared_info_tip_supports_pointer_keyboard_touch_and_htmx() -> None:
    shared = (ROOT.parents[1] / 'components/info_tip.html').read_text(encoding='utf-8')
    js = (ROOT.parents[2] / 'static/js/info_tips.js').read_text(encoding='utf-8')
    assert 'data-kaori-info-tip-trigger' in shared
    assert 'aria-describedby=' in shared
    assert 'role="tooltip"' in shared
    for token in ("'pointerover'", "'focusin'", "'click'", "'keydown'", "'htmx:beforeSwap'"):
        assert token in js
