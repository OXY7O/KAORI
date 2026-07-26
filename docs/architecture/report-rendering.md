# KAORI Report Rendering

## Purpose

The Report Template System remains the canonical definition of report type, selected sections, section order, scope, schedule, artifact storage, and retention. WeasyPrint replaces the default visual renderer without creating a parallel report workflow.

## Runtime flow

```text
Report / ReportTemplate configuration
        -> existing report payload collector
        -> canonical ReportDocument view model
        -> Jinja PDF template
        -> dedicated print CSS
        -> WeasyPrint PDF artifact
        -> configured local or S3-compatible storage
```

The renderer does not query Kubernetes, Prometheus, or Alertmanager from templates. Collection completes before HTML rendering begins.

## Renderer selection

- `REPORT_PDF_RENDERER=weasyprint` is the default.
- `REPORT_PDF_RENDERER=reportlab` provides explicit rollback.
- `REPORT_PDF_LEGACY_FALLBACK_ENABLED=true` allows a failed WeasyPrint generation to fall back to the legacy ReportLab renderer.

Technical exceptions are written to application logs. Report status and transient feedback use a user-safe generation message.

## Template compatibility

System and custom templates continue to store the same `report_type` and ordered `sections` list. The HTML/PDF document builder resolves those sections against the existing report payload and renders only the selected sections. No schema migration is required.

## Security and asset policy

- PDF HTML does not fetch remote assets.
- The renderer uses local Jinja templates and local print CSS.
- Secrets, credentials, raw tracebacks, and internal endpoint details are filtered from generic report presentation.
- Source limitations are disclosed as user-friendly data-quality findings.

## Validation and rollback

Before production rollout:

1. Generate each system template with representative data.
2. Verify cover, TOC links, bookmarks, repeating table headers, and page numbering.
3. Compare key values against the legacy artifact or source payload.
4. Verify local and S3 storage paths.
5. Set `REPORT_PDF_RENDERER=reportlab` to roll back rendering without changing report records or templates.
