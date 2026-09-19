# Domain 12 — Knowledge Base and Versioned Runbook Foundation

## Purpose

KAORI must never execute a mutable wiki page or an unversioned procedure. This domain introduces a stable runbook identity and immutable published revisions that can be locked into a decision snapshot.

## Authority model

- `KnowledgeRunbook` is the stable identity and lifecycle owner.
- `KnowledgeRunbookRevision` owns executable content, evidence requirements, parameter schema, resolver binding, approval policy, steps, rollback metadata, and the canonical content hash.
- `IntelligenceDecision` locks the selected runbook key, revision database identity, public revision identity, semantic version, and content hash.
- Resolver execution continues to use the persisted decision and execution journal from Domains 9–11.

## Lifecycle

`draft → published → withdrawn`

Published content is not edited through the service. A change requires a new revision. Withdrawal prevents new decisions from resolving the revision but does not invalidate historical decisions that already reference it.

Runbook lifecycle is `active`, `deprecated`, or `archived`. Only active runbooks can receive revisions or resolve published content.

## Fail-closed rules

- only draft revisions can be published;
- only published revisions can be resolved for a new decision;
- required evidence keys must exist before decision creation;
- persisted decision creation verifies revision existence, published state, and content hash;
- a mismatched content hash blocks persistence;
- RBAC separates viewing, draft management, and publication.

## Deployment

1. Stop decision creation briefly during migration.
2. Run `flask db heads`; expected head is `20260723_knowledge_runbooks`.
3. Run `flask db upgrade`.
4. Run focused Knowledge and Intelligence tests.
5. Seed runbooks as drafts; review and publish explicitly.
6. Do not enable resolver adapter bindings until the corresponding adapter is registered and dry-run behavior is validated.

## Validation

```bash
pytest -q \
  tests/knowledge/test_versioned_runbook_workflow.py \
  tests/contracts/knowledge/test_domain12_runbook_contract.py \
  tests/intelligence \
  tests/contracts/intelligence
python scripts/verify_architecture_boundaries.py
bash scripts/quality_gate.sh
```

## Rollback

Stop creation of new decisions referencing runbooks, export runbook and decision audit evidence, then:

```bash
flask db downgrade 20260723_resolver_orchestration
```

Downgrade removes runbook tables and the runbook binding columns from decisions. Existing decision, approval, execution, and orchestration records remain, but the explicit runbook-version linkage is lost; export it before rollback.

## Changed files

See `PATCH_MANIFEST.md` in the Domain 12 patch.
