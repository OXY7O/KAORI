# KAORI branch rulesets and organization controls — evidence handover (#4216)

**Scope:** OXY7O/KAORI repository. **Status:** PARTIALLY VERIFIED, NOT ACCEPTED. This is an observation record and admin handover, not a request to weaken delivery gates or an assertion of full protection. Website, Docs and organization-wide settings require separate authoritative reads.

## Verified repository ruleset snapshot

Read-only GitHub REST evidence observed 2026-11-06 (Asia/Jakarta): [ruleset 26596521](https://github.com/OXY7O/KAORI/rules/26596521), named `KAORI - Long-lived branch safety`, reports `enforcement=active`, `target=branch`, and includes exactly `refs/heads/main` and `refs/heads/kaori/staging`. Its reported rules are `deletion` and `non_fast_forward`. The response reports no bypass actors and `current_user_can_bypass=never`. This proves only the returned ruleset configuration at observation time; it does **not** prove that direct pushes require a PR, that reviewers are mandatory, that conversations must be resolved, or that required status checks are configured.

| Control / acceptance evidence | Status | Required next verification |
| --- | --- | --- |
| Active branch ruleset for main and official staging | VERIFIED (read-only snapshot) | Re-read ruleset and branch effective policy before acceptance |
| Delete and non-fast-forward restrictions in this ruleset | VERIFIED (configured) | Controlled negative test from a non-bypass actor |
| Required PR review / resolved conversations | NOT VERIFIED | Admin inspect effective rules and legacy protection |
| Exact required check contexts | NOT VERIFIED | Inspect current job names and fork/bot/staging behavior before enforcement |
| Direct-push prevention / merge method policy | NOT VERIFIED | Inspect effective rules and test non-bypass push rejection |
| Tag rules / release integrity / CODEOWNERS | NOT VERIFIED | Verify existing release authority without mutating tags |
| Repository Actions permissions / runner groups / environments | NOT VERIFIED | Admin inspect effective scopes and trusted runner isolation |
| Organization 2FA / app permissions / emergency access | NOT VERIFIED | Organization owner confirms sanitized effective settings |
| Website and Docs repository protections | NOT VERIFIED | Verify separately in each owning repository |

## Admin configuration and validation sequence

1. Inventory effective rulesets **and** legacy branch protection for `main` and `kaori/staging`, including actors, review requirements, merge methods, required status checks, bypass and emergency recovery. Do not infer missing controls from the single ruleset.
2. Keep `kaori/review/staging-uat` as temporary DevContainer UAT holding only. Do not use its merge evidence as official staging admission.
3. Before adding required contexts, confirm exact live check names and event behavior on trusted same-repository issue PRs, untrusted external forks and Dependabot PRs. Fork checks are hosted, read-only feedback; they must not invoke privileged self-hosted runners or grant admission. Avoid permanent pending-check deadlocks.
4. With admin approval, apply missing controls using GitHub Settings or sanctioned authenticated CLI. This document makes **no** settings mutation. Test rejected direct push/force push/deletion from a non-bypass actor, valid reviewed staging integration, and valid main promotion. Retain sanitized timestamps and check-run links.
5. Record maintainer approval and break-glass recovery evidence privately. Never paste tokens, bypass identities, security findings or internal runner details into public issues or Slack.

## Delivery and dependency boundaries

#4214 / [Draft PR #4218](https://github.com/OXY7O/KAORI/pull/4218) requires a real external-fork negative test before fork-sensitive enforcement. #4219 / [Draft PR #4220](https://github.com/OXY7O/KAORI/pull/4220) remains advisory Dependabot intake. #4212 remains NO-GO for license cutover. This handover neither marks those PRs Ready nor authorizes publication, Full Admission, staging merge, deployment, provider mutation, or human UAT acceptance.

The governing workflow remains `docs/engineering/KAORI_DELIVERY_WORKFLOW.md` and the temporary holding exception is #2227. GitHub Project Status, Priority, Type, Story Points, Sprint and native cross-repository relationships must be synchronized on their own authority, not duplicated in issue or PR bodies.
