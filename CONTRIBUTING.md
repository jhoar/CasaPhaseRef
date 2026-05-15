# Contributing

Run before submitting changes:

```bash
ruff check .
mypy src
pytest -m "not integration"
```

CASA integration tests are optional and require a CASA-capable environment.
