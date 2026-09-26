# Punctual

_It's one fewer dimension!_

Lightweight kanban for humans and agents. Svelte frontend, FastAPI/FastMCP backend,
SQLite storage through SQLAlchemy, Alembic migrations, and an HTTP-based CLI. Separate boards, with tasks and
one-level subtasks. MIT licensed.

## Run locally

Requires Python 3.13+, [uv](https://docs.astral.sh/uv/), and Node 22.12+.

```sh
cd frontend
npm ci
npm run build
cd ../backend
uv sync --locked
export PUNCTUAL_API_KEY='your-shared-key'
uv run python main.py
```

Open **http://localhost:8000** and enter the same API key. The built frontend is
served by FastAPI. For frontend development, run `npm run dev` in `frontend/`;
Vite proxies `/api` to the backend on port 8000. Backend live reload:

```sh
uv run uvicorn punctual.app:create_app --factory --reload
```

## Keyboard first

Press **?** on the board for the complete reference. Shortcuts are disabled while
typing in a field. All controls are also reachable with Tab; dialogs trap focus
and close with Escape.

| Key | Action |
| --- | --- |
| N | New task |
| J / K or ↓ / ↑ | Next / previous card |
| Enter (on card) / E | Open / edit task |
| S | New subtask of selected top-level task |
| 1 / 2 / 3 | Move to To Do / In Progress / Complete |
| C | Claim selected task for 15 minutes |
| R / U | Renew / release your lease |
| X / Delete | Delete, with confirmation |
| / | Focus search |
| G | Refresh |
| O | Focus claim identity |
| Shift L | Sign out |
| Ctrl/Cmd Enter | Save task in editor |
| Escape | Close dialog / clear focused search |

The board refreshes every five seconds, pausing during editing. Revision conflicts
preserve the open draft and show an error; close and reopen to load the new revision.
Parent and subtask statuses are independent.

## CLI

From `backend/`, use `uv run punctual`. Or install the CLI globally with
`uv tool install ./backend` from the repository root.

```sh
export PUNCTUAL_API_KEY='your-shared-key'
export PUNCTUAL_URL='http://localhost:8000'  # default
punctual create 'Ship the first version' --assignee agent-a
punctual list --status 'To Do'
punctual --json get 1
# Generate and retain a random token BEFORE claiming, so a lost response is recoverable.
export PUNCTUAL_LEASE_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
punctual --json claim 1 agent-a --seconds 900
punctual update 1 --revision 1 --status 'In Progress'
punctual renew 1 --seconds 900
punctual update 1 --revision 2 --status Complete
punctual release 1
punctual create 'Write release notes' --parent-id 1
```

Use `punctual --help` or `punctual update --help` for all options. `--json` is a
global flag placed before the command. Output is JSON on stdout in this mode,
including structured errors. Exit codes: **0** success, **1** request/configuration
failure, **2** command usage error, **3** task/revision/lease conflict. Updates and
deletes require an explicit expected revision; the CLI does not silently fetch a
new revision or retry a stale write. `--clear-assignee` and `--clear-parent` unset
those fields. Tokens can also be supplied using `--lease-token`.

## HTTP API

### Boards and ticket keys

Each board has a name and a unique, immutable prefix of 1–8 uppercase ASCII letters
(`^[A-Z]{1,8}$`). Create and select boards in the sidebar. Tasks display stable keys
such as `ENG-12345`; numbering starts at 1 independently in each board, includes
subtasks, and never reuses deleted ticket numbers. Prefixes and task boards cannot
be changed. Parents must belong to the same board; subtasks still support one level.

Existing tasks migrate into board **1**, named **Default**, with prefix **PUN**.
Their keys remain `PUN-<existing numeric ID>`. Numeric IDs, revisions, relationships,
and active leases are preserved. Boards share the instance's authentication;
they organize work rather than define access permissions.

Use `GET /api/boards` and `POST /api/boards` (body: `{"name":"Engineering","prefix":"ENG"}`).
Pass `board_id` when creating or listing tasks; omission selects default board 1.
Resolve a key with `GET /api/tasks/by-key/ENG-1`, then use the returned numeric `id`
for existing edit, delete, and lease endpoints. Task responses include `board_id`,
`number`, `key`, and `parent_key`. Text search also accepts a complete ticket key.
MCP provides `list_boards`, `create_board(board)`, and `get_task_by_key(key)`;
`list_tasks(board_id=...)` and `create_task(task={..., "board_id": ...})` scope work.
CLI listing and creation continue to target the default board; numeric-ID commands
work across boards.

Migration `0003` is automatic. Back up before upgrading; downgrade is refused if
additional boards exist because the old schema cannot represent their keys.

### Endpoints

All `/api/*` and `/mcp/*` calls require `Authorization: Bearer <PUNCTUAL_API_KEY>`.
The API key identifies the trusted group, not individual people. GUI credentials
and owned lease tokens are stored in per-tab session storage. Claim-owner and
assignee names are coordination labels.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/boards` | List boards |
| POST | `/api/boards` | Create with `name`, unique `prefix` |
| GET | `/api/tasks` | List in `board_id` (default 1); optional `status`, `assignee`, `query` filters |
| POST | `/api/tasks` | Create |
| GET | `/api/tasks/{id}` | Read |
| GET | `/api/tasks/by-key/{key}` | Resolve a ticket key |
| PATCH | `/api/tasks/{id}` | Partial update with `revision` and optional `lease_token` |
| DELETE | `/api/tasks/{id}` | JSON body: `revision`, optional `lease_token` |
| POST | `/api/tasks/{id}/claim` | JSON: `owner`, optional `seconds` |
| POST | `/api/tasks/{id}/renew` | JSON: `lease_token`, optional `seconds` |
| POST | `/api/tasks/{id}/release` | JSON: `lease_token` |
| POST | `/api/tasks/{id}/force-release` | JSON: current `revision`, public `lease_id`, and `reason`; overrides a stuck lease |
| GET | `/api/tasks/{id}/lease-history` | Durable forced-release records, retained after task deletion |

```sh
curl http://localhost:8000/api/tasks \
  -H "Authorization: Bearer $PUNCTUAL_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"title":"First task","status":"To Do"}'
```

`/openapi.json`, `/docs`, and `/redoc` are authenticated too; fetch them with the
same bearer header. `/health` is public. Times are Unix seconds. Validation errors
use HTTP 422; domain errors contain `{ "error": { "code": "…", "message": "…" } }`.

### Coordination guarantees

- Unclaimed tasks can be edited or deleted using the matching revision.
- Active leases require the secret token for edits and deletion, plus a matching
  revision. Tokens are returned only by claim and renewal.
- Claims, revision comparisons, lease checks, and mutations occur inside short
  SQLite `BEGIN IMMEDIATE` transactions. Only one concurrent claimant wins.
- Every task edit increments its revision. Claim/renew/release do not change the
  content revision. A claim is independent of status and assignee.
- Leases last 900 seconds by default, configurable from 30 to 86400 seconds. Renew
  before expiry. Expired leases permit direct editing or a new claim; an old token
  cannot renew, release, or mutate a subsequently claimed task.
- Leases survive restarts. There is no transaction held open while an agent works.
- A task with subtasks cannot be deleted until they are deleted or detached.
- SQLite uses WAL, foreign keys, a five-second busy timeout, and versioned startup
  Alembic migrations. Persistent contention returns `database_busy` (503).

### Recovering a lost claim response or token

For agents and retryable clients, generate a cryptographically random token and
save it **before** claiming (for example `secrets.token_urlsafe(32)`). Pass it as
`lease_token` to HTTP `/claim` or MCP `claim_task`, or set `PUNCTUAL_LEASE_TOKEN`
for the CLI. Supplied claim tokens must be 32–100 URL-safe characters. Use a fresh
token for each new claim. Repeating an active claim with the same owner and token
returns the current lease without extending it, including after a server restart.
Owner labels alone cannot recover a token. Store the token durably across agent
tool executions or context resets; exporting it only lasts for that process tree.

If no token was supplied, claiming still generates one server-side. If that token
is lost, any member of the trusted bearer-key group can explicitly force-release:

```sh
punctual --json get 1
# Copy revision and lease_id from that fresh response:
punctual force-release 1 --revision 2 --lease-id '<current-lease-id>' \
  --reason 'Claim response was lost; recovering abandoned work'
punctual lease-history 1
```

MCP offers `force_release_lease(task_id, release)` with the same `revision`,
`lease_id`, and `reason` fields in `release`. It rejects stale task revisions and
replaced or expired leases. Every new claim has a different public lease ID—even
when the same owner claims again—so stale recovery requests cannot clear a newer
claim. Renewal retains that ID. Force-release does not edit task content or change
its revision; fetch again before editing. It invalidates the active token and
records the former owner, lease ID, task revision, time, and reason in SQLite.
The record contains no token and survives task deletion. With shared-key auth,
the reason and owner are labels, not verified individual identities.

### Database development

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

## MCP

Connect a **Streamable HTTP** client to `http://localhost:8000/mcp/` with the same
bearer header. This implementation targets the current **2026-07-28** specification
using FastMCP 4 / MCP SDK 2. Requests are stateless, carry per-request version and
capability metadata, and do not use a session ID or initialization handshake.

Tools: `list_boards`, `create_board`, `get_task_by_key`, `list_tasks`, `get_task`, `create_task`, `update_task`, `delete_task`,
`claim_task`, `renew_lease`, `release_lease`, `force_release_lease`. Tools share exactly the HTTP service
and lock checks. Results have `{ "ok": true, "data": … }` or
`{ "ok": false, "error": { "code": …, "message": … } }`; agents must check `ok`.

SDK client example (run in the backend environment):

```python
import asyncio
import os
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

async def main():
    transport = StreamableHttpTransport(
        'http://localhost:8000/mcp/',
        headers={'Authorization': f"Bearer {os.environ['PUNCTUAL_API_KEY']}"},
    )
    async with Client(transport) as client:
        print(await client.call_tool('list_tasks', {}))

asyncio.run(main())
```

Recommended agent workflow: list → get → claim → update with revision and token →
renew while working → complete → release. An expired lease must be claimed again.

### OpenCode (bearer authentication)

Configure OpenCode V2 in the project's `opencode.json`. Replace the example host
with your server's address; the trailing `/mcp/` is required:

```json
{
  "mcp": {
    "servers": {
      "punctual": {
        "type": "remote",
        "url": "http://localhost:8000/mcp/",
        "protocol": "2026-07-28",
        "oauth": false,
        "headers": {
          "Authorization": "Bearer {env:PUNCTUAL_API_KEY}"
        }
      }
    }
  }
}
```

Provide the existing server key through `PUNCTUAL_API_KEY` in the environment of
the **OpenCode background service**. Exporting it in another terminal does not
update an already-running service. Restart OpenCode's service from the environment
containing the key (`opencode service restart`), then reconnect through `/mcps`
and check `opencode mcp list`. Do not commit the key to configuration. Punctual
uses a shared bearer key, so OAuth registration must be disabled.

For this example, set `PUNCTUAL_ALLOWED_HOSTS=localhost:8000` on the **Punctual
server**. Preserve other allowed hosts as comma-separated values. Docker
environment changes require recreating the container, not just `docker restart`.

### Connection diagnostics

From `backend/`, with `PUNCTUAL_API_KEY` set:

```sh
uv run punctual --url http://localhost:8000 doctor
uv run punctual --url http://localhost:8000 --json doctor
```

Use the base URL, without `/mcp/`. `doctor` checks health, frontend availability,
authenticated API access, MCP discovery for `2026-07-28`, and all twelve tools.
It performs no writes and prints neither keys nor task contents. Exit code is
zero on success and one on failure. Errors distinguish connection failures,
401 (key mismatch), 404/405 (wrong endpoint), 421 (disallowed host), unsupported
protocol, and missing tools. `doctor --host localhost:8000` overrides the HTTP Host
header while retaining the connection URL, for local deployment checks.

## Deployment and configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `PUNCTUAL_API_KEY` | Required | Shared bearer key; server refuses to start without it |
| `PUNCTUAL_DB` | `punctual.db` in working directory | SQLite file; parent directory must exist |
| `PUNCTUAL_STATIC` | Repository `frontend/dist` | Built frontend directory |
| `PUNCTUAL_ALLOWED_HOSTS` | Loopback/server hosts | Comma-separated additional MCP Host values, including port if needed |
| `PUNCTUAL_ALLOWED_ORIGINS` | Same-origin / loopback | Comma-separated additional permitted MCP browser origins |
| `PUNCTUAL_MCP_HOST` | Unset (loopback check) | Deployment diagnostic Host header; saved by `--mcp-host` |

### Docker

Requires Docker Engine or Docker Desktop. Run these commands from the repository
root (the directory containing `Dockerfile`). The image builds the frontend and
installs the backend and CLI; local Python and Node installations are not needed.

#### Build and start

```sh
export PUNCTUAL_API_KEY='replace-with-your-shared-key'
docker build -t punctual .
docker run -d \
  --name punctual \
  --restart unless-stopped \
  -p 127.0.0.1:8000:8000 \
  -e PUNCTUAL_API_KEY \
  -v punctual-data:/data \
  punctual
```

Open **http://localhost:8000** and sign in with the API key you exported. The HTTP
API is at `/api/tasks`; the MCP endpoint is **http://localhost:8000/mcp/**. Both
require `Authorization: Bearer <your-key>`.

The named volume `punctual-data` is created automatically and holds
`/data/punctual.db`. Tasks and leases survive container replacement. Alembic
migrations run automatically on startup. The container runs as a non-root user
(UID 10001); if you use a bind-mounted directory instead of the named volume,
make it writable by that UID.

#### Check and manage the container

```sh
docker logs --tail 100 -f punctual
curl http://localhost:8000/health
docker exec punctual punctual --json list
docker stop punctual
docker start punctual
```

`docker logs -f` follows output; press Ctrl+C to stop following. The bundled CLI
inherits the container's API key and connects to its local backend.

#### Update the image

After updating the source, rebuild and recreate the container using the same volume:

```sh
docker build -t punctual .
docker stop punctual
docker rm punctual
docker run -d \
  --name punctual \
  --restart unless-stopped \
  -p 127.0.0.1:8000:8000 \
  -e PUNCTUAL_API_KEY \
  -v punctual-data:/data \
  punctual
```

Ensure `PUNCTUAL_API_KEY` is still exported in your shell. Container removal does
not remove the named volume. Keep any additional environment variables and port
mappings from your original deployment when recreating it.

#### Remote access

The commands above publish the service on the Docker host's loopback interface.
For a VPS, place a TLS reverse proxy in front of port 8000 and add the external
MCP hostname to the container's environment when creating it:

```sh
-e PUNCTUAL_ALLOWED_HOSTS='punctual.example.com'
```

Include the port in that value when clients use a non-default port, for example
`punctual.example.com:8443`. For a reverse proxy running in another container, put
both containers on a shared Docker network and proxy to `punctual:8000`.

Punctual is intended for small trusted groups, not sensitive information. One
backend process is sufficient for a lightweight VPS.

### Deploy to a remote VPS

Use `scripts/deploy.sh` from your local checkout. It uploads the current source
(including uncommitted changes), builds the image **on the VPS**, and starts or
updates the `punctual` container. Local Docker is not required.

Prerequisites:

- Locally: Bash, SSH, SCP, and tar.
- On the VPS: Bash, Docker Engine, and permission for the SSH user to run Docker
  without an interactive `sudo` prompt. Docker must be able to pull build images
  and download dependencies.
- Working SSH authentication, using your SSH agent, key, or normal SSH configuration.

From the repository root:

```sh
./scripts/deploy.sh deploy@your-vps
```

On the first deployment, the script generates an API key. Subsequent deployments
reuse the configuration in `~/.local/share/punctual/server.env` on the VPS. Retrieve
your generated key with:

```sh
ssh deploy@your-vps 'cat ~/.local/share/punctual/server.env'
```

Alternatively, create a local environment file and pass it explicitly:

```sh
cat > .env.deploy <<'EOF'
PUNCTUAL_API_KEY=replace-with-your-shared-key
PUNCTUAL_ALLOWED_HOSTS=punctual.example.com
EOF
chmod 600 .env.deploy
./scripts/deploy.sh deploy@your-vps --env-file .env.deploy
```

`--env-file` replaces the saved server configuration after a successful deployment.
The script stores that configuration with mode `600`. Environment files, databases,
Git history, dependency directories, and build output are excluded from the source
upload. It fixes the database and static paths to the Docker image's `/data` and
`/app/static` locations.

Available options:

```sh
./scripts/deploy.sh deploy@your-vps \
  --ssh-port 2222 \
  --identity ~/.ssh/vps_key \
  --bind 127.0.0.1 \
  --port 8000
```

The default bind address is `127.0.0.1`. Use your reverse proxy for remote access,
or open an SSH tunnel and visit **http://localhost:8000**:

```sh
ssh -N -L 8000:127.0.0.1:8000 deploy@your-vps
```

For direct network access, pass `--bind 0.0.0.0`. Supply the same bind/port options
on subsequent deployments; only the environment file is automatically reused.

Set the hostname and port MCP clients actually use with `--mcp-host`:

```sh
./scripts/deploy.sh argonaut --bind 0.0.0.0 --port 8000 --mcp-host localhost:8000
```

For HTTPS behind a proxy, use its public hostname (for example,
`--mcp-host punctual.example.com`). This option appends to existing
`PUNCTUAL_ALLOWED_HOSTS` and saves `PUNCTUAL_MCP_HOST` for future health checks.
The merged environment is saved only after deployment succeeds. An explicit
`--env-file` still replaces the saved configuration before these additions.

Deployment uses the same checks as `punctual doctor`, including authenticated
`server/discover` and `tools/list`, before removing the previous container.
Checks run inside the container using the configured external Host header;
they validate application host policy, not external DNS, TLS, proxy routing or
firewall access. Without `--mcp-host` or a saved `PUNCTUAL_MCP_HOST`, checks use
loopback and print a reminder. Run `doctor` from a client machine to verify the
complete network path. A failed check prints sanitized diagnostics and rolls back.

The deployment preserves the `punctual-data` volume and checks the frontend,
health endpoint, and authenticated task API before removing the old container.
If the new container fails to start or become healthy, it restores the previous
container. This involves a short interruption while containers are switched.
Rollback restores the container, **not database migrations**; back up the database
before deploying schema changes that are incompatible with the old application.

Deployments are serialized using `~/.local/share/punctual/deploy.lock`. If a host
crash leaves a stale lock, remove that empty directory after confirming no deploy
is running. Old image tags are retained so they remain available for recovery.

### Backups

Back up a running database using SQLite's backup API, rather than copying only
the `.db` file while WAL writes are active:

For Docker:

```sh
docker exec punctual python -c "import sqlite3; s=sqlite3.connect('/data/punctual.db'); d=sqlite3.connect('/data/backup.db'); s.backup(d); d.close(); s.close()"
docker cp punctual:/data/backup.db ./punctual-backup.db
```

For a local installation, run this from the directory containing the database:

```sh
python -c "import sqlite3; s=sqlite3.connect('punctual.db'); d=sqlite3.connect('backup.db'); s.backup(d); d.close(); s.close()"
```

To restore, stop the server, replace the database with the backup, remove any stale
`-wal`/`-shm` files belonging to the old database, then restart.

## Checks

```sh
cd backend
uv run pytest -q
uv run ruff check punctual tests main.py
uv run ruff format --check punctual tests main.py
cd ../frontend
npm run check
npm run format:check
npm run build
```

Tests cover competing claims and edits, persisted leases, expiry/recovery, token
conflicts, parent integrity, HTTP authentication/validation, and stateless MCP
calls sharing HTTP locking rules.

Frontend source is formatted with Prettier and `prettier-plugin-svelte`. Run
`npm run format` in `frontend/` after editing Svelte, TypeScript, or CSS; production
assets are minified by Vite at build time.

## Source layout

### Frontend

The frontend follows a lightweight feature-sliced structure. Dependencies flow
downward: **app → pages → widgets → features → entities → shared**. Slices on the
same layer remain independent. Components own their styles; shared styles contain
typography and reusable controls.

```text
frontend/src/
├── app/                     # Composition, authentication lifecycle, shared styles
├── pages/board/             # Board workflows, dialogs, shortcut registry
├── widgets/
│   ├── board/               # Board state, columns, toolbar, task actions, footer
│   └── sidebar/             # Workspace navigation and identity controls
├── features/
│   ├── authentication/      # Login form and credential state
│   ├── task-editor/         # Task/subtask editing and local drafts
│   └── task-deletion/       # Delete confirmation
├── entities/task/           # Task types, API, card, and local lease state
├── shared/
│   ├── api/                 # Generic authenticated HTTP client
│   ├── keyboard/            # Shortcut event handling
│   └── ui/                  # Brand, modal, shortcut reference dialog
└── main.ts
```

`app/App.svelte` owns authentication and injects the API and lease state into the
board page. The board has no dependency on login/session state. `BoardPage.svelte`
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
and migrations are encapsulated in `db/`. Tests are organized by tasks, HTTP, MCP,
CLI, and migrations, with shared fixtures in `backend/tests/conftest.py`.
