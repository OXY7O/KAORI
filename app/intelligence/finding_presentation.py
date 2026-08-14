from __future__ import annotations

from typing import Any


def _clean(value: Any) -> str:
    return str(value or '').strip()


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def compact_recommendation_summary(value: Any, *, limit: int = 180) -> str:
    text = ' '.join(str(value or '').split())
    if not text:
        return 'Evidence-backed operational guidance is available in View Details.'
    for marker in (' Examples:', ' Example:', ' Examples include:'):
        if marker in text:
            text = text.split(marker, 1)[0].rstrip(' .') + '.'
            break
    if len(text) <= limit:
        return text
    first_sentence = text.split('. ', 1)[0].strip()
    if 48 <= len(first_sentence) <= limit:
        return first_sentence.rstrip('.') + '.'
    words: list[str] = []
    length = 0
    for word in text.split():
        projected = length + len(word) + (1 if words else 0)
        if projected > limit:
            break
        words.append(word)
        length = projected
    return ' '.join(words).rstrip(' ,;:-') + '.'


def finding_scope_details(finding: dict[str, Any]) -> tuple[str, str]:
    evidence = _mapping(finding.get('evidence'))
    source_label = str(finding.get('source_kind_label') or 'Resource')
    if _clean(finding.get('domain')) == 'object_storage':
        system_name = _clean(evidence.get('system_name'))
        bucket_name = _clean(evidence.get('bucket_name'))
        provider_label = _clean(evidence.get('provider_label')) or 'Object Storage'
        if bucket_name:
            supporting = ' · '.join(value for value in (system_name, provider_label) if value)
            return bucket_name, supporting or source_label
        if system_name:
            return system_name, f'{source_label} · {provider_label}'
        return 'Object Storage Scope', source_label

    namespace = _clean(evidence.get('namespace'))
    affected_count = evidence.get('affected_pods') or evidence.get('affected_count') or evidence.get('count')
    title = namespace if namespace and namespace != 'cluster scope' else 'Cluster Scope'
    supporting = f'{affected_count} {source_label} item(s)' if affected_count else source_label
    return title, supporting


def format_affected_summary(item: dict[str, Any]) -> str:
    evidence = _mapping(item.get('evidence'))
    source_kind = str(item.get('source_kind_label') or item.get('source_kind') or 'Resource')
    if _clean(item.get('domain')) == 'object_storage':
        system_name = _clean(evidence.get('system_name')) or 'Object Storage system'
        bucket_name = _clean(evidence.get('bucket_name'))
        provider_label = _clean(evidence.get('provider_label')) or 'Object Storage'
        resource = f'{source_kind} {bucket_name}' if bucket_name else f'{source_kind} {system_name}'
        location = f' on {system_name}' if bucket_name else ''
        return f'{resource}{location} ({provider_label}) matched this recommendation rule.'

    affected_count = evidence.get('affected_pods') or evidence.get('affected_count') or evidence.get('count')
    namespace = _clean(evidence.get('namespace'))
    cluster_id = _clean(evidence.get('cluster_id'))
    if affected_count:
        locations = []
        if namespace and namespace != 'cluster scope':
            locations.append(f'namespace {namespace}')
        if cluster_id:
            locations.append(f'cluster {cluster_id}')
        location = ' in ' + ' / '.join(locations) if locations else ''
        return f'{affected_count} {source_kind.lower()} item(s){location} matched this recommendation rule.'
    domain = str(item.get('domain_label') or item.get('domain') or 'asset')
    return f'{source_kind} item in {domain} scope matched this recommendation rule.'


def _base_affected_items(item: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {'label': 'Asset', 'value': str(item.get('domain_label') or item.get('domain') or '-')},
        {'label': 'Resource', 'value': str(item.get('source_kind_label') or item.get('source_kind') or 'Resource')},
    ]


def _object_storage_affected_items(item: dict[str, Any]) -> list[dict[str, str]]:
    evidence = _mapping(item.get('evidence'))
    output = _base_affected_items(item)
    fields = (
        ('Provider', 'provider_label'),
        ('System', 'system_name'),
        ('Bucket', 'bucket_name'),
        ('Usage', 'usage_display'),
        ('Quota', 'quota_display'),
        ('Quota Utilization', 'quota_utilization_display'),
        ('Exposure', 'exposure_display'),
        ('Encryption', 'encryption_display'),
        ('Forecast Window', 'forecast_window'),
        ('Capacity ETA', 'capacity_eta_display'),
        ('Growth / Day', 'growth_per_day_display'),
    )
    for label, key in fields:
        value = _clean(evidence.get(key))
        if value and value != 'N/A':
            output.append({'label': label, 'value': value})
    return output[:8]


def _kubernetes_affected_items(item: dict[str, Any]) -> list[dict[str, str]]:
    evidence = _mapping(item.get('evidence'))
    output = _base_affected_items(item)
    fields = (
        ('Cluster', 'cluster_id'),
        ('Namespace', 'namespace'),
        ('Phase', 'phase'),
        ('Status', 'status'),
        ('TLS Secret', 'secret_name'),
        ('TLS Secret', 'example_secret'),
        ('Issuer', 'issuer'),
    )
    for label, key in fields:
        value = _clean(evidence.get(key))
        if value:
            output.append({'label': label, 'value': value})
    count = evidence.get('affected_pods') or evidence.get('affected_count') or evidence.get('count')
    if count:
        output.append({'label': 'Affected', 'value': str(count)})
    days_remaining = evidence.get('days_remaining') or evidence.get('min_days_remaining')
    if days_remaining is not None:
        output.append({'label': 'Days Remaining', 'value': str(days_remaining)})
    return output[:8]


def build_affected_items(item: dict[str, Any]) -> list[dict[str, str]]:
    if _clean(item.get('domain')) == 'object_storage':
        return _object_storage_affected_items(item)
    return _kubernetes_affected_items(item)


def build_fix_steps(item: dict[str, Any]) -> list[str]:
    source_kind = _clean(item.get('source_kind'))
    category = _clean(item.get('category'))
    action = _clean(item.get('recommended_action'))
    if source_kind == 'object_storage_system':
        steps = [
            'Review the committed Object Storage forecast finding, provider, evidence window, growth rate, and projected capacity boundary.',
            'Open Object Storage Analytics > Forecast and validate the current worker snapshot, usage history, top consumers, and physical headroom before changing capacity.',
            action or 'Apply the approved capacity expansion, lifecycle, retention, or demand-reduction change.',
            'Refresh the Object Storage forecast worker and confirm the projected exhaustion boundary no longer matches this recommendation rule.',
        ]
    elif source_kind == 'object_storage_bucket':
        steps = [
            'Review the committed Object Storage finding, provider, system, bucket ownership, and the captured quota or governance evidence.',
            'Open Object Storage Inventory and the related Object Storage Analytics workspace to validate the latest committed configuration and current operational context.',
            action or 'Apply the approved bucket quota, access, encryption, lifecycle, or data-retention correction through the provider change path.',
            'Resync Object Storage inventory and confirm the committed evidence no longer matches this recommendation rule.',
        ]
    elif source_kind == 'pod':
        steps = [
            'Review the committed Pod finding, affected namespace, workload ownership, restart count, phase, and related inventory evidence.',
            'Open Pod Inventory or the related workload page and validate live events, image pull state, probes, scheduling constraints, restarts, and node placement.',
            'Apply the approved manifest or configuration correction, then restart or safely roll out the affected workload.',
            'Resync Pod inventory and confirm the workload is healthy and this recommendation no longer appears.',
        ]
    elif source_kind == 'node':
        steps = [
            'Review the committed Node finding, pressure conditions, schedulability, capacity, and affected workload context.',
            'Open Node Inventory and validate kubelet, container runtime, disk pressure, memory pressure, network reachability, and recent node events.',
            'Recover the node or cordon and drain it safely before applying the required infrastructure correction.',
            'Resync Node inventory and confirm healthy conditions, schedulable capacity, and recommendation clearance.',
        ]
    elif source_kind == 'persistent_volume':
        steps = [
            'Review the committed PVC/PV finding, namespace, storage class, binding state, capacity, and affected workload dependency.',
            'Open Storage Analysis and validate PVC/PV events, provisioner health, access modes, quota, and current attachment or mount state.',
            'Correct binding or provisioning, expand capacity, or remove the blocking storage condition using the approved change path.',
            'Resync storage inventory and confirm the claim is healthy and this recommendation no longer appears.',
        ]
    elif source_kind == 'tls_secret':
        steps = [
            'Review the committed TLS Secret finding, issuer, SAN coverage, expiry, namespace ownership, and Ingress usage mapping.',
            'Open Kubernetes Governance > TLS Secret and validate the replacement certificate, private key match, selected existing Secret targets, and HTMX preview.',
            'Upload the renewed tls.crt and tls.key, then update only the approved existing Kubernetes TLS Secret targets.',
            'Resync TLS inventory, validate the affected Ingress endpoint certificate chain, and confirm the recommendation is cleared.',
        ]
    elif source_kind == 'workload':
        steps = [
            'Review the committed workload finding, controller type, namespace, rollout state, replica health, and affected container context.',
            'Open Workload Analysis and validate requests, limits, rollout conditions, images, probes, events, and namespace policy constraints.',
            'Patch the approved workload manifest and complete a controlled rollout of the affected workload.',
            'Resync workload inventory and confirm healthy rollout state and recommendation clearance.',
        ]
    elif category == 'capacity':
        steps = [
            'Review the committed capacity finding, selected scope, utilization trend, saturation point, and top-consumer evidence.',
            'Validate the current Prometheus source, time range, workload demand, quotas, limits, and infrastructure allocation before changing capacity.',
            'Apply the approved capacity, quota, limit, or infrastructure allocation change.',
            'Refresh analytics and generated report context, then confirm the risk state and recommendation are cleared.',
        ]
    else:
        steps = [
            'Review the committed recommendation evidence, affected scope, resource identifiers, and rule condition.',
            'Open the related inventory, analytics, governance, or integration page and validate the current live resource state and ownership.',
            action or 'Apply the recommended remediation through the approved operational change path.',
            'Resync the relevant KAORI data source and confirm the condition is resolved and the recommendation no longer appears.',
        ]
    return list(dict.fromkeys(step.strip() for step in steps if step.strip()))[:4]
