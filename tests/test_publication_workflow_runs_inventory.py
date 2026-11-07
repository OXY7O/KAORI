"""Regression coverage for sanitized workflow-run metadata inventory (#4212)."""
import importlib.util
import json
import subprocess
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "publication_workflow_runs_inventory.py"
spec = importlib.util.spec_from_file_location("publication_workflow_runs_inventory", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class WorkflowRunInventoryTests(unittest.TestCase):
    def run_inventory(self, pages, returncode=0):
        def runner(command, **kwargs):
            self.assertEqual(command[:4], ["gh", "api", "--paginate", "--slurp"])
            self.assertEqual(kwargs["timeout"], 30)
            return subprocess.CompletedProcess(command, returncode, json.dumps(pages), "")
        return module.inventory("OXY7O/KAORI", runner)

    def test_counts_without_disclosing_names_or_urls(self):
        pages = [{"total_count": 2, "workflow_runs": [{"id": 1, "name": "private", "logs_url": "https://private.invalid"}]},
                 {"total_count": 2, "workflow_runs": [{"id": 2}]}]
        result = self.run_inventory(pages)
        self.assertEqual(result["run_count"], 2)
        self.assertEqual(result["assessment"], "INCOMPLETE")
        self.assertNotIn("private", json.dumps(result))
        self.assertNotIn("logs_url", json.dumps(result))

    def test_empty_valid_inventory(self):
        result = self.run_inventory([{"total_count": 0, "workflow_runs": []}])
        self.assertEqual(result["run_count"], 0)

    def test_partial_pagination_fails_closed(self):
        result = self.run_inventory([{"total_count": 3, "workflow_runs": [{"id": 1}]}])
        self.assertIsNone(result["run_count"])

    def test_duplicate_and_invalid_ids_fail_closed(self):
        for ids in ([1, 1], [0, 2], [True, 2]):
            with self.subTest(ids=ids):
                result = self.run_inventory([{"total_count": 2, "workflow_runs": [{"id": i} for i in ids]}])
                self.assertIsNone(result["run_count"])

    def test_inconsistent_total_fails_closed(self):
        result = self.run_inventory([{"total_count": 2, "workflow_runs": [{"id": 1}]},
                                     {"total_count": 3, "workflow_runs": [{"id": 2}]}])
        self.assertIsNone(result["run_count"])

    def test_api_failure_fails_closed(self):
        result = self.run_inventory([], returncode=1)
        self.assertEqual(result["run_metadata_access"], "FAILED_OR_INCOMPLETE")

    def test_invalid_repository_never_invokes_runner(self):
        for value in ("../KAORI", "OXY7O/..", "OXY7O/KAORI;id", None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    module.inventory(value, lambda *a, **k: self.fail("runner invoked"))


if __name__ == "__main__":
    unittest.main()
