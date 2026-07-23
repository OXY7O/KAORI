# Domain 13 — Runbook Authoring Validation & Resolver Compatibility

## Objective

Prevent KAORI from publishing operational guidance that cannot be safely resolved in the target runtime. A draft is documentation; a published revision is an executable governance contract and therefore requires deterministic validation.

## Publication boundary

`publish_revision()` validates the draft before changing `publication_status` to `published`. The validation evidence is persisted in `publication_validation_json`, together with reviewer identity and review timestamp. A failed review leaves the revision as `draft`.

Validation covers:

- semantic version format and exact patch/minor/major transition;
- closed JSON parameter schema with declared required fields;
- non-empty evidence requirements;
- registered resolver action and matching action identity;
- mandatory `dry_run()` and `execute()` adapter contract;
- required runtime capabilities;
- supported compatibility profiles;
- rollback metadata where the adapter or automatic policy requires it;
- at least one executable step.

## Semantic version rules

Given previous version `1.2.3`:

- patch must become `1.2.4`;
- minor must become `1.3.0`;
- major must become `2.0.0`.

Skipping versions or using non-semantic labels is rejected. This makes the change intent explicit during publication review.

## Parameter schema

The root must be an object and `additionalProperties` must be false. Every required field must exist in `properties`. Runtime values are checked for missing, unknown, and incorrectly typed parameters before resolver dispatch.

## Resolver compatibility

Adapters declare:

- `action_key`;
- `capability_keys`;
- `compatibility_profiles`;
- `rollback_required`;
- callable `dry_run()` and `execute()` methods.

A runbook cannot be published merely because an action string exists. The registered adapter must support the required capability/profile set and rollback boundary.

## Deployment

1. Apply Domains 8–12 first.
2. Stop runbook publication writes.
3. Run `flask db upgrade`.
4. Start the application and resolver workers.
5. Run focused tests and architecture checks.
6. Re-enable publication only after resolver registry bootstrap is available.

## Validation

```bash
pytest -q \
  tests/knowledge/test_runbook_publication_validation.py \
  tests/contracts/knowledge/test_domain13_publication_gate_contract.py

pytest -q tests/knowledge tests/contracts/knowledge tests/resolver tests/contracts/resolver
python scripts/verify_architecture_boundaries.py
bash scripts/quality_gate.sh
```

## Rollback

Stop publication writes, export review evidence, then downgrade:

```bash
flask db downgrade 20260723_knowledge_runbooks
```

Downgrade removes authoring compatibility metadata and publication review evidence, but does not remove the underlying runbooks or revisions.
