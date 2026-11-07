#!/usr/bin/env python3
"""Sanitized, read-only workflow-run metadata inventory for publication audit #4212.

Counts only accessible retained run metadata; never reads logs or grants clearance.
"""
import argparse
import json
import re
import subprocess


def inventory(repository, runner=subprocess.run):
    if (not isinstance(repository, str)
            or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository)
            or any(part in (".", "..") for part in repository.split("/"))):
        raise ValueError("invalid owner/repository")
    command = ["gh", "api", "--paginate", "--slurp",
               f"repos/{repository}/actions/runs?per_page=100"]
    try:
        result = runner(command, capture_output=True, text=True,
                        check=False, timeout=30)
        if result.returncode:
            raise RuntimeError("API failed")
        pages = json.loads(result.stdout)
        if not isinstance(pages, list) or not pages:
            raise ValueError("invalid pagination")
        runs = []
        total = None
        for page in pages:
            if not isinstance(page, dict) or not isinstance(page.get("workflow_runs"), list):
                raise ValueError("invalid page")
            count = page.get("total_count")
            if type(count) is not int or count < 0 or (total is not None and count != total):
                raise ValueError("invalid total_count")
            total = count
            runs.extend(page["workflow_runs"])
        # GitHub's list-runs API is capped at 1,000 results for some filters.
        # Never present a partial listing as an exhaustive historical count.
        if len(runs) != total:
            raise ValueError("incomplete pagination")
        ids = [r.get("id") for r in runs if isinstance(r, dict)]
        if (len(ids) != len(runs) or any(type(i) is not int or i <= 0 for i in ids)
                or len(ids) != len(set(ids))):
            raise ValueError("invalid or duplicate run IDs")
        # Aggregate only fixed outcome categories. Never emit workflow names, URLs,
        # actor identities, job logs or unrecognized provider-controlled values.
        outcomes = {"success": 0, "failure": 0, "cancelled": 0,
                    "timed_out": 0, "action_required": 0, "other": 0}
        for run in runs:
            conclusion = run.get("conclusion")
            if conclusion is not None and not isinstance(conclusion, str):
                raise ValueError("invalid conclusion")
            key = conclusion if conclusion in outcomes and conclusion != "other" else "other"
            outcomes[key] += 1
    except (OSError, RuntimeError, ValueError, TypeError, subprocess.TimeoutExpired):
        return {"repository": repository, "assessment": "INCOMPLETE",
                "run_metadata_access": "FAILED_OR_INCOMPLETE", "run_count": None, "conclusion_counts": None,
                "limitations": "Metadata unavailable or incomplete; no logs/content/rights clearance"}
    return {"repository": repository, "assessment": "INCOMPLETE",
            "run_metadata_access": "READ", "run_count": len(runs),
            "conclusion_counts": outcomes,
            "limitations": "Retained run metadata only; logs, deleted runs, secrets and rights not reviewed"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repositories", nargs="+")
    args = parser.parse_args()
    print(json.dumps([inventory(repo) for repo in args.repositories], indent=2))


if __name__ == "__main__":
    main()
