# Settings UI Reference

This document owns Settings- and Access-specific page composition.

- Two-column forms use `items-start` and self-sized cards.
- A primary configuration card does not stretch solely because the guidance rail is longer.
- Primary form actions and permission disclosures align to the configuration-card content width.
- Complex guidance uses expandable sections and remains closed by default unless immediate visibility is operationally necessary.
- Settings pages consume the global hero, form, label, feedback, and accessibility contracts.


### Account security posture (#5323)

Account preserves Profile, Activity, Credentials and MFA query-backed tabs. Profile presents read-only effective personal MFA policy, idle/absolute session limits and policy-level Remember Me eligibility using committed state; credential ownership remains in the existing identity and credential panels. Activity is an exact-user latest-five committed authentication/password-change projection with allowlisted personal security action labels, not an administrative audit registry. No new navigation, device inventory or global security policy mutation. New candidate visual and runtime evidence is pending.
