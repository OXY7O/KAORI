import runpy
from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding='utf-8')


def test_recommendation_detail_exposes_affected_assets_and_measured_evidence() -> None:
    template = read('app/templates/intelligence/partials/_recommendation_detail_content.html')
    runtime = read('app/intelligence/kubernetes_runtime_recommendations.py')
    evidence = read('app/intelligence/finding_evidence.py')

    assert 'Affected Assets' in template
    assert 'Evidence Details' in template
    assert 'Observed Evidence' in template
    assert 'item.affected_assets' in template
    assert 'item.evidence_details' in template
    assert 'build_restart_groups' in runtime
    assert 'build_restart_evidence' in runtime
    assert 'Current Pod Inventory generation' in evidence
    assert "'affected_assets': assets" in evidence
    assert "'threshold_display': f'>= {threshold} restarts per pod'" in evidence
    assert "'max_observation_display': f'{highest_count} restarts'" in evidence
    assert "'max_observation_asset': highest_name" in evidence


def test_recommendation_evidence_presenter_keeps_asset_identity_and_restart_evidence() -> None:
    module = runpy.run_path('app/intelligence/finding_presentation.py')
    item = {
        'source_kind_label': 'Pod',
        'evidence': {
            'affected_count': 1,
            'threshold_display': '>= 5 restarts per pod',
            'observed_total_display': '100 restarts across 1 affected pod',
            'max_observation_display': '100 restarts',
            'max_observation_asset': 'payments-api-7d9f',
            'snapshot_basis': 'Current Pod Inventory generation',
            'affected_assets': [
                {
                    'type': 'Pod',
                    'name': 'payments-api-7d9f',
                    'namespace': 'payments',
                    'workload_type': 'Deployment',
                    'workload_name': 'payments-api',
                    'node_name': 'worker-01',
                    'phase': 'Running',
                    'evidence_display': '100 restarts',
                }
            ],
        },
    }

    assets = module['build_affected_assets'](item)
    evidence = module['build_evidence_details'](item)

    assert assets == [
        {
            'type': 'Pod',
            'name': 'payments-api-7d9f',
            'namespace': 'payments',
            'owner': 'Deployment / payments-api',
            'node': 'worker-01',
            'state': 'Running',
            'evidence': '100 restarts',
        }
    ]
    assert {'label': 'Trigger Threshold', 'value': '>= 5 restarts per pod'} in evidence
    assert {'label': 'Highest Observation', 'value': '100 restarts'} in evidence
    assert {'label': 'Highest Impact Asset', 'value': 'payments-api-7d9f'} in evidence


def test_restart_review_header_uses_measured_counts_without_losing_original_evidence() -> None:
    presentation = runpy.run_path('app/intelligence/finding_presentation.py')
    summary = presentation['recommendation_detail_header_summary']
    finding = {
        'rule_key': 'kubernetes.pod.high_restart_count:cluster:capsule-system',
        'summary': 'Full source summary with highest pod name and measured counts.',
        'evidence': {
            'evidence_window': 'Latest fast Kubernetes alert signal',
            'affected_count': 2,
            'total_restart_count': 91,
            'max_restart_count': 70,
        },
    }

    assert summary(finding) == (
        'Latest fast Kubernetes alert signal · 2 affected pods · '
        '91 total restarts · peak 70'
    )
    assert finding['summary'] == 'Full source summary with highest pod name and measured counts.'

    one_pod = {
        **finding,
        'evidence': {
            **finding['evidence'],
            'affected_count': 1,
            'total_restart_count': 70,
        },
    }
    assert '1 affected pod · 70 total restarts · peak 70' in summary(one_pod)


def test_modal_header_keeps_full_context_when_restart_evidence_is_incomplete() -> None:
    presentation = runpy.run_path('app/intelligence/finding_presentation.py')
    summary = presentation['recommendation_detail_header_summary']
    original = 'Source-qualified evidence must remain available in its original form.'
    finding = {
        'rule_key': 'kubernetes.pod.high_restart_count:cluster:capsule-system',
        'summary': original,
        'evidence': {
            'affected_count': 2,
            'total_restart_count': 91,
        },
    }
    assert summary(finding) == original
    assert summary({**finding, 'evidence': {**finding['evidence'], 'max_restart_count': 100}}) == original
    assert summary({**finding, 'rule_key': 'registry.image.scan'}) == original

    template = read('app/templates/intelligence/partials/_recommendation_detail_content.html')
    service = read('app/intelligence/service.py')
    assert 'data-kaori-recommendation-header-summary' in template
    assert 'xl:whitespace-nowrap' in template
    assert 'title="{{ item.summary }}"' in template
    assert 'item.detail_header_summary|default(item.summary, true)' in template
    assert "finding['detail_header_summary'] = recommendation_detail_header_summary(finding)" in service
