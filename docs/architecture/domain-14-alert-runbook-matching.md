# Domain 14 — Alert-to-Runbook Matching and Decision Candidate Generation

## Objective

Domain 14 deterministically maps an alert or KAORI intelligence rule to one immutable published runbook revision. The output is a preview-only `DecisionCandidate`; it is never an execution authorization.

## Flow

`Alert → active binding selectors → one published revision → evidence extraction → non-executable candidate → human/policy decision boundary`

## Safety contracts

- Bindings target a concrete published revision, not a mutable runbook identity.
- Rule, alertname, cluster, namespace, and required labels are exact-match selectors.
- Lowest numeric priority wins; multiple winners at the same priority fail as ambiguous.
- Required evidence is extracted before candidate creation; missing evidence fails closed.
- Candidate evidence is read-only and the candidate exposes `executable=False`.
- Domain 14 does not persist an `IntelligenceDecision`, issue a token, enqueue Celery, or invoke a resolver.

## Deployment

Apply migration `20260723_alert_runbook_matching` after `20260723_runbook_validation`, then run focused Knowledge tests and architecture checks.

## Validation

```bash
pytest -q tests/knowledge/test_alert_runbook_matching.py tests/contracts/knowledge/test_domain14_alert_runbook_matching_contract.py
python scripts/verify_architecture_boundaries.py
```

## Rollback

Disable binding writes, export binding definitions and audit evidence, verify no authoring process depends on them, then downgrade to `20260723_runbook_validation`. Existing runbooks, revisions, decisions, approvals, and execution journals remain intact.
