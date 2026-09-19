# Domain 7 Intelligence Test Fixture Hotfix

## Problem

The functional test supplied empty dictionaries for enabled recommendation rules. The production builders intentionally treat an empty rule mapping as absent and return before querying inventory, so the generation-filter capture was never reached.

## Change

The test now supplies minimal truthy rule mappings containing each rule's `rule_key`. This exercises the real enabled-rule path while keeping query results empty and avoiding unrelated finding construction.

## Scope

Test-only change. No production code, database schema, migration, runtime behavior, or deployment configuration changes.

## Validation

```bash
pytest -q \
  tests/intelligence/test_current_generation_recommendations.py \
  tests/contracts/intelligence/test_domain7_current_generation_contract.py
```

## Rollback

Revert the test and this document, or revert the associated Git commit.
