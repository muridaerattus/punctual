# Development

[Documentation index](../README.md#documentation)

## Local development

Follow the [quick start](../README.md#run-locally) to install dependencies and build
the frontend. For frontend development, run `npm run dev` in `frontend/`;
Vite proxies `/api` to the backend on port 8000. Backend live reload, from `backend/`
with `PUNCTUAL_API_KEY` set:

```sh
uv run uvicorn punctual.app:create_app --factory --reload
```

## Checks

From the repository root:

```sh
cd backend
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
cd ../frontend
npm run check
npm run format:check
npm run build
```

Tests cover competing claims and edits, persisted leases, expiry/recovery, token
conflicts, parent integrity, HTTP authentication/validation, stateless MCP calls
sharing HTTP locking rules, boards, and migrations.

Frontend source is formatted with Prettier and `prettier-plugin-svelte`. Run
`npm run format` in `frontend/` after editing Svelte, TypeScript, or CSS; production
assets are minified by Vite at build time.

## Source layout

### Frontend

The frontend uses Feature-Sliced Design (FSD). Dependencies flow
downward: **app → pages → widgets → features → entities → shared**. Slices on the
same layer remain independent. Components own their styles; shared styles contain
typography and reusable controls.

```text
frontend/src/
├── app/                     # Composition, authentication lifecycle, shared styles
├── pages/board/             # Board workflows, dialogs, shortcut registry
├── widgets/
│   ├── board/               # Board state, columns, toolbar, task actions, footer
│   └── sidebar/             # Board navigation and identity controls
├── features/
│   ├── authentication/      # Login form and credential state
│   ├── board-creation/      # Board creation dialog
│   ├── task-editor/         # Task/subtask editing and local drafts
│   └── task-deletion/       # Delete confirmation
├── entities/
│   ├── board/               # Board types and API
│   └── task/                # Task types and API, task card, local lease state
├── shared/
│   ├── api/                 # Generic authenticated HTTP client
│   ├── keyboard/            # Shortcut event handling
│   └── ui/                  # Brand, modal, shortcut reference dialog
└── main.ts
```

`app/App.svelte` owns authentication and injects separate task and board APIs plus
lease state into the board page. Both APIs use the same shared HTTP client; the
`entities/board` and `entities/task` slices do not import each other. The board widget
composes them, using numeric board IDs to scope task requests. The board has no
dependency on login/session state. `BoardPage.svelte`
coordinates task dialogs and polling. Shortcut bindings and displayed descriptions
share `pages/board/shortcuts.ts` so the help reference stays aligned with actions.

### Backend

```text
backend/punctual/
├── app.py                   # Application factory and lifecycle
├── config.py                # Centralized PUNCTUAL_* server settings
├── api/                     # HTTP routes, authentication, error responses
├── mcp/                     # MCP tool adapter
├── cli/                     # Commands and HTTP client/output handling
├── tasks/                   # TaskService, input schemas, lease rules, domain errors
└── db/                      # SQLAlchemy base/models, sessions, Alembic migrations
```

HTTP and MCP call the same `TaskService`; the CLI calls HTTP. Database sessions
and migrations are encapsulated in `db/`. Tests are organized by tasks, boards, HTTP,
MCP, CLI, migrations, diagnostics, and deployment, with shared fixtures in
`backend/tests/conftest.py`.

## Database development

SQLAlchemy models live in `backend/punctual/db/models.py`. The task service uses ORM
sessions; `db/session.py` configures SQLite and reserves the writer before lease and
revision checks. Alembic owns schema changes in `backend/punctual/db/migrations/` and
runs `upgrade head` on startup. The initial revision also adopts the compatible
prototype schema while preserving existing tasks and leases.

From `backend/`:

```sh
uv run alembic current
uv run alembic revision --autogenerate -m 'describe schema change'
uv run alembic upgrade head
```

Set `PUNCTUAL_DB` to target a non-default database. Review generated migrations
before applying them. Migration scripts are packaged alongside the application.

Board migration `0003` is automatic and preserves existing task IDs, revisions,
relationships, leases, and `PUN-<id>` keys in the default board. Back up before
upgrading; downgrade is refused if additional boards exist because the old schema
cannot represent their keys. See [backups](deployment.md#backups).
