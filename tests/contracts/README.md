# Architecture contract tests

This suite validates code ownership, dependency direction, canonical paths, and retired boundaries. Contract tests are useful guardrails, but they are not evidence that a user-facing function works.

Run separately:

```bash
pytest -q tests/contracts -m contract
```
