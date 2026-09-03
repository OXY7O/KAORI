# RC Tag Reuse RED Evidence

This file records the intended TDD checkpoint for Issue #138.

## Candidate

- Branch: `kaori/bug-138-rc-tag-reuse`
- Base authority: admitted `kaori/staging` SHA `5ab3242dbbdf3218f92218d19f76576ca17051ad`
- Production workflow remains unchanged at this checkpoint.
- New contract: `test_rc_publish_reserves_tag_and_refuses_registry_tag_reuse`

## Expected RED

The canonical Developer Check must fail because `.github/workflows/publish-staging-image.yml` does not yet contain:

- durable RC Git tag reservation before registry mutation;
- monotonic handling for an incomplete reserved RC tag;
- a pre-push registry existence check preventing overwrite.

No unrelated failure is acceptable as RED evidence.
