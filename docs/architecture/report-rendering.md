# KAORI Report Rendering

## Purpose

The Report Template System is the canonical definition of report type, selected sections, section order, scope, schedule, artifact storage, and retention. KAORI uses one PDF implementation so report generation has one runtime contract, one failure path, and one operational support model.

## Canonical runtime flow

```text
Report / ReportTemplate configuration
        -> prepared report payload collector
        -> canonical ReportDocument view model
        -> Jinja PDF template
        -> dedicated print CSS
        -> WeasyPrint PDF artifact
        -> configured local or S3-compatible storage
```

The renderer does not query Kubernetes, Prometheus, Alertmanager, or other providers from templates. Collection completes before HTML rendering begins.

## Engine policy

- WeasyPrint is the only PDF engine supported by KAORI.
- There is no runtime engine selector and no second-engine fallback.
- A render failure keeps the previous ready artifact when one exists, records technical evidence in worker logs, and returns sanitized operational feedback to the user.
- Renderer readiness is established through dependency installation, container system libraries, template contracts, and generation tests.

## Template compatibility

System and custom templates continue to store the same `report_type` and ordered `sections` list. The HTML/PDF document builder resolves those sections against the prepared report payload and renders only the selected sections. No report-record schema migration is required for the engine retirement.

## Security and asset policy

- PDF HTML does not fetch remote assets.
- The renderer uses local Jinja templates and local print CSS.
- Secrets, credentials, raw tracebacks, and internal endpoint details are filtered from report presentation.
- Source limitations are disclosed as user-friendly data-quality findings.

## Validation and recovery

Before production rollout:

1. Generate every system template with representative data.
2. Verify cover, table of contents, bookmarks, repeating table headers, page numbering, charts, and long-table pagination.
3. Compare report values against the prepared source payload and the corresponding KAORI workspace.
4. Verify local and S3-compatible storage save, read, download, and outage behavior.
5. Verify failed regeneration retains an existing ready artifact.
6. Roll back the application release if a renderer defect is discovered; do not switch engines at runtime.
