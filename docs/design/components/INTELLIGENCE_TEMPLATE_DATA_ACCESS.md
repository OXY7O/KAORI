# Intelligence Template Data Access

Intelligence presentation payloads are dictionaries. Keys that overlap Python
mapping methods—such as `items`, `keys`, `values`, `get`, `copy`, and `update`—
must use bracket notation in Jinja.

Use:

```jinja
{% for item in payload['items']|default([], true) %}
```

Do not use:

```jinja
{% for item in payload.items %}
```

Jinja resolves the second form to `dict.items`, which is a callable method and
cannot be iterated as a record collection. The same rule applies to nested
objects such as grouped Automation Control domains.
