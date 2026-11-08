"""Regression coverage for sanitized Actions artifact inventory (#4212)."""

import importlib.util
import json
import subprocess
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'publication_actions_inventory.py'
spec = importlib.util.spec_from_file_location('publication_actions_inventory', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ArtifactInventoryTests(unittest.TestCase):
    def test_paginated_counts_do_not_disclose_metadata(self):
        pages = [
            {'total_count': 2, 'artifacts': [{'id': 1, 'expired': False, 'name': 'secret.zip'}]},
            {
                'total_count': 2,
                'artifacts': [{'id': 2, 'expired': True, 'archive_download_url': 'https://private.invalid'}],
            },
        ]

        def runner(command, **kwargs):
            self.assertEqual(command[:4], ['gh', 'api', '--paginate', '--slurp'])
            return subprocess.CompletedProcess(command, 0, json.dumps(pages), '')

        report = module.inventory('OXY7O/KAORI', runner)
        self.assertEqual((report['artifact_count'], report['expired_count']), (2, 1))
        self.assertEqual(report['assessment'], 'INCOMPLETE')
        self.assertNotIn('secret.zip', json.dumps(report))
        self.assertNotIn('private.invalid', json.dumps(report))

    def test_failed_api_is_not_zero_artifacts(self):
        report = module.inventory('OXY7O/KAORI', lambda c, **k: subprocess.CompletedProcess(c, 1, '', 'private'))
        self.assertIsNone(report['artifact_count'])
        self.assertNotIn('private', json.dumps(report))

    def test_invalid_page_fails_closed(self):
        report = module.inventory(
            'OXY7O/KAORI', lambda c, **k: subprocess.CompletedProcess(c, 0, json.dumps([{'artifacts': [{}]}]), '')
        )
        self.assertIsNone(report['artifact_count'])

    def test_duplicate_ids_fail_closed(self):
        page = [{'total_count': 2, 'artifacts': [{'id': 1, 'expired': False}, {'id': 1, 'expired': False}]}]
        report = module.inventory('OXY7O/KAORI', lambda c, **k: subprocess.CompletedProcess(c, 0, json.dumps(page), ''))
        self.assertIsNone(report['artifact_count'])

    def test_inconsistent_total_count_fails_closed(self):
        pages = [
            {'total_count': 2, 'artifacts': [{'id': 1, 'expired': False}]},
            {'total_count': 3, 'artifacts': [{'id': 2, 'expired': False}]},
        ]
        report = module.inventory(
            'OXY7O/KAORI', lambda c, **k: subprocess.CompletedProcess(c, 0, json.dumps(pages), '')
        )
        self.assertEqual(report['artifact_metadata_access'], 'FAILED_OR_INVALID')
        self.assertIsNone(report['artifact_count'])

    def test_timeout_fails_closed_without_disclosing_command(self):
        def runner(command, **kwargs):
            self.assertEqual(kwargs['timeout'], 30)
            raise subprocess.TimeoutExpired(command, kwargs['timeout'], output='private')

        report = module.inventory('OXY7O/KAORI', runner)
        self.assertEqual(report['artifact_metadata_access'], 'FAILED_OR_INVALID')
        self.assertIsNone(report['artifact_count'])
        self.assertNotIn('private', json.dumps(report))

    def test_nonpositive_artifact_id_fails_closed(self):
        for invalid_id in (0, -1):
            with self.subTest(invalid_id=invalid_id):
                pages = [{'total_count': 1, 'artifacts': [{'id': invalid_id, 'expired': False}]}]
                report = module.inventory(
                    'OXY7O/KAORI',
                    lambda c, **k: subprocess.CompletedProcess(c, 0, json.dumps(pages), ''),
                )
                self.assertEqual(report['artifact_metadata_access'], 'FAILED_OR_INVALID')
                self.assertIsNone(report['artifact_count'])

    def test_rejects_untrusted_repository(self):
        with self.assertRaises(ValueError):
            module.inventory('OXY7O/KAORI;rm -rf /')

    def test_rejects_dot_segment_repository_without_invoking_gh(self):
        def forbidden_runner(*args, **kwargs):
            self.fail('GitHub CLI must not run for invalid repository segments')

        for invalid in ('../KAORI', 'OXY7O/..', './KAORI', 'OXY7O/.', None):
            with self.subTest(repository=invalid):
                with self.assertRaises(ValueError):
                    module.inventory(invalid, forbidden_runner)


if __name__ == '__main__':
    unittest.main()
