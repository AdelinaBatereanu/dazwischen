# Dazwischen

## Status

Project skeleton only. Implementation will be added in later phases.

## Local development

This project uses `uv` and an existing virtual environment.

```bash
uv sync
uv run pytest
uv run ruff check .
uv run uvicorn app.main:app --reload
```

## Intended structure

- `app/mcp_server.py` — public MCP adapter
- `app/main.py` — application composition
- `app/catalog/` — public catalog construction and registry
- `app/validation/` — candidate tool checks
- `app/routing/` — tool invocation routing
- `app/verticals/` — mocked vertical services
- `app/models/` — shared data contracts
- `tests/`
