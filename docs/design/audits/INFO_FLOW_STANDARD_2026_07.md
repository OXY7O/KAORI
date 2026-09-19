# Info Flow Standardization Audit — July 2026

## Scope

This audit compared the existing **Role Assignment Flow** on Roles & Access with the **Alertmanager Scope & Workflow** guidance on Register Alertmanager Instance.

## Finding

The Role Assignment Flow already provided the clearest KAORI pattern for explaining an ordered governance sequence:

- prominent expandable header;
- numbered vertical timeline;
- concise stage titles and descriptions;
- one final boundary note.

Alertmanager Scope & Workflow contained equivalent information, but presented it as independent information cards. That made the relationship between registration, reachability, validation, and scope binding less explicit.

## Standardization performed

A shared component was introduced:

```text
app/templates/components/info_flow.html
```

The following pages now consume it:

```text
app/templates/settings/roles/index.html
app/templates/integrations/observability/alert_source/providers/alertmanager/instance_form.html
```

### Roles & Access

The existing flow was migrated without changing its domain meaning:

1. Permission Catalog.
2. Role Composition.
3. User Management.

The Super Admin emergency-authority boundary remains the final note.

### Register Alertmanager Instance

The page now expresses one ordered operational lifecycle:

1. Register Connection Identity.
2. Verify Reachability.
3. Validate Capabilities.
4. Assign Operational Scope.

The final note clarifies that registration alone does not establish capability readiness or scope eligibility.

## Result

Both modules now share the same:

- geometry;
- typography;
- numbering;
- expandable behavior;
- Title Case treatment;
- flow-wide boundary note;
- responsive vertical layout.

## Guardrail

`tests/ui/test_info_flow_contract.py` prevents the Role Assignment and Alertmanager flows from returning to page-local timeline/card implementations.
