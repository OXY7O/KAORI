"""Fail-closed regression coverage for sanitized GitHub release metadata inventory (#4212)."""
import importlib.util
import json
import subprocess
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "publication_release_assets_inventory.py"
spec = importlib.util.spec_from_file_location("publication_release_assets_inventory", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReleaseAssetInventoryTests(unittest.TestCase):
    def run_inventory(self, pages, returncode=0):
        def runner(command, **kwargs):
            self.assertEqual(command[:4], ["gh", "api", "--paginate", "--slurp"])
            self.assertEqual(kwargs["timeout"], 30)
            return subprocess.CompletedProcess(command, returncode, json.dumps(pages), "")
        return module.inventory("OXY7O/KAORI", runner)

    def test_valid_counts_and_sanitized_output(self):
        pages = [[{"id": 1, "draft": False, "prerelease": True,
                   "name": "private-release", "assets": [{"id": 10, "name": "secret-name"}]}],
                 [{"id": 2, "draft": True, "prerelease": False, "assets": []}]]
        result = self.run_inventory(pages)
        self.assertEqual((result["release_count"], result["asset_count"],
                          result["draft_count"], result["prerelease_count"]), (2, 1, 1, 1))
        self.assertEqual(result["assessment"], "INCOMPLETE")
        self.assertNotIn("private-release", json.dumps(result))
        self.assertNotIn("secret-name", json.dumps(result))

    def test_empty_release_list_is_valid_but_not_clearance(self):
        result = self.run_inventory([[]])
        self.assertEqual(result["release_count"], 0)
        self.assertEqual(result["assessment"], "INCOMPLETE")

    def test_duplicate_or_invalid_release_ids_fail_closed(self):
        for ids in ([1, 1], [0], [True], ["1"], [-1]):
            with self.subTest(ids=ids):
                releases = [{"id": i, "draft": False, "prerelease": False, "assets": []}
                            for i in ids]
                result = self.run_inventory([releases])
                self.assertEqual(result["release_metadata_access"], "FAILED_OR_INCOMPLETE")
                self.assertIsNone(result["release_count"])

    def test_duplicate_or_invalid_asset_ids_fail_closed(self):
        for ids in ([1, 1], [0], [True], ["1"]):
            with self.subTest(ids=ids):
                release = {"id": 1, "draft": False, "prerelease": False,
                           "assets": [{"id": i} for i in ids]}
                self.assertIsNone(self.run_inventory([[release]])["asset_count"])

    def test_malformed_pagination_and_records_fail_closed(self):
        for pages in ([], {}, [None], [42], [[None]], [[{}]],
                      [[{"id": 1, "draft": 1, "prerelease": False, "assets": []}]],
                      [[{"id": 1, "draft": False, "prerelease": False, "assets": None}]]):
            with self.subTest(pages=pages):
                result = self.run_inventory(pages)
                self.assertEqual(result["release_metadata_access"], "FAILED_OR_INCOMPLETE")
                self.assertIsNone(result["release_count"])

    def test_page_and_asset_budgets_fail_closed(self):
        original_pages, original_assets = module.MAX_PAGES, module.MAX_ASSETS
        try:
            module.MAX_PAGES = 1
            self.assertIsNone(self.run_inventory([[], []])["release_count"])
            module.MAX_PAGES = original_pages
            module.MAX_ASSETS = 1
            release = {"id": 1, "draft": False, "prerelease": False,
                       "assets": [{"id": 1}, {"id": 2}]}
            self.assertIsNone(self.run_inventory([[release]])["asset_count"])
        finally:
            module.MAX_PAGES, module.MAX_ASSETS = original_pages, original_assets

    def test_release_record_budget_fails_closed(self):
        original = module.MAX_RELEASES
        try:
            module.MAX_RELEASES = 1
            releases = [{"id": i, "draft": False, "prerelease": False, "assets": []}
                        for i in (1, 2)]
            result = self.run_inventory([releases])
            self.assertEqual(result["release_metadata_access"], "FAILED_OR_INCOMPLETE")
            self.assertIsNone(result["release_count"])
            self.assertEqual(result["assessment"], "INCOMPLETE")
        finally:
            module.MAX_RELEASES = original

    def test_unencodable_unicode_response_fails_closed(self):
        def runner(command, **kwargs):
            return subprocess.CompletedProcess(command, 0, "\ud800", "")
        result = module.inventory("OXY7O/KAORI", runner)
        self.assertEqual(result["release_metadata_access"], "FAILED_OR_INCOMPLETE")
        self.assertIsNone(result["release_count"])

    def test_response_size_budget_fails_closed(self):
        original = module.MAX_RESPONSE_BYTES
        try:
            module.MAX_RESPONSE_BYTES = 2
            result = self.run_inventory([[]])
            self.assertIsNone(result["release_count"])
        finally:
            module.MAX_RESPONSE_BYTES = original

    def test_api_failure_timeout_and_missing_cli_do_not_leak_diagnostics(self):
        def failed(command, **kwargs):
            return subprocess.CompletedProcess(command, 1, "", "private stderr")
        def timeout(command, **kwargs):
            raise subprocess.TimeoutExpired(command, 30)
        def missing(command, **kwargs):
            raise FileNotFoundError("private executable path")
        for runner in (failed, timeout, missing):
            with self.subTest(runner=runner.__name__):
                result = module.inventory("OXY7O/KAORI", runner)
                self.assertEqual(result["release_metadata_access"], "FAILED_OR_INCOMPLETE")
                self.assertNotIn("private", json.dumps(result))

    def test_duplicate_json_keys_fail_closed_at_any_depth(self):
        payloads = [
            '[[{"id":1,"id":2,"draft":false,"prerelease":false,"assets":[]}]]',
            '[[{"id":1,"draft":false,"prerelease":false,"assets":[{"id":10,"id":11}]}]]',
            '[[{"id":1,"draft":false,"draft":true,"prerelease":false,"assets":[]}]]',
        ]
        for payload in payloads:
            with self.subTest(payload=payload):
                def runner(command, **kwargs):
                    return subprocess.CompletedProcess(command, 0, payload, "")
                result = module.inventory("OXY7O/KAORI", runner)
                self.assertEqual(result["release_metadata_access"], "FAILED_OR_INCOMPLETE")
                self.assertIsNone(result["release_count"])
                self.assertEqual(result["assessment"], "INCOMPLETE")

    def test_nonstandard_json_constants_fail_closed_at_any_depth(self):
        for constant in ("NaN", "Infinity", "-Infinity"):
            for payload in (
                f"[[{{\"id\":1,\"draft\":false,\"prerelease\":false,\"assets\":[],\"extra\":{constant}}}]]",
                f"[[{{\"id\":1,\"draft\":false,\"prerelease\":false,\"assets\":[{{\"id\":2,\"extra\":{constant}}}]}}]]",
            ):
                with self.subTest(constant=constant, payload=payload):
                    def runner(command, **kwargs):
                        return subprocess.CompletedProcess(command, 0, payload, "")
                    result = module.inventory("OXY7O/KAORI", runner)
                    self.assertEqual(result["assessment"], "INCOMPLETE")
                    self.assertEqual(result["release_metadata_access"], "FAILED_OR_INCOMPLETE")
                    self.assertIsNone(result["release_count"])

    def test_invalid_repository_rejected_before_runner(self):
        def runner(*args, **kwargs):
            self.fail("runner must not be called")
        for repo in ("../repo", "owner/..", "owner/repo/extra", "owner repo/name", ""):
            with self.subTest(repo=repo):
                with self.assertRaises(ValueError):
                    module.inventory(repo, runner)


if __name__ == "__main__":
    unittest.main()
