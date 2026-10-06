# Modal and Drawer Standard

Titles use Title Case and 16–18 px semibold. Supporting copy uses sentence case. Primary and secondary actions follow the global button contract; destructive confirmation uses critical semantics.

Drawers are preferred for operational detail and inspection. Modals are preferred for focused confirmation or short workflows. Do not duplicate full page navigation inside either component.

## Destructive confirmation contract

Use a KAORI modal for deleting or detaching persisted objects. Browser-native `confirm()` prompts are prohibited.

A destructive confirmation must include:

- a critical semantic icon surface;
- a precise Title Case question;
- the affected object name;
- one concise consequence statement;
- an explicit irreversible-action statement when applicable;
- Cancel and one critical confirmation action;
- Escape and backdrop close behavior;
- focus returned to the original trigger after cancellation.

The UI confirmation never replaces server-side lifecycle checks. Binding blockers, last-owner rules, or other authority boundaries must be enforced again in the service layer.

## Reduced motion

Shared modal/drawer geometry and focus behavior remain identical when `prefers-reduced-motion: reduce` is active. Slide/fade transitions are suppressed and JavaScript must not retain transition-only close delays. The surface still opens, closes, restores focus where its accessibility contract requires it, and preserves all state/evidence semantics.
