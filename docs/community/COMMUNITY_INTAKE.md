# Community feedback intake (pre-launch)

**Authority:** [KAORI issue #4217](https://github.com/OXY7O/KAORI/issues/4217), under [governance roadmap #4211](https://github.com/OXY7O/KAORI/issues/4211). This guide describes maintainer triage; it does **not** activate GitHub Discussions, approve publication, or alter GitHub Project fields.

## Entry points and status

- [GitHub Issues](https://github.com/OXY7O/KAORI/issues) are the governed engineering backlog **only after maintainer acceptance**. Search existing issues before proposing new work.
- [GitHub Discussions](https://github.com/OXY7O/KAORI/discussions) is the proposed public feedback route, **pending administrator enablement and launch approval**. Do not advertise it as active until verified.
- For suspected vulnerabilities, **do not open a public issue or Discussion containing exploit details, credentials, or affected private infrastructure**. Use the repository's private vulnerability reporting when enabled; if unavailable, use the maintainer-approved private contact route. Never post secrets in public channels.
- Organization-wide contributor and support defaults are being reviewed in [OXY7O/.github issue #2](https://github.com/OXY7O/.github/issues/2); local repository instructions and its current license take precedence.

## Maintainer triage

1. **Classify** incoming feedback as question, idea, reproducible defect, security concern, or external code proposal. Redirect security concerns to private intake before public discussion.
2. **Deduplicate** against existing KAORI issues and accepted work. Ask for a minimal, sanitized reproduction when needed; do not request credentials, tokens, or private logs.
3. **Assess** fit, rights, operational risk, maintenance cost, and dependencies. Feedback is not a commitment to implement, support, or ship SaaS functionality.
4. **Accept or decline** with a concise rationale. Only accepted work receives an issue linked to the existing parent/dependency, using established labels and GitHub Project native Type, Status, Priority, Story Points, Sprint and ownership fields. Do not invent parallel planning metadata in issue bodies.
5. **Implement** on an issue-linked branch. The temporary `kaori/review/staging-uat` branch is a DevContainer exploratory UAT holding lane, **not** the official admission or release baseline. Official `kaori/staging` admission requires exact-head checks, review, and human acceptance under [delivery workflow](engineering/KAORI_DELIVERY_WORKFLOW.md).
6. **Close the feedback loop** with the accepted issue or documented decline. A holding merge never implies UAT PASS or closes an issue awaiting acceptance.

## Launch verification (not yet complete)

- [ ] Administrator verifies Discussions is enabled and appropriate categories exist.
- [ ] Private vulnerability reporting route is tested without publishing sensitive information.
- [ ] Organization community policies and repository-specific instructions are accepted.
- [ ] Maintainer demonstrates triage of one harmless test Discussion into existing issue taxonomy without creating duplicate work.
- [ ] Maintainer explicitly approves public contribution launch.

No public response-time SLA, external contributor acceptance, security feature activation, or SaaS availability is implied by this document.
