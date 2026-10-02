# Working on Punctual

Keep Punctual keyboard-first, agent-first, smooth, and dev-friendly.

## Structure and conventions

- `frontend/src/`: Svelte/TypeScript using Feature-Sliced Design (FSD). Dependencies flow down through
  `app → pages → widgets → features → entities → shared`; keep sibling slices independent.
  Preserve keyboard navigation, dialog focus handling, and useful accessibility labels.
- `backend/punctual/`: FastAPI HTTP routes and FastMCP tools share `TaskService`;
  the CLI calls HTTP. Put domain rules in the service so adapters stay consistent.
- `backend/punctual/db/`: SQLite via SQLAlchemy and Alembic. Use migrations for schema
  changes; preserve existing data, stable board ticket keys, revisions, and lease checks.
- `backend/tests/`: pytest coverage for domain rules, adapters, migrations, and deployment.
- `docs/`: detailed guides. Keep the root README a quick start and documentation index.

## Development and checks

Setup and live reload: [development guide](docs/development.md).
Run the checks relevant to your changes:

```sh
# From the repository root (local Markdown links and anchors)
uv run --locked --project scripts python scripts/check_doc_links.py

# From backend/
uv run pytest -q
uv run ruff check .
uv run ruff format --check .

# From frontend/
npm run check
npm run format:check
npm run build
```

Use `npm run format` for frontend formatting. Keep documentation and examples in
sync with behavior; never commit API keys or lease tokens.

When working a tracked task, choose its board, claim it, update using its revision
and lease token, renew as needed, and release when done. Save a random token before
claiming. See [MCP workflow](docs/mcp.md) and [lease recovery](docs/api.md#recovering-a-lost-claim-response-or-token).

Prefer `get_task_context` for task/parent/subtask context, `find_available_work` for
unclaimed To Do candidates, and `board_overview` for counts. MCP `query_tasks` returns
compact pages (`data.items`, `next_cursor`, `truncated`), not a task array. Use
`start_task` and `complete_task` for atomic status/lease transitions, and
`create_task_tree` for atomic parent/child creation. Save distinct random request IDs
before composite writes and replay identical inputs after a lost response; never
silently replace an expected revision. `get_lease_history` returns forced releases
only. Workflow rules belong in the shared service, not the HTTP/MCP adapters.
Use an exact ticket key or numeric ID for `get_task_context(key=...)` and granular
mutations (`task_id=...`); no preliminary ID lookup is needed. `query_tasks` requires
a board prefix or exact name. Removed MCP tools: `list_tasks`, `get_task`, and
`get_task_by_key`. The HTTP/CLI getters and list endpoints remain available.
