# Community feedback intake — maintainer triage contract

**Status: pre-launch / maintainer preparation.** This document does not assert that GitHub Discussions, private vulnerability reporting, external contribution acceptance, or public support commitments are enabled. External contribution launch requires explicit maintainer acceptance after #4212 (publication and rights), #4214 (fork-safe validation), #4215 (native security), #4216 (rulesets), and the shared OXY7O/.github policy issue #2.

## One planning authority

GitHub Discussions, when enabled by an administrator, is a feedback and conversation surface—not a substitute for a governed KAORI Issue or GitHub Project. Do not copy Project Status, Priority, Sprint, Story Points, Issue Type, or relationship metadata into Issue bodies. Maintain native metadata and relationships using the existing taxonomy and delivery workflow.

## Maintainer decision path

| Intake | Initial handling | Accepted engineering outcome |
| --- | --- | --- |
| Idea / feature suggestion | Check product direction, duplicates, scope, and existing parent Issue | Link or create one bounded Issue with acceptance criteria and dependencies; refine in the existing Project |
| Reproducible defect | Request sanitized reproduction, version/SHA, expected/actual behavior, and impact | Link existing defect or create scoped child Issue; classify severity using existing labels |
| External pull request | Review rights, provenance, safety, and governing Issue; treat fork CI as feedback only | Adopt approved changes on a maintainer-owned issue-linked branch; run normal trusted gates |
| Usage question | Answer or link existing documentation when feasible | No engineering commitment unless separately accepted as an Issue |
| Vulnerability / credential exposure | **Do not request details publicly**; redirect immediately to the private reporting path in [SECURITY.md](../../SECURITY.md) | Privately triage and coordinate response; publish only sanitized tracking where safe |

For every submission: search for duplicates first, distinguish **acknowledged** from **accepted**, record a concise reason when declining, and avoid promising a support SLA. An accepted Issue must still follow [KAORI Delivery Workflow](../engineering/KAORI_DELIVERY_WORKFLOW.md) and applicable staging/DevContainer UAT boundaries. Fork feedback does not confer trusted CI, staging admission, deployment, or human acceptance.

## Sanitized triage rehearsal (documentation example, NOT an executed Discussion)

This example makes the acceptance boundary reviewable without implying that public Discussions is enabled or that a real contributor was contacted. A maintainer must separately perform and record the live test required by the activation checklist.

| Field | Example evidence / decision |
| --- | --- |
| Intake surface | Hypothetical Idea: "Show the last successful repository inventory refresh" |
| Sanitized reproduction | No credentials, installation IDs, private repository names, API payloads or customer data; describe expected versus observed UI behavior only |
| Duplicate search | Search existing Source Control issues (for example [#4030](https://github.com/OXY7O/KAORI/issues/4030)) before proposing a new issue |
| Classification | Feature suggestion, **acknowledged only**; not an accepted engineering commitment |
| Maintainer decision | Link the existing issue if scope matches; otherwise request refinement or decline with a reason. Do not auto-create a Ready issue |
| Project metadata | Only after explicit acceptance, maintain native Issue Type, Status, Priority, Sprint, Story Points, parent/dependencies and owner in GitHub, not copied into prose |
| Delivery authority | If accepted, issue-scoped work and required checks; exploratory DevContainer review in `kaori/review/staging-uat` does not constitute staging admission |
| Closure evidence | Record the actual Discussion URL, linked issue/decision, sanitized reviewer evidence and date **only when the live rehearsal is performed** |

## Activation checklist (human/admin controlled)

- [ ] Rights/publication review records GO for the relevant repository (#4212).
- [ ] Fork safety and security controls have actual negative-test evidence (#4214/#4215/#4216).
- [ ] Shared organization community policy is accepted (OXY7O/.github#2).
- [ ] Maintainer enables GitHub Discussions and confirms the intended categories: Announcements, Ideas, Q&A, General, Show and Tell.
- [ ] Private vulnerability intake is independently verified; public navigation never directs vulnerability details to Discussions.
- [ ] A sanitized test Discussion is triaged against existing Issue/Project metadata without creating a duplicate.
- [ ] README, contribution and support links are updated only after their actual destinations exist and launch is approved.

Website and Docs maintain their own issue, CI and acceptance authority (OXY7O/kaori-website#136/#137; OXY7O/kaori-docs#74/#75). This document does not authorize cross-repository code changes or a SaaS availability claim.
