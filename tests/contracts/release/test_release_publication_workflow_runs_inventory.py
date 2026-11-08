"""Fail-closed regression coverage for publication workflow-run metadata #4212."""

import importlib.util
import json
import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace

SCRIPT = Path(__file__).resolve().parents[3] / 'scripts/publication_workflow_runs_inventory.py'
SPEC = importlib.util.spec_from_file_location('publication_workflow_runs_inventory', SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class WorkflowRunsInventoryTests(unittest.TestCase):
    def run_inventory(self, pages, returncode=0):
        calls = []

        def runner(command, **kwargs):
            calls.append((command, kwargs))
            return SimpleNamespace(returncode=returncode, stdout=json.dumps(pages))

        result = MODULE.inventory('OXY7O/KAORI', runner=runner)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1]['timeout'], 30)
        self.assertEqual(calls[0][1]['check'], False)
        return result

    def test_complete_pagination_counts_without_exposing_run_metadata(self):
        pages = [
            {'total_count': 2, 'workflow_runs': [{'id': 1, 'name': 'private-build'}]},
            {'total_count': 2, 'workflow_runs': [{'id': 2, 'logs_url': 'sensitive-url'}]},
        ]
        result = self.run_inventory(pages)
        self.assertEqual(result['run_metadata_access'], 'READ')
        self.assertEqual(result['run_count'], 2)
        self.assertEqual(result['assessment'], 'INCOMPLETE')
        self.assertNotIn('private-build', json.dumps(result))
        self.assertNotIn('sensitive-url', json.dumps(result))

    def test_incomplete_pagination_fails_closed(self):
        result = self.run_inventory([{'total_count': 2, 'workflow_runs': [{'id': 1}]}])
        self.assertEqual(result['run_metadata_access'], 'FAILED_OR_INCOMPLETE')
        self.assertIsNone(result['run_count'])

    def test_inconsistent_page_totals_fail_closed(self):
        pages = [
            {'total_count': 2, 'workflow_runs': [{'id': 1}]},
            {'total_count': 3, 'workflow_runs': [{'id': 2}]},
        ]
        self.assertEqual(self.run_inventory(pages)['run_metadata_access'], 'FAILED_OR_INCOMPLETE')

    def test_duplicate_and_boolean_ids_fail_closed(self):
        for ids in ([1, 1], [True, 2], [0, 2]):
            with self.subTest(ids=ids):
                result = self.run_inventory([{'total_count': 2, 'workflow_runs': [{'id': i} for i in ids]}])
                self.assertEqual(result['run_metadata_access'], 'FAILED_OR_INCOMPLETE')

    def test_malformed_pages_fail_closed(self):
        for pages in (
            [],
            {},
            [{'total_count': 1, 'workflow_runs': None}],
            [{'total_count': True, 'workflow_runs': []}],
        ):
            with self.subTest(pages=pages):
                self.assertEqual(self.run_inventory(pages)['run_metadata_access'], 'FAILED_OR_INCOMPLETE')

    def test_api_failure_and_timeout_fail_closed(self):
        self.assertEqual(self.run_inventory([], returncode=1)['run_metadata_access'], 'FAILED_OR_INCOMPLETE')

        def timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd='gh', timeout=30)

        self.assertEqual(
            MODULE.inventory('OXY7O/KAORI', runner=timeout)['run_metadata_access'],
            'FAILED_OR_INCOMPLETE',
        )

    def test_invalid_repository_rejected_before_runner(self):
        def forbidden(*args, **kwargs):
            self.fail('runner must not execute')

        for name in ('../KAORI', 'OXY7O/..', 'OXY7O/.', 'OXY7O/KAORI/extra', None):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    MODULE.inventory(name, runner=forbidden)


if __name__ == '__main__':
    unittest.main()
