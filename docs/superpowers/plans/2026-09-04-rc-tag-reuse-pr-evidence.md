# RC Tag Reuse PR Evidence

## Current phase

TDD RED only. Production workflow is intentionally unchanged until Developer Check proves the new collision-safety contract fails for the expected reason.

## Required progression

1. Open PR to `kaori/staging` from `kaori/bug-138-rc-tag-reuse`.
2. Capture RED Developer Check on exact current branch SHA.
3. Implement only the workflow changes required by Issue #138.
4. Capture GREEN Developer Check on exact final head.
5. Merge to `kaori/staging`.
6. Require fresh Full Admission before any further RC cut.
