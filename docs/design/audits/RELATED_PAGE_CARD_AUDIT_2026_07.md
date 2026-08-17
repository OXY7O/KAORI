# Related Page Card Audit — July 2026

## Scope

The initial audit established the shared Related Page Card from the Permission Catalog relationship on Roles & Access. A placement correction was then completed after reviewing provider landing pages and their contextual subpages.

Reviewed areas:

- Roles & Access;
- Integrations Overview;
- Kubernetes provider landing, registration, edit, and detail pages;
- Prometheus provider landing, registration, configuration, and detail pages;
- Alertmanager provider landing, registration, configuration, and detail pages.

## Final Decision

Related Page Cards are contextual workflow navigation. They are not provider portfolio or registry navigation.

Therefore:

- overview, landing, list, and registry pages do not use the component;
- create, edit, detail, configuration, and validation subpages may use it in the right-side contextual column;
- single-page modules may use it on the main page when no subpage exists.

Integrations Overview was not given a Related Page Card because it is itself the navigation and portfolio summary for provider workspaces.

## Standardized Relationships

| Contextual Workspace | Related Workspace | Relationship |
|---|---|---|
| Roles & Access | Permission Catalog | Roles assign code-backed permission keys. |
| Kubernetes connection workflow | Kubernetes Inventory | Validated connections supply normalized resource context. |
| Prometheus connection workflow | Kubernetes Analytics | Eligible metrics sources supply governed query data. |
| Alertmanager connection workflow | Alert Intelligence | Eligible alert sources supply governed alert lifecycle context. |

## Implementation Result

Removed from provider landing pages:

```text
app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/frontpage.html
app/templates/integrations/prometheus.html
app/templates/integrations/observability/alert_source/providers/alertmanager/frontpage.html
```

Applied to contextual subpages:

```text
app/templates/cluster/add.html
app/templates/cluster/edit.html
app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/detail.html
app/templates/prometheus/instance_form.html
app/templates/prometheus/instance_detail.html
app/templates/prometheus/config.html
app/templates/integrations/observability/alert_source/providers/alertmanager/instance_form.html
app/templates/integrations/observability/alert_source/providers/alertmanager/config.html
app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_detail_configuration.html
```

The Roles & Access exception remains valid.

The action spacing was also corrected in the shared component with a 24 px top gap before the bottom-aligned action.

For detailed placement evidence, see:

```text
docs/design/audits/RELATED_PAGE_CARD_PLACEMENT_AUDIT_2026_07.md
```
