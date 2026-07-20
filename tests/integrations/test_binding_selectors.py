from __future__ import annotations

import ast
import importlib.util
import re
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[2] / 'app/integrations/binding_selectors.py'
SPEC = importlib.util.spec_from_file_location('kaori_binding_selectors', MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
BindingSelectorError = MODULE.BindingSelectorError
apply_promql_scope = MODULE.apply_promql_scope
build_selector = MODULE.build_selector
selector_filters = MODULE.selector_filters
selector_summary = MODULE.selector_summary


def test_build_selector_normalizes_provider_neutral_matcher() -> None:
    selector = build_selector(label=' cluster ', value=' k8s-vm-dev ', operator='=')

    assert selector == {
        'matchers': [
            {'label': 'cluster', 'operator': '=', 'value': 'k8s-vm-dev'},
        ]
    }
    assert selector_filters(selector) == ('cluster="k8s-vm-dev"',)
    assert selector_summary(selector) == 'cluster="k8s-vm-dev"'


def test_promql_scope_is_injected_into_bare_and_explicit_vectors() -> None:
    selector = build_selector(label='cluster', value='k8s-vm-dev')
    expression = 'sum by (node) (rate(container_cpu_usage_seconds_total{container!=""}[5m])) / count(kube_node_info)'

    scoped = apply_promql_scope(expression, selector)

    assert 'container_cpu_usage_seconds_total{cluster="k8s-vm-dev",container!=""}' in scoped
    assert 'kube_node_info{cluster="k8s-vm-dev"}' in scoped
    assert 'sum by (node)' in scoped
    assert 'rate(' in scoped


def test_promql_scope_rejects_conflicting_existing_identity() -> None:
    selector = build_selector(label='cluster', value='k8s-vm-dev')

    with pytest.raises(BindingSelectorError, match='conflicting matcher'):
        apply_promql_scope('up{cluster="k8s-prod"}', selector)


def test_selector_requires_both_label_and_value() -> None:
    with pytest.raises(BindingSelectorError, match='Both selector label and selector value'):
        build_selector(label='cluster', value='')


def test_promql_scope_does_not_lose_metrics_adjacent_to_arithmetic_operators() -> None:
    selector = build_selector(label='cluster', value='k8s-vm-dev')

    assert apply_promql_scope('1+up', selector) == '1+up{cluster="k8s-vm-dev"}'
    assert apply_promql_scope('1-up', selector) == '1-up{cluster="k8s-vm-dev"}'
    assert apply_promql_scope('1e-3+up', selector) == '1e-3+up{cluster="k8s-vm-dev"}'


def test_promql_scope_preserves_label_lists_durations_strings_and_comments() -> None:
    selector = build_selector(label='cluster', value='k8s-vm-dev')
    expression = 'sum without (pod, container) (rate(http_requests_total[5m])) # keep metric_name\nlabel_replace(up, "dst", "$1", "src", "(.*)")'

    scoped = apply_promql_scope(expression, selector)

    assert 'sum without (pod, container)' in scoped
    assert 'http_requests_total{cluster="k8s-vm-dev"}[5m]' in scoped
    assert '# keep metric_name' in scoped
    assert 'label_replace(up{cluster="k8s-vm-dev"}, "dst", "$1", "src", "(.*)")' in scoped


def test_all_registered_promql_profile_metrics_receive_scope_matcher() -> None:
    selector = build_selector(label='cluster', value='k8s-vm-dev')
    profile_path = Path(__file__).resolve().parents[2] / 'app/prometheus/query_profiles/kubernetes_v1.py'
    tree = ast.parse(profile_path.read_text(encoding='utf-8'))
    checked = 0

    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == 'QueryDefinition'
        ):
            continue
        values: dict[str, object] = {}
        for keyword in node.keywords:
            try:
                values[str(keyword.arg)] = ast.literal_eval(keyword.value)
            except (TypeError, ValueError):
                continue
        expression = values.get('expression')
        required_metrics = values.get('required_metrics', ())
        if not isinstance(expression, str) or not isinstance(required_metrics, tuple):
            continue
        scoped = apply_promql_scope(expression, selector)
        for metric in required_metrics:
            if not isinstance(metric, str):
                continue
            checked += 1
            pattern = rf'(?<![A-Za-z0-9_:]){re.escape(metric)}\{{[^}}]*cluster="k8s-vm-dev"'
            assert re.search(pattern, scoped), f'{values.get("key")}: {metric} was not scoped'

    assert checked >= 200


def test_selector_form_values_supports_legacy_and_configured_bindings() -> None:
    assert MODULE.selector_form_values(None) == {'label': '', 'operator': '=', 'value': ''}
    assert MODULE.selector_form_values(
        MODULE.build_selector(label='cluster', operator='=~', value='prod-.+')
    ) == {'label': 'cluster', 'operator': '=~', 'value': 'prod-.+'}
