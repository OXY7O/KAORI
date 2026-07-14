# KAORI Welcome

Welcome is the authenticated platform landing page and is not an infrastructure dashboard.

- Every authenticated role can open `/` and `/welcome`; both resolve to `welcome.index`.
- It summarizes KAORI across Kubernetes, Server, and HCI.
- Shortcut visibility is derived from the signed-in user's permissions.
- It must not load live Prometheus, Alertmanager, Kubernetes, Server, or HCI data.
- Shortcut definitions are maintained in `shortcuts.py`.
- Presentation is maintained in `templates/welcome/index.html`.

Do not add asset-specific KPI, capacity, alert, or inventory aggregation to this package.
