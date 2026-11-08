import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.publication_inventory import inventory


class InventoryTests(unittest.TestCase):
    def test_history_includes_deleted_file_without_disclosing_paths(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)

            def git(*args):
                subprocess.run(['git', '-C', d, *args], check=True, capture_output=True)

            git('init', '-q')
            git('config', 'user.name', 'Test')
            git('config', 'user.email', 'test@example.invalid')
            (repo / 'temporary-secret-name.txt').write_text('placeholder')
            git('add', '.')
            git('commit', '-qm', 'first')
            (repo / 'temporary-secret-name.txt').unlink()
            git('add', '-u')
            git('commit', '-qm', 'delete')
            result = inventory(repo)
            self.assertEqual(result['history_commit_count'], 2)
            self.assertEqual(result['tracked_head_file_count'], 0)
            self.assertGreater(result['reachable_history_object_count'], 2)
            self.assertNotIn('temporary-secret-name', str(result))
            self.assertEqual(result['assessment'], 'INCOMPLETE')

    def test_detached_head_commit_is_included_without_exposing_content(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)

            def git(*args):
                return subprocess.run(['git', '-C', d, *args], check=True, capture_output=True).stdout.strip()

            git('init', '-q')
            git('config', 'user.name', 'Test')
            git('config', 'user.email', 'test@example.invalid')
            (repo / 'base.txt').write_text('base')
            git('add', '.')
            git('commit', '-qm', 'base')
            base = git('rev-parse', 'HEAD').decode()
            git('checkout', '--detach', '-q', base)
            (repo / 'private-detached-name.txt').write_text('placeholder')
            git('add', '.')
            git('commit', '-qm', 'detached')
            result = inventory(repo)
            self.assertTrue(result['head_outside_local_refs'])
            self.assertEqual(result['history_commit_count'], 2)
            self.assertGreaterEqual(result['reachable_history_object_count'], 6)
            self.assertNotIn('private-detached-name', str(result))
            self.assertEqual(result['assessment'], 'INCOMPLETE')
