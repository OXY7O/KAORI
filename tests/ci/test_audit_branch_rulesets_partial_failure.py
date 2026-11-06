"""Regression for independent effective branch checks after inventory failure (#4216)."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "audit_branch_rulesets.sh"


class BranchRulesetPartialFailureTest(unittest.TestCase):
    def test_list_failure_still_checks_both_branches_and_other_repos(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            calls = temp / "calls.txt"
            mock = temp / "gh"
            mock.write_text(
                "#!/usr/bin/env bash\n"
                'printf "%s\\n" "$*" >> "$CALLS_FILE"\n'
                'if [[ "$*" == "ruleset list --repo OXY7O/KAORI" ]]; then exit 1; fi\n'
                "exit 0\n",
                encoding="utf-8",
            )
            mock.chmod(0o755)
            env = dict(os.environ, PATH=f"{temp}:{os.environ.get('PATH', '')}", CALLS_FILE=str(calls))
            completed = subprocess.run(
                ["bash", str(SCRIPT), "OXY7O/KAORI", "OXY7O/kaori-docs"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 1)
            self.assertIn("INCOMPLETE", completed.stderr)
            self.assertNotIn("INVENTORY COMPLETE", completed.stdout)
            recorded = calls.read_text(encoding="utf-8").splitlines()
            self.assertEqual(
                recorded,
                [
                    "ruleset list --repo OXY7O/KAORI",
                    "ruleset check main --repo OXY7O/KAORI",
                    "ruleset check kaori/staging --repo OXY7O/KAORI",
                    "ruleset list --repo OXY7O/kaori-docs",
                    "ruleset check main --repo OXY7O/kaori-docs",
                    "ruleset check kaori/staging --repo OXY7O/kaori-docs",
                ],
            )


if __name__ == "__main__":
    unittest.main()
