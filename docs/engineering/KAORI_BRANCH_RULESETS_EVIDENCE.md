# KAORI branch rulesets and organization controls — evidence handover (#4216)

**Scope:** KAORI Application, Website and Docs repository rulesets. **Status:** PARTIALLY VERIFIED, NOT ACCEPTED. Read-only REST observations recorded on 2026-11-08 (Asia/Jakarta); GitHub effective/legacy protection, bypass tests, organization settings and maintainer acceptance are separate. This document does not authorize weaker delivery gates.

## Verified repository ruleset snapshot

GitHub REST ruleset detail reads on **2026-11-08** returned three **active** repository rulesets for each repository, with no bypass actors in the returned ruleset objects. This is **configured policy evidence**, not proof that legacy protection or all effective branch policies were examined or that negative-push tests were performed.

| Repository | Long-lived safety (main + staging) | PR-only integration (main + staging) | Staging status-check contexts |
| --- | --- | --- | --- |
| `OXY7O/KAORI` | [26596521](https://github.com/OXY7O/KAORI/rules/26596521): `deletion`, `non_fast_forward` | [26684718](https://github.com/OXY7O/KAORI/rules/26684718): merge-only PR rule | [26685250](https://github.com/OXY7O/KAORI/rules/26685250): `Developer Check`, `KAORI CI / Admission` |
| `OXY7O/kaori-website` | [26685572](https://github.com/OXY7O/kaori-website/rules/26685572): `deletion`, `non_fast_forward` | [26685631](https://github.com/OXY7O/kaori-website/rules/26685631): merge-only PR rule | [26685877](https://github.com/OXY7O/kaori-website/rules/26685877): `Route Checks`, `Website Validation` |
| `OXY7O/kaori-docs` | [26687947](https://github.com/OXY7O/kaori-docs/rules/26687947): `deletion`, `non_fast_forward` | [26688007](https://github.com/OXY7O/kaori-docs/rules/26688007): merge-only PR rule | [26688106](https://github.com/OXY7O/kaori-docs/rules/26688106): `Route Checks`, `Docs Validation` |

Each PR-only ruleset currently reports `required_approving_review_count: 0`, `required_review_thread_resolution: false`, `dismiss_stale_reviews_on_push: false`, `require_code_owner_review: false`, and `allowed_merge_methods: [merge]`. These configured values **do not enforce human approval**. This is an observed governance gap, not a theoretical or yet-to-be-verified concern. All three staging required-check rulesets report `strict_required_status_checks_policy: false` and `do_not_enforce_on_create: true`. The returned repository rulesets do not include required status checks targeting `main`; legacy branch protection and effective per-branch rules must be checked independently before asserting a main-branch gap or completion.

| Control / acceptance evidence | Status | Required next verification |
| --- | --- | --- |
| Active branch rulesets for `refs/heads/main` and `refs/heads/kaori/staging` | VERIFIED (configured) | Re-read effective per-branch policy at acceptance |
| Delete and non-fast-forward restrictions in all three repositories | VERIFIED (configured) | Controlled rejection test from a non-bypass actor |
| PR-only integration rule and merge-only method | VERIFIED (configured) | Negative direct-push test and effective legacy protection review |
| Required PR review / resolved conversations | GAP VERIFIED (0 approvals; false resolution) | Configure appropriate enforced review and resolution requirement with maintainer consent; check feasibility of independent reviewer |
| Exact required check contexts | VERIFIED (configured for staging) | Confirm actual check identity, fork/bot behavior, and effective branch check before acceptance |
| Direct-push prevention / merge method policy | NOT VERIFIED (effective) | Controlled non-bypass push rejection and merge test; configured rule alone is insufficient |
| `main` required-check enforcement / legacy branch protection | NOT VERIFIED | Inspect effective branch protection; do not infer from repository rulesets alone |
| Tag rules / release integrity / CODEOWNERS | NOT VERIFIED | Verify existing immutable release authority without mutating tags |
| Repository Actions permissions / runner groups / environments | NOT VERIFIED | Admin inspect effective scopes and trusted runner isolation |
| Organization 2FA / app permissions / emergency access | NOT VERIFIED | Organization owner confirms sanitized effective settings |
| Website and Docs repository protections | PARTIALLY VERIFIED (rulesets only) | Inspect legacy/effective branch protection and perform negative tests in each owning repo |

**Administrative change boundary:** The connected repository API provides read access to rulesets but does not authorize GitHub Settings mutations here. An authorized repository administrator must configure missing review/resolve requirements without creating single-maintainer deadlocks, verify exact required-check contexts (including skipped fork/bot runs), preserve native KAORI admission controls, and capture after-state evidence. Do not claim settings have already been changed.

## Required-status skipped-job hazard — remediation pending

GitHub's [official job-condition documentation](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-jobs-with-conditions) explicitly states that a job skipped by a job-level `if` reports **Success**, even as a required check. Its [required-check troubleshooting guidance](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks) also warns that a dependent job skipped after a failed predecessor may not block merging. Required `Developer Check`, `Route Checks`, `Website Validation` and `Docs Validation` must therefore be evaluated by their **actual GitHub check conclusions**, not merely the workflow name, green overall run, or a conditionally skipped path.

| Repository / issue | Code status on 2026-11-08 | Remaining assurance |
| --- | --- | --- |
| Application [#4278](https://github.com/OXY7O/KAORI/issues/4278) / [Draft PR #4239](https://github.com/OXY7O/KAORI/pull/4239) | Hosted `Route Checks` rejects untrusted source **before checkout**; `Developer Check` aggregator is always scheduled and fails when routing is not successful. The change is a **Draft PR to official staging**, not merged or effective on the protected branch | Exact-head Python & Governance, real fork negative test, runner-group verification #4233, Full Admission and human acceptance are PENDING |
| Website [Draft PR #141](https://github.com/OXY7O/kaori-website/pull/141) | Hosted required `Route Checks` fails fork before checkout; privileged Website Validation depends on successful route. Exact-head Developer Check #42426699555 PASS on trusted branch | Real fork negative test, official staged admission, required-check policy after-state and human UAT PENDING |
| Docs [Draft PR #79](https://github.com/OXY7O/kaori-docs/pull/79) | Hosted required `Route Checks` fails fork before checkout; privileged Docs Validation depends on successful route. Exact-head Developer Check #42426754511 PASS on trusted branch | Real fork negative test, official staged admission, required-check policy after-state and human UAT PENDING |

**Controller distinction:** Blocking job execution on a privileged runner and enforcing a failing required check are **different conditions**. A job-level `if` can prevent runner allocation but result in a successful skipped required check; a first-step rejection on a privileged runner can fail but allocate that runner before the trust check. Keep the required policy job hosted and make it **FAIL** for untrusted PR origin before any checkout. This document records prepared source evidence, **not proof of a successful live external-fork attack or negative test**.

**Admin access boundary:** A read-only request for KAORI's legacy `main` branch-protection API returned `403 Resource not accessible by integration`; the connected GitHub API cannot verify effective legacy protection or mutate Rulesets/Project metadata. The required approving reviewer and resolved-conversation gap above remains configured as observed. Require authorized maintainer Settings review and a controlled negative push/PR test; do not silently strengthen reviewer rules without checking independent-review capacity and recovery from a single-maintainer deadlock.

## Admin configuration and validation sequence

1. Inventory effective rulesets **and** legacy branch protection for `main` and `kaori/staging`, including actors, review requirements, merge methods, required status checks, bypass and emergency recovery. Do not infer missing controls from the single ruleset.
2. Keep `kaori/review/staging-uat` as temporary DevContainer UAT holding only. Do not use its merge evidence as official staging admission.
3. Before adding required contexts, confirm exact live check names and event behavior on trusted same-repository issue PRs, untrusted external forks and Dependabot PRs. Fork checks are hosted, read-only feedback; they must not invoke privileged self-hosted runners or grant admission. Avoid permanent pending-check deadlocks.
4. With admin approval, apply missing controls using GitHub Settings or sanctioned authenticated CLI. This document makes **no** settings mutation. Test rejected direct push/force push/deletion from a non-bypass actor, valid reviewed staging integration, and valid main promotion. Retain sanitized timestamps and check-run links.
5. Record maintainer approval and break-glass recovery evidence privately. Never paste tokens, bypass identities, security findings or internal runner details into public issues or Slack.

## Delivery and dependency boundaries

#4214 / [PR #4218](https://github.com/OXY7O/KAORI/pull/4218) and #4219 / [PR #4220](https://github.com/OXY7O/KAORI/pull/4220) were integrated into the **temporary review holding branch** on 2026-11-08; neither merge constitutes official staging admission, external-fork negative testing, Dependabot activation or Human Acceptance. #4212 remains NO-GO for license cutover. This handover neither marks those PRs Ready nor authorizes publication, Full Admission, staging merge, deployment, provider mutation, or human UAT acceptance.

The governing workflow remains `docs/engineering/KAORI_DELIVERY_WORKFLOW.md` and the temporary holding exception is #2227. GitHub Project Status, Priority, Type, Story Points, Sprint and native cross-repository relationships must be synchronized on their own authority, not duplicated in issue or PR bodies.
