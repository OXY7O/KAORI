# Domain 15 — Decision Candidate Review and Promotion

## Purpose

Persist alert-to-runbook matches as reviewable, non-executable candidates. A candidate cannot authorize, dispatch, or invoke a resolver. Promotion is an explicit, attributed transition into the existing immutable decision workflow.

## State model

`pending -> promoted | dismissed | expired`

Terminal states cannot be reopened. A promoted candidate links to exactly one `IntelligenceDecision`.

## Safety contracts

- Candidate payload stores `executable=false`.
- Duplicate alerts are suppressed using a SHA-256 key over binding, alert fingerprint, revision, and evidence hash.
- Promotion revalidates binding lifecycle, published revision, action/resolver identity, content hash, and evidence hash.
- The resulting policy may be stricter than the runbook policy, never weaker.
- Promotion calls `create_decision_snapshot()` and `persist_decision()` only.
- Candidate code does not issue tokens, enqueue Celery delivery, or call resolver adapters.
- Expired candidates cannot be promoted.

## Deployment

Apply migration `20260723_candidate_review` after `20260723_alert_runbook_matching`. Run focused intelligence and contract tests before enabling candidate review routes.

## Rollback

Stop candidate creation and review, export pending/promoted candidate evidence, then downgrade to `20260723_alert_runbook_matching`. Decisions already promoted remain intact, but their candidate attribution is removed by downgrade.
