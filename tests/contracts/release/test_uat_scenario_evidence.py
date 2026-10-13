from pathlib import Path

from scripts.uat_scenario_evidence import evaluate, read_junit

SHA = 'a' * 40
TREE = 'b' * 40
MANIFEST = {
    'scenarios': [{
        'id': 'UAT-EXAMPLE-001',
        'nodes': [{'nodeid': 'tests/unit/test_example.py::test_case'}],
        'required_artifacts': {},
    }]
}
EXECUTION = {
    'candidate': {'source_sha': SHA, 'tree_sha': TREE},
    'run': {'run_id': 'isolated-test-run', 'runner': 'pytest', 'started_at': '2026-10-13T09:00:00+07:00'},
    'environment': {'kind': 'local', 'provider_mode': 'simulated'},
    'evidence': {},
}


def _evaluate(cases, *, manifest=MANIFEST, execution=EXECUTION, digest=None, root=None):
    return evaluate(
        manifest, execution, cases,
        expected_source=SHA,
        expected_tree=TREE,
        expected_digest=digest,
        evidence_root=root or Path('.'),
    )


def test_missing_runner_identity_blocks_machine_readiness() -> None:
    invalid = {**EXECUTION, 'run': {}}
    report = _evaluate({'tests.unit.test_example::test_case': ['PASS']}, execution=invalid)
    assert report['scenarios'][0]['result'] == 'BLOCKED'
    assert report['machine_readiness'] == 'INCOMPLETE'


def test_naive_execution_timestamp_is_not_accepted() -> None:
    invalid = {**EXECUTION, 'run': {**EXECUTION['run'], 'started_at': '2026-10-13T09:00:00'}}
    report = _evaluate({'tests.unit.test_example::test_case': ['PASS']}, execution=invalid)
    assert report['scenarios'][0]['result'] == 'BLOCKED'


def test_missing_junit_case_is_not_run() -> None:
    report = _evaluate({})
    assert report['scenarios'][0]['result'] == 'NOT RUN'
    assert report['machine_readiness'] == 'INCOMPLETE'
    assert report['human_acceptance'] == 'PENDING'


def test_skipped_or_failed_junit_is_never_pass() -> None:
    key = 'tests.unit.test_example::test_case'
    assert _evaluate({key: ['SKIP']})['scenarios'][0]['result'] == 'SKIP'
    assert _evaluate({key: ['FAIL']})['scenarios'][0]['result'] == 'FAIL'
    assert _evaluate({key: ['PASS', 'FAIL']})['scenarios'][0]['result'] == 'FAIL'


def test_successful_junit_only_reaches_human_review_not_acceptance() -> None:
    report = _evaluate({'tests.unit.test_example::test_case': ['PASS']})
    assert report['scenarios'][0]['result'] == 'PASS'
    assert report['machine_readiness'] == 'READY_FOR_HUMAN_REVIEW'
    assert report['human_acceptance'] == 'PENDING'


def test_wrong_exact_source_tree_or_deployed_digest_blocks() -> None:
    case = {'tests.unit.test_example::test_case': ['PASS']}
    wrong = {**EXECUTION, 'candidate': {'source_sha': 'f' * 40, 'tree_sha': TREE}}
    assert _evaluate(case, execution=wrong)['scenarios'][0]['result'] == 'BLOCKED'
    wrong_tree = {**EXECUTION, 'candidate': {'source_sha': SHA, 'tree_sha': 'f' * 40}}
    assert _evaluate(case, execution=wrong_tree)['scenarios'][0]['result'] == 'BLOCKED'
    deployed = {
        **EXECUTION,
        'candidate': {'source_sha': SHA, 'tree_sha': TREE, 'oci_digest': 'sha256:' + 'c' * 64},
        'environment': {'kind': 'server_uat', 'provider_mode': 'real'},
    }
    assert _evaluate(case, execution=deployed, digest='sha256:' + 'd' * 64)['scenarios'][0]['result'] == 'BLOCKED'


def test_required_missing_or_empty_artifact_blocks(tmp_path: Path) -> None:
    case = {'tests.unit.test_example::test_case': ['PASS']}
    constrained = {'scenarios': [{**MANIFEST['scenarios'][0], 'required_artifacts': {'screenshot': 1}}]}
    assert _evaluate(case, manifest=constrained, root=tmp_path)['scenarios'][0]['result'] == 'BLOCKED'
    (tmp_path / 'shot.png').touch()
    evidence = {**EXECUTION, 'evidence': {'UAT-EXAMPLE-001': [{'kind': 'screenshot', 'path': 'shot.png'}]}}
    incomplete = _evaluate(case, manifest=constrained, execution=evidence, root=tmp_path)
    assert incomplete['scenarios'][0]['result'] == 'BLOCKED'
    (tmp_path / 'shot.png').write_bytes(b'captured')
    assert _evaluate(case, manifest=constrained, execution=evidence, root=tmp_path)['scenarios'][0]['result'] == 'PASS'


def test_real_provider_uat_is_not_inferred_from_mocked_fixtures() -> None:
    case = {'tests.unit.test_example::test_case': ['PASS']}
    constrained = {'scenarios': [{**MANIFEST['scenarios'][0], 'real_provider_required': True}]}
    assert _evaluate(case, manifest=constrained)['scenarios'][0]['result'] == 'BLOCKED'


def test_junit_reader_preserves_failing_rerun_and_parameter_ids(tmp_path: Path) -> None:
    xml = tmp_path / 'junit.xml'
    xml.write_text(
        '<testsuite>'
        '<testcase classname="tests.unit.test_example" name="test_case"/>'
        '<testcase classname="tests.unit.test_example" name="test_case"><failure/></testcase>'
        '<testcase classname="tests.ui.test_wizard" name="test_form[small-mobile]"><skipped/></testcase>'
        '</testsuite>', encoding='utf-8',
    )
    cases = read_junit([xml])
    assert cases['tests.unit.test_example::test_case'] == ['PASS', 'FAIL']
    assert cases['tests.ui.test_wizard::test_form[small-mobile]'] == ['SKIP']


def test_partial_viewport_coverage_and_skipped_variant_do_not_pass() -> None:
    variants = ['large-desktop', 'small-mobile']
    scoped = {
        'scenarios': [{
            'id': 'UAT-UIX-EXAMPLE',
            'nodes': [{
                'nodeid': 'tests/ui/test_example.py::test_viewport',
                'variants': variants,
            }],
            'required_artifacts': {},
        }]
    }
    only_one = {
        'tests.ui.test_example::test_viewport[large-desktop]': ['PASS'],
    }
    result = _evaluate(only_one, manifest=scoped)
    assert result['scenarios'][0]['result'] == 'NOT RUN'
    assert result['scenarios'][0]['passed_test_cases'] == 1

    skipped = {
        **only_one,
        'tests.ui.test_example::test_viewport[small-mobile]': ['SKIP'],
    }
    assert _evaluate(skipped, manifest=scoped)['scenarios'][0]['result'] == 'SKIP'


def test_outside_evidence_root_is_not_accepted(tmp_path: Path) -> None:
    case = {'tests.unit.test_example::test_case': ['PASS']}
    constrained = {'scenarios': [{**MANIFEST['scenarios'][0], 'required_artifacts': {'trace': 1}}]}
    outside = tmp_path.parent / 'not-in-uat-evidence.trace'
    outside.write_bytes(b'is not permitted')
    provided = {
        **EXECUTION,
        'evidence': {'UAT-EXAMPLE-001': [{
            'kind': 'trace', 'path': f'../{outside.name}',
        }]},
    }
    result = _evaluate(case, manifest=constrained, execution=provided, root=tmp_path)
    assert result['scenarios'][0]['result'] == 'BLOCKED'


def test_two_ui_nodes_require_distinct_viewport_artifacts(tmp_path: Path) -> None:
    nodes = [
        {'nodeid': f'tests/ui/test_example.py::test_{name}', 'variants': ['mobile']}
        for name in ('a', 'b')
    ]
    manifest = {'scenarios': [{
        'id': 'UAT-UIX-EXAMPLE',
        'nodes': nodes,
        'required_artifacts': {'screenshot': 2},
    }]}
    cases = {
        'tests.ui.test_example::test_a[mobile]': ['PASS'],
        'tests.ui.test_example::test_b[mobile]': ['PASS'],
    }
    (tmp_path / 'screenshot.png').write_bytes(b'image')
    first = {
        'kind': 'screenshot',
        'nodeid': nodes[0]['nodeid'],
        'variant': 'mobile',
        'path': 'screenshot.png',
    }
    request = {**EXECUTION, 'evidence': {'UAT-UIX-EXAMPLE': [first, first]}}
    assert _evaluate(cases, manifest=manifest, execution=request, root=tmp_path)['scenarios'][0]['result'] == 'BLOCKED'
    second = {**first, 'nodeid': nodes[1]['nodeid']}
    request = {**EXECUTION, 'evidence': {'UAT-UIX-EXAMPLE': [first, second]}}
    assert _evaluate(cases, manifest=manifest, execution=request, root=tmp_path)['scenarios'][0]['result'] == 'BLOCKED'
    (tmp_path / 'second.png').write_bytes(b'other visual evidence')
    second = {**second, 'path': 'second.png'}
    request = {**EXECUTION, 'evidence': {'UAT-UIX-EXAMPLE': [first, second]}}
    assert _evaluate(cases, manifest=manifest, execution=request, root=tmp_path)['scenarios'][0]['result'] == 'PASS'


def test_real_provider_requires_readback_even_with_all_junit_pass(tmp_path: Path) -> None:
    scoped = {'scenarios': [{
        **MANIFEST['scenarios'][0],
        'real_provider_required': True,
        'required_artifacts': {'provider_readback': 1},
    }]}
    digest = 'sha256:' + 'c' * 64
    request = {
        **EXECUTION,
        'candidate': {**EXECUTION['candidate'], 'oci_digest': digest},
        'environment': {'kind': 'server_uat', 'provider_mode': 'real'},
    }
    cases = {'tests.unit.test_example::test_case': ['PASS']}
    report = _evaluate(cases, manifest=scoped, execution=request, digest=digest, root=tmp_path)
    assert report['scenarios'][0]['result'] == 'BLOCKED'

    (tmp_path / 'provider-readback.json').write_text('{"verified":false}', encoding='utf-8')
    request['evidence'] = {'UAT-EXAMPLE-001': [{
        'kind': 'provider_readback', 'path': 'provider-readback.json',
    }]}
    # Presence permits machine dossier completeness, not independent provider validation.
    report = _evaluate(cases, manifest=scoped, execution=request, digest=digest, root=tmp_path)
    assert report['scenarios'][0]['result'] == 'PASS'
    assert report['human_acceptance'] == 'PENDING'
