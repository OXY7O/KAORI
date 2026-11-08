"""Regression tests for sanitized, fail-closed release metadata inventory (#4212)."""

import importlib.util
import json
import subprocess
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'publication_release_inventory.py'
spec = importlib.util.spec_from_file_location('publication_release_inventory', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReleaseInventoryTests(unittest.TestCase):
    def test_paginated_assets_are_counted_without_disclosing_identifiers(self):
        payload = [
            [
                {
                    'id': 101,
                    'name': 'confidential-release',
                    'assets': [
                        {
                            'id': 201,
                            'name': 'sensitive-asset.zip',
                            'browser_download_url': 'https://example.invalid/private',
                        }
                    ],
                }
            ],
            [{'id': 102, 'name': 'another', 'assets': []}],
        ]

        def runner(command, **kwargs):
            self.assertEqual(command[:4], ['gh', 'api', '--paginate', '--slurp'])
            return subprocess.CompletedProcess(command, 0, json.dumps(payload), '')

        report = module.inventory('OXY7O/KAORI', runner)
        self.assertEqual((report['release_count'], report['asset_count']), (2, 1))
        self.assertEqual(report['assessment'], 'INCOMPLETE')
        self.assertNotIn('sensitive-asset', json.dumps(report))
        self.assertNotIn('confidential-release', json.dumps(report))

    def test_duplicate_release_ids_fail_closed(self):
        payload = [[{'id': 7, 'assets': []}, {'id': 7, 'assets': []}]]
        report = module.inventory(
            'OXY7O/KAORI', lambda c, **k: subprocess.CompletedProcess(c, 0, json.dumps(payload), '')
        )
        self.assertEqual(report['release_metadata_access'], 'INVALID')
        self.assertIsNone(report['release_count'])

    def test_duplicate_asset_ids_fail_closed(self):
        payload = [[{'id': 7, 'assets': [{'id': 9}, {'id': 9}]}]]
        report = module.inventory(
            'OXY7O/KAORI', lambda c, **k: subprocess.CompletedProcess(c, 0, json.dumps(payload), '')
        )
        self.assertEqual(report['release_metadata_access'], 'INVALID')
        self.assertIsNone(report['asset_count'])

    def test_api_failure_does_not_claim_zero_releases(self):
        def runner(command, **kwargs):
            return subprocess.CompletedProcess(command, 1, '', 'sensitive error')

        report = module.inventory('OXY7O/KAORI', runner)
        self.assertEqual(report['release_metadata_access'], 'FAILED')
        self.assertIsNone(report['release_count'])
        self.assertNotIn('sensitive error', json.dumps(report))

    def test_malformed_pagination_fails_closed(self):
        def runner(command, **kwargs):
            return subprocess.CompletedProcess(command, 0, '{"not":"pages"}', '')

        report = module.inventory('OXY7O/KAORI', runner)
        self.assertEqual(report['release_metadata_access'], 'INVALID')
        self.assertIsNone(report['asset_count'])

    def test_rejects_untrusted_repository_identifier(self):
        with self.assertRaises(ValueError):
            module.inventory('OXY7O/KAORI;echo secret')


if __name__ == '__main__':
    unittest.main()
