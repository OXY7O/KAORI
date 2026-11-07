"""Regression tests for fail-closed Actions artifact pagination (#4212)."""
import importlib.util
import json
import subprocess
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "publication_actions_inventory.py"
spec = importlib.util.spec_from_file_location("publication_actions_inventory", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fake_runner(pages):
    def run(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, json.dumps(pages), "")
    return run


class ActionsPaginationTest(unittest.TestCase):
    def test_complete_pages_are_counted(self):
        pages = [
            {"total_count": 2, "artifacts": [{"id": 1, "expired": False}]},
            {"total_count": 2, "artifacts": [{"id": 2, "expired": True}]},
        ]
        result = module.inventory("OXY7O/KAORI", fake_runner(pages))
        self.assertEqual(result["artifact_metadata_access"], "READ")
        self.assertEqual(result["artifact_count"], 2)
        self.assertEqual(result["expired_count"], 1)

    def test_incomplete_pages_fail_closed(self):
        result = module.inventory("OXY7O/KAORI", fake_runner([
            {"total_count": 2, "artifacts": [{"id": 1, "expired": False}]}
        ]))
        self.assertEqual(result["artifact_metadata_access"], "FAILED_OR_INVALID")
        self.assertIsNone(result["artifact_count"])

    def test_inconsistent_total_fails_closed(self):
        result = module.inventory("OXY7O/KAORI", fake_runner([
            {"total_count": 2, "artifacts": [{"id": 1, "expired": False}]},
            {"total_count": 3, "artifacts": [{"id": 2, "expired": False}]},
        ]))
        self.assertEqual(result["assessment"], "INCOMPLETE")
        self.assertIsNone(result["artifact_count"])

    def test_missing_total_fails_closed(self):
        result = module.inventory("OXY7O/KAORI", fake_runner([
            {"artifacts": []}
        ]))
        self.assertEqual(result["artifact_metadata_access"], "FAILED_OR_INVALID")


if __name__ == "__main__":
    unittest.main()
