"""Regression tests for sanitized release inventory pagination (#4212)."""
import importlib.util
import json
import unittest
from pathlib import Path
from types import SimpleNamespace

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "publication_release_inventory.py"
spec = importlib.util.spec_from_file_location("publication_release_inventory", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def runner_for(pages, returncode=0):
    def run(command, **kwargs):
        assert command[:3] == ["gh", "api", "--paginate"]
        return SimpleNamespace(returncode=returncode, stdout=json.dumps(pages))
    return run


class ReleaseInventoryTests(unittest.TestCase):
    def test_valid_paginated_metadata_is_counted_without_names(self):
        pages = [[{"id": 1, "name": "private-name", "assets": [{"id": 7, "name": "private.zip"}]}],
                 [{"id": 2, "assets": []}]]
        output = module.inventory("OXY7O/KAORI", runner_for(pages))
        self.assertEqual((output["release_count"], output["asset_count"]), (2, 1))
        self.assertEqual(output["assessment"], "INCOMPLETE")
        self.assertNotIn("private", json.dumps(output))

    def test_duplicate_release_id_fails_closed(self):
        pages = [[{"id": 1, "assets": []}], [{"id": 1, "assets": []}]]
        self.assertEqual(module.inventory("OXY7O/KAORI", runner_for(pages))["release_metadata_access"], "INVALID")

    def test_duplicate_asset_id_fails_closed(self):
        pages = [[{"id": 1, "assets": [{"id": 7}, {"id": 7}]}]]
        self.assertEqual(module.inventory("OXY7O/KAORI", runner_for(pages))["release_metadata_access"], "INVALID")

    def test_malformed_asset_id_fails_closed(self):
        pages = [[{"id": 1, "assets": [{"id": True}]}]]
        self.assertEqual(module.inventory("OXY7O/KAORI", runner_for(pages))["release_metadata_access"], "INVALID")

    def test_cli_unavailable_fails_closed(self):
        def missing(*args, **kwargs):
            raise FileNotFoundError("gh")
        self.assertEqual(module.inventory("OXY7O/KAORI", missing)["release_metadata_access"], "FAILED")

    def test_invalid_repo_rejected(self):
        with self.assertRaises(ValueError):
            module.inventory("OXY7O/KAORI;echo injected", runner_for([]))


if __name__ == "__main__":
    unittest.main()
