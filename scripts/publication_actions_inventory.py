#!/usr/bin/env python3
"""Read-only, sanitized GitHub Actions artifact inventory for #4212.

Counts only accessible, currently retained artifact metadata. This is NOT a
historical artifact/log review, content scan, rights clearance or GO decision.
"""
import argparse
import json
import re
import subprocess


def inventory(repository, runner=subprocess.run):
    if (not isinstance(repository, str) or
            not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) or
            any(part in (".", "..") for part in repository.split("/"))):
        raise ValueError("invalid owner/repository")
    command = ["gh", "api", "--paginate", "--slurp",
               f"repos/{repository}/actions/artifacts?per_page=100"]
    try:
        result = runner(command, capture_output=True, text=True, check=False, timeout=30)
        if result.returncode != 0:
            raise RuntimeError("API failed")
        pages = json.loads(result.stdout)
        if not isinstance(pages, list) or not pages:
            raise ValueError("invalid pagination")
        artifacts = []
        declared_total = None
        for page in pages:
            if not isinstance(page, dict) or not isinstance(page.get("artifacts"), list):
                raise ValueError("invalid artifact page")
            total = page.get("total_count")
            if not isinstance(total, int) or isinstance(total, bool) or total < 0:
                raise ValueError("invalid total_count")
            if declared_total is not None and total != declared_total:
                raise ValueError("inconsistent total_count")
            declared_total = total
            entries = page["artifacts"]
            if any(not isinstance(item, dict) or
                   not isinstance(item.get("expired"), bool) for item in entries):
                raise ValueError("invalid artifact entries")
            artifacts.extend(entries)
        if len(artifacts) != declared_total:
            raise ValueError("incomplete artifact pagination")
        # An artifact may be listed more than once only if the upstream API
        # pagination is inconsistent. Fail closed instead of silently double-counting.
        ids = [a.get("id") for a in artifacts]
        if any(not isinstance(i, int) or isinstance(i, bool) or i <= 0 for i in ids) or len(ids) != len(set(ids)):
            raise ValueError("missing or duplicate artifact IDs")
    except (OSError, RuntimeError, ValueError, TypeError, subprocess.TimeoutExpired):
        return {"repository": repository, "assessment": "INCOMPLETE",
                "artifact_metadata_access": "FAILED_OR_INVALID",
                "artifact_count": None, "expired_count": None,
                "limitations": "Artifact metadata inaccessible or incomplete; no clearance"}
    return {"repository": repository, "assessment": "INCOMPLETE",
            "artifact_metadata_access": "READ",
            "artifact_count": len(artifacts),
            "expired_count": sum(a["expired"] for a in artifacts),
            "limitations": "Accessible metadata only; expired/deleted artifacts, workflow logs, content, secrets and rights not reviewed"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repositories", nargs="+")
    args = parser.parse_args()
    print(json.dumps([inventory(repo) for repo in args.repositories], indent=2))


if __name__ == "__main__":
    main()
