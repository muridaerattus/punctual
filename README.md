# Punctual

Lightweight, keyboard-first kanban for humans and agents. Svelte frontend,
FastAPI/FastMCP backend, SQLite through SQLAlchemy, Alembic migrations, and an
HTTP-based CLI. Separate boards have stable ticket keys and one-level subtasks.
MIT licensed.

## Run locally

Requires Python 3.13+, [uv](https://docs.astral.sh/uv/), and Node 22.12+.
From the repository root:

```sh
cd frontend
npm ci
npm run build
cd ../backend
uv sync --locked
export PUNCTUAL_API_KEY='your-shared-key'
uv run python main.py
```

Open **http://localhost:8000** and enter the same API key. FastAPI serves the built
frontend. Press **?** on the board for keyboard shortcuts.

## Documentation

- [Board usage](docs/usage.md): boards, ticket keys, keyboard shortcuts, and editing.
- [CLI](docs/cli.md): installation, commands, output, and exit codes.
- [HTTP API](docs/api.md): endpoints, authentication, revisions, and leases.
- [MCP](docs/mcp.md): agent workflow, client setup, OpenCode, and diagnostics.
- [Deployment](docs/deployment.md): configuration, Docker, VPS deployment, and backups.
- [Development](docs/development.md): live reload, checks, architecture, and migrations.

Contributor guidance is in [AGENTS.md](AGENTS.md).
