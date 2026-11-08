"""Regression coverage for sanitized workflow-run metadata inventory (#4212)."""

import importlib.util
import json
import subprocess
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'publication_workflow_runs_inventory.py'
spec = importlib.util.spec_from_file_location('publication_workflow_runs_inventory', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class WorkflowRunInventoryTests(unittest.TestCase):
    def run_inventory(self, pages, returncode=0):
        def runner(command, **kwargs):
            self.assertEqual(command[:4], ['gh', 'api', '--paginate', '--slurp'])
            self.assertEqual(kwargs['timeout'], 30)
            return subprocess.CompletedProcess(command, returncode, json.dumps(pages), '')

        return module.inventory('OXY7O/KAORI', runner)

    def test_counts_without_disclosing_names_or_urls(self):
        pages = [
            {'total_count': 2, 'workflow_runs': [{'id': 1, 'name': 'private', 'logs_url': 'https://private.invalid'}]},
            {'total_count': 2, 'workflow_runs': [{'id': 2}]},
        ]
        result = self.run_inventory(pages)
        self.assertEqual(result['run_count'], 2)
        self.assertEqual(result['assessment'], 'INCOMPLETE')
        self.assertNotIn('private', json.dumps(result))
        self.assertNotIn('logs_url', json.dumps(result))

    def test_empty_valid_inventory(self):
        result = self.run_inventory([{'total_count': 0, 'workflow_runs': []}])
        self.assertEqual(result['run_count'], 0)

    def test_partial_pagination_fails_closed(self):
        result = self.run_inventory([{'total_count': 3, 'workflow_runs': [{'id': 1}]}])
        self.assertIsNone(result['run_count'])

    def test_duplicate_and_invalid_ids_fail_closed(self):
        for ids in ([1, 1], [0, 2], [True, 2]):
            with self.subTest(ids=ids):
                result = self.run_inventory([{'total_count': 2, 'workflow_runs': [{'id': i} for i in ids]}])
                self.assertIsNone(result['run_count'])

    def test_inconsistent_total_fails_closed(self):
        result = self.run_inventory(
            [{'total_count': 2, 'workflow_runs': [{'id': 1}]}, {'total_count': 3, 'workflow_runs': [{'id': 2}]}]
        )
        self.assertIsNone(result['run_count'])

    def test_api_failure_fails_closed(self):
        result = self.run_inventory([], returncode=1)
        self.assertEqual(result['run_metadata_access'], 'FAILED_OR_INCOMPLETE')

    def test_malformed_pages_and_run_records_fail_closed(self):
        cases = [
            [],
            {},
            [None],
            [{'workflow_runs': [], 'total_count': True}],
            [{'workflow_runs': [], 'total_count': -1}],
            [{'workflow_runs': [], 'total_count': '0'}],
            [{'workflow_runs': [None], 'total_count': 1}],
            [{'workflow_runs': ['unexpected'], 'total_count': 1}],
            [{'workflow_runs': [{'name': 'missing id'}], 'total_count': 1}],
        ]
        for pages in cases:
            with self.subTest(pages=pages):
                result = self.run_inventory(pages)
                self.assertEqual(result['assessment'], 'INCOMPLETE')
                self.assertEqual(result['run_metadata_access'], 'FAILED_OR_INCOMPLETE')
                self.assertIsNone(result['run_count'])

    def test_missing_cli_and_timeout_fail_closed_without_details(self):
        for error in (
            FileNotFoundError('sensitive executable path'),
            subprocess.TimeoutExpired(['gh', 'api', 'sensitive'], 30),
        ):
            with self.subTest(error=type(error).__name__):

                def runner(*args, **kwargs):
                    raise error

                result = module.inventory('OXY7O/KAORI', runner)
                self.assertEqual(result['run_metadata_access'], 'FAILED_OR_INCOMPLETE')
                self.assertIsNone(result['run_count'])
                self.assertNotIn('sensitive', json.dumps(result))

    def test_invalid_json_and_api_stderr_are_not_exposed(self):
        def runner(command, **kwargs):
            return subprocess.CompletedProcess(command, 0, '{invalid-json', 'private diagnostic')

        result = module.inventory('OXY7O/KAORI', runner)
        self.assertEqual(result['run_metadata_access'], 'FAILED_OR_INCOMPLETE')
        self.assertNotIn('private diagnostic', json.dumps(result))

    def test_sanitized_outcome_aggregation(self):
        records = [
            {'id': 1, 'conclusion': 'success', 'name': 'private workflow', 'logs_url': 'https://private.invalid'},
            {'id': 2, 'conclusion': 'failure'},
            {'id': 3, 'conclusion': None},
            {'id': 4, 'conclusion': 'unexpected-sensitive-value'},
        ]
        result = self.run_inventory([{'total_count': 4, 'workflow_runs': records}])
        self.assertEqual(
            result['conclusion_counts'],
            {'success': 1, 'failure': 1, 'cancelled': 0, 'timed_out': 0, 'action_required': 0, 'other': 2},
        )
        self.assertEqual(sum(result['conclusion_counts'].values()), result['run_count'])
        self.assertNotIn('private workflow', json.dumps(result))
        self.assertNotIn('unexpected-sensitive-value', json.dumps(result))
        self.assertNotIn('private.invalid', json.dumps(result))

    def test_malformed_conclusion_fails_closed(self):
        result = self.run_inventory(
            [{'total_count': 1, 'workflow_runs': [{'id': 1, 'conclusion': {'secret': 'never-print'}}]}]
        )
        self.assertEqual(result['run_metadata_access'], 'FAILED_OR_INCOMPLETE')
        self.assertIsNone(result['conclusion_counts'])
        self.assertNotIn('never-print', json.dumps(result))

    def test_sanitized_lifecycle_status_aggregation(self):
        records = [
            {'id': 1, 'status': 'completed', 'conclusion': 'success'},
            {'id': 2, 'status': 'queued', 'conclusion': None},
            {'id': 3, 'status': 'in_progress', 'conclusion': None},
            {'id': 4, 'status': 'sensitive-provider-status', 'conclusion': None},
        ]
        result = self.run_inventory([{'total_count': 4, 'workflow_runs': records}])
        self.assertEqual(result['status_counts'], {'completed': 1, 'queued': 1, 'in_progress': 1, 'other': 1})
        self.assertEqual(sum(result['status_counts'].values()), result['run_count'])
        self.assertNotIn('sensitive-provider-status', json.dumps(result))

    def test_invalid_status_fails_closed(self):
        result = self.run_inventory(
            [{'total_count': 1, 'workflow_runs': [{'id': 1, 'status': {'private': 'never-print'}}]}]
        )
        self.assertEqual(result['run_metadata_access'], 'FAILED_OR_INCOMPLETE')
        self.assertIsNone(result['status_counts'])
        self.assertNotIn('never-print', json.dumps(result))

    def test_invalid_repository_never_invokes_runner(self):
        for value in ('../KAORI', 'OXY7O/..', 'OXY7O/KAORI;id', None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    module.inventory(value, lambda *a, **k: self.fail('runner invoked'))


if __name__ == '__main__':
    unittest.main()
