# Debug tests

Temporary reproduction or diagnostic tests belong here and must use the `debug` marker.
They must not be used as release evidence and should be deleted once the defect has a permanent functional regression test.

Run explicitly with:

```bash
pytest -q tests/debug -m debug
```
