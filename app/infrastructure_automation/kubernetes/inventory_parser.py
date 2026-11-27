"""Offline exact Kubespray inventory parsing; no Ansible execution or SSH."""

from __future__ import annotations

import json
from importlib import import_module
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from app.infrastructure_automation.kubernetes.source_policy import ANSIBLE_CORE_VERSION


def compile_inventory(document: dict[str, Any]) -> dict[str, Any]:
    """Convert only the canonical inventory document, never caller extra-vars."""
    if (
        document.get('schema') != 'kaori.kubespray.inventory_config.v1'
        or document.get('execution_authorized') is not False
    ):
        raise ValueError('The canonical non-executable inventory document is required.')
    hosts = document['hosts']
    control = {h['name']: {} for h in hosts if h['role'] == 'control_plane'}
    workers = {h['name']: {} for h in hosts if h['role'] == 'worker'}
    if len(hosts) != 3 or len(control) != 1 or len(workers) != 2 or set(control) & set(workers):
        raise ValueError('The exact three-node pilot topology is required.')
    return {
        'all': {
            'hosts': {
                h['name']: {
                    'ansible_host': h['address'],
                    'ansible_port': h['ssh_port'],
                    'ip': h['address'],
                    'access_ip': h['address'],
                }
                for h in hosts
            },
            'vars': {
                'kube_pods_subnet': document['config']['pod_cidr'],
                'kube_service_addresses': document['config']['service_cidr'],
            },
            'children': {
                'kube_control_plane': {'hosts': control},
                'kube_node': {'hosts': workers},
                'etcd': {'hosts': control},
                'k8s_cluster': {'children': {'kube_control_plane': {}, 'kube_node': {}}},
            },
        }
    }


def verify_ansible_inventory(document: dict[str, Any]) -> None:
    """Use the fixed YAML parser directly; do not initialize dynamic inventory plugins."""
    if version('ansible-core') != ANSIBLE_CORE_VERSION:
        raise ValueError('The pinned Ansible Core version is required for inventory qualification.')
    from_data = compile_inventory(document)
    # Import only in the explicitly requested local parser path: web and
    # generic integration workers need not install the automation dependency.
    dataloader = import_module('ansible.parsing.dataloader')
    inventory_data = import_module('ansible.inventory.data')
    yaml_plugin = import_module('ansible.plugins.inventory.yaml')
    expected = from_data['all']
    with TemporaryDirectory(prefix='kaori-inventory-parser-') as directory:
        path = Path(directory) / 'inventory.yml'
        path.write_text(json.dumps(from_data), encoding='utf-8')
        path.chmod(0o600)
        inventory = inventory_data.InventoryData()
        yaml_plugin.InventoryModule().parse(inventory, dataloader.DataLoader(), str(path))
        actual = set(inventory.hosts)
        if actual != set(expected['hosts']):
            raise ValueError('Ansible inventory host identity did not match.')
        for name, fields in expected['hosts'].items():
            if any(inventory.hosts[name].vars.get(key) != value for key, value in fields.items()):
                raise ValueError('Ansible inventory endpoint fields did not match.')
        for name in ('kube_control_plane', 'kube_node', 'etcd', 'k8s_cluster'):
            group = inventory.groups.get(name)
            members = set(expected['hosts']) if name == 'k8s_cluster' else set(expected['children'][name]['hosts'])
            if group is None or {host.name for host in group.get_hosts()} != members:
                raise ValueError('Ansible inventory group membership did not match.')
        if any(inventory.groups['all'].vars.get(key) != value for key, value in expected['vars'].items()):
            raise ValueError('Ansible inventory network fields did not match.')
