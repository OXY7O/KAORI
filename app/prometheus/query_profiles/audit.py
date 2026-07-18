from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from app.prometheus.capabilities import definition as capability_definition
from app.prometheus.exceptions import PrometheusError
from app.prometheus.query_profiles import PROFILE_KEY, list_queries
from app.prometheus.query_profiles.feature_contracts import evaluate_feature_contracts


@dataclass(frozen=True)
class QueryCheckResult:
    key: str
    status: str
    message: str
    missing_metrics: tuple[str, ...] = ()
    missing_labels: tuple[str, ...] = ()
    deprecated: bool = False
    replacement_key: str | None = None


class PromQLProfileAuditor:
    """Validate the versioned PromQL profile against one configured endpoint."""

    def __init__(self, client: Any) -> None:
        self.client = client

    def audit(self, *, execute_queries: bool = True) -> dict[str, Any]:
        definitions = list_queries()
        available_metrics = self._available_metric_names()
        namespaces = self.client.label_values('namespace').get('data') or []
        sample_namespace = namespaces[0] if namespaces else 'default'
        label_requirements = {
            metric
            for definition in definitions
            for metric, _labels in definition.required_labels
            if metric in available_metrics
        }
        metric_label_cache = self._labels_for_metrics(label_requirements)
        results: list[QueryCheckResult] = []

        for definition in definitions:
            missing_metrics = tuple(
                metric for metric in definition.required_metrics if metric not in available_metrics
            )
            missing_labels: list[str] = []
            if not missing_metrics and definition.required_labels:
                for metric, required_labels in definition.required_labels:
                    labels = metric_label_cache.get(metric, set())
                    missing_labels.extend(
                        f'{metric}.{label}' for label in required_labels if label not in labels
                    )

            status = 'ready'
            message = 'Required metrics and labels are available.'
            if missing_metrics:
                status = 'blocked'
                message = 'Required metrics are unavailable.'
            elif missing_labels:
                status = 'blocked'
                message = 'Required label schema is unavailable.'
            elif definition.is_deprecated:
                status = 'deprecated'
                message = 'Query is deprecated and must use its registered replacement.'
            elif execute_queries:
                expression = definition.expression.replace('$namespace', _escape_label_value(sample_namespace))
                response = self.client.query(expression)
                if response.get('status') != 'success':
                    status = 'blocked'
                    message = 'Prometheus rejected the query.'

            results.append(QueryCheckResult(
                key=definition.key,
                status=status,
                message=message,
                missing_metrics=missing_metrics,
                missing_labels=tuple(sorted(set(missing_labels))),
                deprecated=definition.is_deprecated,
                replacement_key=definition.replacement_key,
            ))

        retention = self.validate_retention(('24h', '7d', '30d', '60d'))
        blocked = sum(item.status == 'blocked' for item in results)
        deprecated = sum(item.status == 'deprecated' for item in results)
        domain_summary = self._domain_summary(definitions, results)
        blocked_details = self._blocked_details(definitions, results)
        capability_assessments = self._capability_assessments(
            available_metrics, metric_label_cache, retention, blocked_details
        )
        feature_contracts = evaluate_feature_contracts(self.client, sample_namespace=sample_namespace) if execute_queries else []
        if feature_contracts:
            self._reconcile_capabilities_from_contracts(capability_assessments, feature_contracts)
        module_readiness = self._module_readiness(domain_summary)
        core_domains = {'app.prometheus', 'app.analytics.capacity', 'app.analytics.utilization'}
        critical_blocked = sum(
            item['blocked_count'] for domain, item in domain_summary.items() if domain in core_domains
        )
        return {
            'profile': PROFILE_KEY,
            'checked_at': datetime.now(UTC).isoformat(),
            'query_count': len(results),
            'ready_count': len(results) - blocked - deprecated,
            'blocked_count': blocked,
            'critical_blocked_count': critical_blocked,
            'deprecated_count': deprecated,
            'domain_summary': domain_summary,
            'blocked_details': blocked_details,
            'capability_assessments': capability_assessments,
            'available_capabilities': sorted(
                item['key'] for item in capability_assessments if item['status'] == 'available'
            ),
            'module_readiness': module_readiness,
            'feature_contracts': feature_contracts,
            'retention': retention,
            'results': [asdict(item) for item in results],
        }


    @staticmethod
    def _reconcile_capabilities_from_contracts(
        assessments: list[dict[str, Any]],
        contracts: list[dict[str, Any]],
    ) -> None:
        """Make feature-query evidence authoritative over advisory metric discovery."""
        by_key = {item['key']: item for item in assessments}
        by_contract = {item['key']: item for item in contracts}
        mapping = {
            'capacity_metrics': ('capacity.cpu', 'capacity.memory', 'capacity.worker'),
            'utilization_metrics': ('utilization.cpu', 'utilization.memory'),
            'node_filesystem_identity': ('storage.filesystem',),
            'pvc_usage': ('storage.pvc',),
            'workload_metrics': ('workload.namespace', 'workload.owner', 'workload.qos'),
        }
        for capability_key, contract_keys in mapping.items():
            assessment = by_key.get(capability_key)
            selected = [by_contract[key] for key in contract_keys if key in by_contract]
            if assessment is None or not selected:
                continue
            failed = [item for item in selected if item['status'] == 'failed']
            ready = [item for item in selected if item['status'] == 'ready']
            not_observed = [item for item in selected if item['status'] == 'not_observed']
            if failed:
                assessment['status'] = 'misconfigured'
                assessment['status_label'] = 'Failed'
            elif ready:
                assessment['status'] = 'available'
                assessment['status_label'] = 'Ready'
            elif not_observed:
                assessment['status'] = 'not_observed'
                assessment['status_label'] = 'Not Observed'
            assessment['evidence'] = ' '.join(item['observed'] for item in selected)
            assessment['observed'] = assessment['evidence']
            assessment['expected'] = ' '.join(item['expected'] for item in selected)
            assessment['technical_checks'] = [
                check
                for item in selected
                for check in item['technical_checks']
            ]
            assessment['technical_check_count_display'] = (
                f"{len(assessment['technical_checks'])} technical checks"
            )
            assessment['recommendation'] = ' '.join(
                item['recommendation'] for item in selected if item['status'] != 'ready'
            ) or 'No remediation is required. The exact registered Analytics queries passed.'

    def validate_retention(self, horizons: Iterable[str]) -> dict[str, dict[str, Any]]:
        output: dict[str, dict[str, Any]] = {}
        now = datetime.now(UTC)
        for horizon in horizons:
            delta = _parse_duration(horizon)
            sample_time = now - delta
            response = self.client.query_at('count(up)', sample_time.timestamp())
            rows = response.get('data', {}).get('result', []) if response.get('status') == 'success' else []
            output[horizon] = {
                'available': bool(rows),
                'sample_time': sample_time.isoformat(),
                'message': 'Historical samples found.' if rows else 'No historical samples found at this horizon.',
            }
        return output

    def _available_metric_names(self) -> set[str]:
        response = self.client.label_values('__name__')
        return set(response.get('data') or []) if response.get('status') == 'success' else set()

    def _labels_for_metrics(self, metrics: set[str]) -> dict[str, set[str]]:
        """Fetch recent label schemas in bounded batches instead of one request per query.

        Thanos Query can make unbounded /series calls expensive. Restricting discovery to
        the last 15 minutes and batching metric selectors keeps full validation finite.
        A failed batch is recorded as an empty schema and degrades only affected queries.
        """
        output = {metric: set() for metric in metrics}
        metric_list = sorted(metrics)
        now = datetime.now(UTC)
        start = (now - timedelta(minutes=15)).timestamp()
        end = now.timestamp()
        for offset in range(0, len(metric_list), 12):
            batch = metric_list[offset:offset + 12]
            try:
                response = self.client.series(batch, limit=500, start=start, end=end)
            except PrometheusError:
                continue
            rows = response.get('data') or [] if response.get('status') == 'success' else []
            for row in rows:
                metric = row.get('__name__')
                if metric in output:
                    output[metric].update(row.keys())
        return output

    def _capability_assessments(
        self,
        available_metrics: set[str],
        metric_labels: dict[str, set[str]],
        retention: dict[str, dict[str, Any]],
        blocked_details: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        assessments: list[dict[str, Any]] = []

        def add(
            key: str,
            status: str,
            evidence: str,
            *,
            observed: str | None = None,
            expected: str | None = None,
            technical_checks: list[dict[str, str]] | None = None,
            possible_causes: list[str] | None = None,
        ) -> None:
            item = capability_definition(key)
            if item is None:
                return
            status_labels = {
                'available': 'Ready',
                'missing': 'Failed',
                'misconfigured': 'Failed',
                'not_observed': 'Not Observed',
                'unsupported': 'Unsupported',
            }
            checks = technical_checks or []
            for check in checks:
                check.setdefault('status_label', status_labels.get(check.get('status', ''), 'Unknown'))
            assessments.append({
                'key': item.key,
                'label': item.label,
                'status': status,
                'status_label': status_labels.get(status, status.replace('_', ' ').title()),
                'required_by': list(item.required_by),
                'required_by_display': ', '.join(item.required_by),
                'impact': item.impact,
                'source_owner': item.source_owner,
                'recommendation': item.recommendation,
                'expected_signals': list(item.expected_signals),
                'expected_signals_display': ', '.join(item.expected_signals),
                'validation_query': item.validation_query,
                'evidence': evidence,
                'observed': observed or evidence,
                'expected': expected or 'The complete feature query contract returns usable data.',
                'technical_checks': checks,
                'technical_check_count_display': f'{len(checks)} technical checks',
                'possible_causes': possible_causes or [],
            })

        add('instant_query', 'available', 'The configured endpoint accepted vector(1).')
        add('range_query', 'available', 'The Prometheus-compatible range query contract is expected and audited by the query profile.')

        identity = {'kube_node_info', 'kube_pod_info', 'kube_namespace_status_phase'}
        missing_identity = sorted(identity - available_metrics)
        add(
            'kubernetes_identity',
            'available' if not missing_identity else 'missing',
            'All Kubernetes identity metrics are queryable.' if not missing_identity else f"Missing metrics: {', '.join(missing_identity)}",
        )

        utilization_metrics = {
            'kube_node_status_capacity',
            'container_cpu_usage_seconds_total',
            'container_memory_working_set_bytes',
            'kube_pod_status_phase',
            'kube_node_status_condition',
            'kube_node_info',
            'kube_pod_info',
        }
        missing_utilization = sorted(utilization_metrics - available_metrics)
        utilization_label_requirements = {
            'kube_node_status_capacity': {'node', 'resource'},
            'container_cpu_usage_seconds_total': {'node', 'container'},
            'container_memory_working_set_bytes': {'node', 'container'},
            'kube_pod_status_phase': {'namespace', 'pod', 'phase'},
            'kube_node_status_condition': {'node', 'condition', 'status'},
            'kube_node_info': {'node'},
            'kube_pod_info': {'node', 'namespace', 'pod'},
        }
        invalid_utilization_labels = sorted(
            metric
            for metric, required_labels in utilization_label_requirements.items()
            if metric in available_metrics
            and not required_labels.issubset(metric_labels.get(metric, set()))
        )
        if missing_utilization:
            utilization_status = 'missing'
            utilization_evidence = f"Missing metrics: {', '.join(missing_utilization)}"
        elif invalid_utilization_labels:
            utilization_status = 'misconfigured'
            utilization_evidence = (
                'Required utilization labels are incomplete on: '
                f"{', '.join(invalid_utilization_labels)}."
            )
        else:
            utilization_status = 'available'
            utilization_evidence = 'CPU, memory, pod, readiness, pressure, and node identity contracts are queryable.'
        add('utilization_metrics', utilization_status, utilization_evidence)

        workload_metrics = {
            'kube_namespace_status_phase',
            'kube_resourcequota',
            'kube_pod_owner',
            'kube_pod_status_qos_class',
            'kube_pod_info',
            'kube_pod_container_resource_requests',
            'kube_pod_container_resource_limits',
            'container_cpu_usage_seconds_total',
            'container_memory_working_set_bytes',
        }
        missing_workload = sorted(workload_metrics - available_metrics)
        workload_label_requirements = {
            'kube_namespace_status_phase': {'namespace', 'phase'},
            'kube_resourcequota': {'namespace', 'resource', 'type'},
            'kube_pod_owner': {'namespace', 'pod', 'owner_kind', 'owner_name'},
            'kube_pod_status_qos_class': {'namespace', 'pod', 'qos_class'},
            'kube_pod_info': {'namespace', 'pod', 'node'},
            'kube_pod_container_resource_requests': {'namespace', 'pod', 'container', 'resource', 'unit'},
            'kube_pod_container_resource_limits': {'namespace', 'pod', 'container', 'resource', 'unit'},
            'container_cpu_usage_seconds_total': {'namespace', 'pod', 'container'},
            'container_memory_working_set_bytes': {'namespace', 'pod', 'container'},
        }
        invalid_workload_labels = sorted(
            metric
            for metric, required_labels in workload_label_requirements.items()
            if metric in available_metrics
            and not required_labels.issubset(metric_labels.get(metric, set()))
        )
        if missing_workload:
            workload_status = 'missing'
            workload_evidence = f"Missing metrics: {', '.join(missing_workload)}"
        elif invalid_workload_labels:
            workload_status = 'misconfigured'
            workload_evidence = (
                'Required workload identity and governance labels are incomplete on: '
                f"{', '.join(invalid_workload_labels)}."
            )
        else:
            workload_status = 'available'
            workload_evidence = (
                'Namespace, quota, ownership, QoS, placement, request/limit, and usage contracts are queryable.'
            )
        add('workload_metrics', workload_status, workload_evidence)

        capacity_metrics = {
            'kube_node_status_allocatable',
            'container_cpu_usage_seconds_total',
            'container_memory_working_set_bytes',
            'kube_node_role',
            'kube_pod_info',
        }
        missing_capacity = sorted(capacity_metrics - available_metrics)
        capacity_label_requirements = {
            'kube_node_status_allocatable': {'node', 'resource', 'unit'},
            'container_cpu_usage_seconds_total': {'node', 'container'},
            'container_memory_working_set_bytes': {'node', 'container'},
            'kube_node_role': {'node', 'role'},
            'kube_pod_info': {'node', 'namespace', 'pod'},
        }
        invalid_capacity_labels = sorted(
            metric
            for metric, required_labels in capacity_label_requirements.items()
            if metric in available_metrics
            and not required_labels.issubset(metric_labels.get(metric, set()))
        )
        if missing_capacity:
            capacity_status = 'missing'
            capacity_evidence = f"Missing metrics: {', '.join(missing_capacity)}"
        elif invalid_capacity_labels:
            capacity_status = 'misconfigured'
            capacity_evidence = (
                'Required worker-capacity labels are incomplete on: '
                f"{', '.join(invalid_capacity_labels)}."
            )
        else:
            capacity_status = 'available'
            capacity_evidence = 'Worker allocatable, usage, role, and pod-placement contracts are queryable.'
        add('capacity_metrics', capacity_status, capacity_evidence)

        resource = {'kube_pod_container_resource_requests', 'kube_pod_container_resource_limits'}
        missing_resource = sorted(resource - available_metrics)
        add(
            'resource_requests_limits',
            'available' if not missing_resource else 'missing',
            'Request and limit metrics are queryable.' if not missing_resource else f"Missing metrics: {', '.join(missing_resource)}",
        )

        pvc_metrics = (
            'kubelet_volume_stats_capacity_bytes',
            'kubelet_volume_stats_used_bytes',
            'kubelet_volume_stats_available_bytes',
        )
        pvc_checks = [
            self._technical_metric_check(metric, available_metrics, metric_labels, {'namespace', 'persistentvolumeclaim'})
            for metric in pvc_metrics
        ]
        pvc_contract = self._query_contract(
            'sum by (namespace, persistentvolumeclaim) (kubelet_volume_stats_used_bytes)',
            required_labels={'namespace', 'persistentvolumeclaim'},
        )
        pvc_missing = [metric for metric in pvc_metrics if metric not in available_metrics]
        if pvc_contract['passed']:
            pvc_status = 'available'
            pvc_evidence = f"Validation query returned {pvc_contract['series_count']} PVC series."
        elif pvc_missing:
            pvc_status = 'missing'
            pvc_evidence = f"Validation query failed because metrics were not found: {', '.join(pvc_missing)}."
        else:
            pvc_status = 'not_observed'
            pvc_evidence = 'PVC metrics are available, but the validation query returned no active PVC series.'
        add(
            'pvc_usage',
            pvc_status,
            pvc_evidence,
            observed=pvc_contract['observed'],
            expected='At least one numeric series grouped by namespace and persistentvolumeclaim when PVCs are active.',
            technical_checks=pvc_checks + [pvc_contract['technical_check']],
            possible_causes=[
                'No active PVC currently exposes kubelet volume statistics.',
                'Kubelet volume metrics are filtered before reaching the configured query endpoint.',
                'Namespace or persistentvolumeclaim labels were transformed by relabeling.',
            ],
        )

        filesystem_metrics = ('node_filesystem_size_bytes', 'node_filesystem_avail_bytes')
        filesystem_checks = [
            self._technical_metric_check(metric, available_metrics, metric_labels, {'mountpoint', 'fstype'})
            for metric in filesystem_metrics
        ]
        size_contract = self._filesystem_contract('node_filesystem_size_bytes')
        available_contract = self._filesystem_contract('node_filesystem_avail_bytes')
        filesystem_missing = [metric for metric in filesystem_metrics if metric not in available_metrics]
        if size_contract['passed'] and available_contract['passed']:
            node_status = 'available'
            common_nodes = sorted(size_contract['nodes'] & available_contract['nodes'])
            node_evidence = (
                f"Storage query contract passed. Capacity and available queries returned canonical node series"
                f" for {len(common_nodes)} shared nodes."
            )
        elif filesystem_missing:
            node_status = 'missing'
            node_evidence = f"Storage query contract failed because metrics were not found: {', '.join(filesystem_missing)}."
        else:
            node_status = 'misconfigured'
            node_evidence = (
                'Filesystem metrics are present, but one or more exact Storage Analytics validation queries '
                'did not return usable canonical node series.'
            )
        observed_nodes = sorted(size_contract['nodes'] | available_contract['nodes'])
        add(
            'node_filesystem_identity',
            node_status,
            node_evidence,
            observed=(
                f"Capacity query: {size_contract['series_count']} series; available query: "
                f"{available_contract['series_count']} series; canonical nodes observed: "
                f"{', '.join(observed_nodes[:5]) or 'none'}."
            ),
            expected=(
                'Both exact Storage Analytics queries return at least one numeric series with node, '
                'nodename, or kubernetes_node identity. /var is preferred and / is accepted as fallback.'
            ),
            technical_checks=filesystem_checks + [
                size_contract['technical_check'],
                available_contract['technical_check'],
            ],
            possible_causes=[
                'The /var and / mountpoint filters do not match the labels exposed by node-exporter.',
                'A recording rule or metric relabel rule changes the labels used by the analytics query.',
                'Thanos Query can see the raw metric but not the expected recent series or store block.',
                'The validator query and the Storage Analytics query profile are out of sync.',
            ],
        )

        history_ready = bool(retention.get('60d', {}).get('available'))
        add(
            'long_term_history',
            'available' if history_ready else 'missing',
            'Historical samples were found at 60 days.' if history_ready else 'No samples were found at the 60-day horizon.',
        )

        return assessments

    def _query_contract(
        self,
        expression: str,
        *,
        required_labels: set[str] | None = None,
    ) -> dict[str, Any]:
        required_labels = required_labels or set()
        try:
            response = self.client.query(expression)
        except PrometheusError as exc:
            return {
                'passed': False,
                'series_count': 0,
                'observed': f'Validation query failed: {type(exc).__name__}.',
                'technical_check': {
                    'label': 'Validation query',
                    'status': 'misconfigured',
                    'evidence': f'Provider rejected the query: {type(exc).__name__}.',
                },
            }
        rows = response.get('data', {}).get('result', []) if response.get('status') == 'success' else []
        valid_rows = [
            row for row in rows
            if required_labels.issubset(set((row.get('metric') or {}).keys()))
        ]
        passed = bool(valid_rows)
        return {
            'passed': passed,
            'series_count': len(valid_rows),
            'observed': (
                f'{len(valid_rows)} usable series returned from {len(rows)} total series.'
                if rows else 'The validation query returned zero series.'
            ),
            'technical_check': {
                'label': 'Validation query',
                'status': 'available' if passed else 'misconfigured',
                'evidence': f'{len(valid_rows)} usable series returned from {len(rows)} total series.',
            },
        }

    def _filesystem_contract(self, metric: str) -> dict[str, Any]:
        canonical_labels = ('node', 'nodename', 'kubernetes_node')
        expressions = (
            f'{metric}{{mountpoint="/var", fstype!~"tmpfs|overlay"}}',
            f'{metric}{{mountpoint="/", fstype!~"tmpfs|overlay"}}',
        )
        selected_expression = expressions[0]
        rows: list[dict[str, Any]] = []
        for expression in expressions:
            selected_expression = expression
            try:
                response = self.client.query(expression)
            except PrometheusError:
                continue
            rows = response.get('data', {}).get('result', []) if response.get('status') == 'success' else []
            if rows:
                break
        nodes: set[str] = set()
        usable = 0
        for row in rows:
            labels = row.get('metric') or {}
            identity = next((labels.get(label) for label in canonical_labels if labels.get(label)), None)
            if identity:
                nodes.add(str(identity))
                usable += 1
        passed = usable > 0
        return {
            'passed': passed,
            'series_count': usable,
            'nodes': nodes,
            'technical_check': {
                'label': f'{metric} analytics query',
                'status': 'available' if passed else 'misconfigured',
                'evidence': (
                    f'{usable} usable series across {len(nodes)} canonical nodes using: {selected_expression}'
                    if rows else f'Zero series returned using /var and / fallback queries for {metric}.'
                ),
            },
        }

    @staticmethod
    def _technical_metric_check(
        metric: str,
        available_metrics: set[str],
        metric_labels: dict[str, set[str]],
        advisory_labels: set[str],
    ) -> dict[str, str]:
        if metric not in available_metrics:
            return {
                'label': metric,
                'status': 'missing',
                'evidence': 'Metric name was not found in the configured query endpoint.',
            }
        observed = sorted(metric_labels.get(metric, set()))
        matched = sorted(advisory_labels & set(observed))
        return {
            'label': metric,
            'status': 'available',
            'evidence': (
                f"Metric is available. Advisory labels observed: {', '.join(matched) or 'none in recent /series sample'}."
            ),
        }

    @staticmethod
    def _module_readiness(domain_summary: dict[str, dict[str, int]]) -> dict[str, dict[str, object]]:
        labels = {
            'app.prometheus': 'Kubernetes Overview',
            'app.analytics.utilization': 'Utilization Analytics',
            'app.analytics.capacity': 'Capacity Analytics',
            'app.analytics.storage': 'Storage Analytics',
            'app.analytics.workload': 'Workload Analytics',
            'app.analytics.forecast': 'Forecast',
            'app.analytics.top_consumers': 'Top Consumers',
        }
        output: dict[str, dict[str, object]] = {}
        for domain, values in domain_summary.items():
            blocked = values.get('blocked_count', 0)
            output[domain] = {
                'label': labels.get(domain, domain.replace('app.analytics.', '').replace('app.', '').replace('_', ' ').title()),
                'status': 'ready' if blocked == 0 else ('unavailable' if values.get('ready_count', 0) == 0 else 'degraded'),
                'ready_count': values.get('ready_count', 0),
                'query_count': values.get('query_count', 0),
                'blocked_count': blocked,
            }
        return output

    @staticmethod
    def _blocked_details(definitions: Sequence[Any], results: Sequence[QueryCheckResult]) -> list[dict[str, Any]]:
        """Return compact, user-facing evidence for checks that block profile coverage."""
        output: list[dict[str, Any]] = []
        for definition, result in zip(definitions, results, strict=True):
            if result.status != 'blocked':
                continue
            output.append({
                'key': result.key,
                'domain': definition.domain,
                'domain_label': definition.domain.replace('app.analytics.', '').replace('app.', '').replace('.', ' ').replace('_', ' ').title(),
                'message': result.message,
                'missing_metrics': list(result.missing_metrics),
                'missing_labels': list(result.missing_labels),
            })
        return output

    @staticmethod
    def _domain_summary(definitions: Sequence[Any], results: Sequence[QueryCheckResult]) -> dict[str, dict[str, int]]:
        output: dict[str, dict[str, int]] = {}
        for definition, result in zip(definitions, results, strict=True):
            item = output.setdefault(definition.domain, {'query_count': 0, 'ready_count': 0, 'blocked_count': 0, 'deprecated_count': 0})
            item['query_count'] += 1
            if result.status == 'ready':
                item['ready_count'] += 1
            elif result.status == 'blocked':
                item['blocked_count'] += 1
            elif result.status == 'deprecated':
                item['deprecated_count'] += 1
        return output


def _parse_duration(value: str) -> timedelta:
    unit = value[-1]
    amount = int(value[:-1])
    if unit == 'h':
        return timedelta(hours=amount)
    if unit == 'd':
        return timedelta(days=amount)
    raise ValueError(f'Unsupported retention duration: {value}')


def _escape_label_value(value: str) -> str:
    return value.replace('\\', '\\\\').replace('\"', '\\"')
