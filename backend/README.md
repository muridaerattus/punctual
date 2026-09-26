# Punctual backend

FastAPI HTTP endpoints, FastMCP tools, a shared transactional SQLite service, and
the `punctual` CLI. See the [project README](../README.md) for setup and the
[development guide](../docs/development.md) for architecture, checks, and migrations.
Usage references: [HTTP API](../docs/api.md), [MCP](../docs/mcp.md), and [CLI](../docs/cli.md).

```sh
uv sync --locked
export PUNCTUAL_API_KEY='your-shared-key'
uv run python main.py
```

Run tests with `uv run pytest -q`.
