# Settings template convention

Each Settings subpage should use this structure:

```text
settings/<section>/index.html
settings/<section>/partials/_hero.html
settings/<section>/partials/_*.html
```

Routes should render `settings/<section>/index.html` so page-level layout stays thin and reusable UI pieces live under `partials/`.
