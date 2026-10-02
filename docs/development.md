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
uv run --locked --project scripts python scripts/check_doc_links.py
cd backend
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
cd ../frontend
npm run check
npm run format:check
npm run build
```

The documentation check scans all Git-tracked `.md` files, checks local files and
GitHub-style heading anchors (including duplicate headings and explicit HTML
IDs), and reports failures as `file:line`. It parses Markdown links, images, and
reference links; fenced/indented code and inline code examples are ignored.
External URLs are skipped without network requests. Root-relative paths start at
the repository root; URL-encoded paths/anchors are decoded. Fragments on non-Markdown
files and raw HTML links are not checked. Add new Markdown files to Git before
running the check. Run the checker's focused tests from the repository root with:

```sh
uv run --locked --project scripts python -m unittest discover -s scripts/tests -v
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
same layer remain independent. Components own their layout; shared styles contain
design tokens, typography, and reusable controls.

```text
frontend/src/
├── app/                     # Composition, authentication lifecycle, style entry point
├── pages/board/             # Board workflows, dialogs, shortcut registry
├── widgets/
│   ├── board/               # Board state, columns, search, and contextual task actions
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
│   ├── styles/              # Semantic design tokens and shared control styles
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

#### Design foundations

The visual system is centralized in `frontend/src/shared/styles/`:

- `tokens.css` owns semantic colors, surface levels, fonts, type sizes, spacing,
  control heights, radii, shadows, and motion settings. Change these tokens to
  tune the design across the application.
- `base.css` owns global typography, native form controls, focus indicators, and
  reusable classes such as `.primary`, `.quiet`, `.error`, and `.dialog-actions`.
- `app/styles.css` imports both once, through `main.ts`. Shared styles never import
  from higher FSD layers. Reusable interactive components live in `shared/ui/`.

Use semantic tokens in component styles (`var(--surface-card)`,
`var(--text-secondary)`, `var(--space-3)`) rather than introducing local palettes.
Keep component-specific dimensions, grids, and responsive layout in the owning
slice. Default controls use `--control-height`; explicitly compact controls may
use `--control-height-compact`.

The design uses clear surface hierarchy, compact controls, and purposeful motion,
implemented with Svelte and CSS.
Hover is a preview; selected tasks retain their inset marker and keyboard focus
uses a separate outline. Never delay focus or selection for an animation. Motion
uses the shared timing tokens, which become zero under reduced-motion preferences;
dialog entrance animation is enabled only when motion is allowed. Native modal
focus handling and keyboard shortcuts remain part of component behavior.

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
