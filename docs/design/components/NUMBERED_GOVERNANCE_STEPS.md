# KAORI Numbered Governance Steps

## Purpose

`components/numbered_governance_steps.html` is the shared non-arrow sequence for governance workflows where ordering matters but the UI should read like the existing KAORI boundary/lifecycle cards.

Use it for short operator-facing sequences such as Tenant Setup, Membership, and Access Grant governance.

## Visual contract

- numbered cards, not connector arrows;
- shared Violet icon treatment;
- one concise title and one short operational description per step;
- contiguous card geometry using `bg-outline-subtle` separators;
- responsive 2-column fallback and an explicit 3/4/5-column desktop layout.

## Semantics

The sequence communicates **order**, not asynchronous job progress. Do not use it as a progress tracker or imply a completed state from the step number alone.

For mutable execution progress, use the existing job/progress/status components instead.
