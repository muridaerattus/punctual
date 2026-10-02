# HTTP API

[Documentation index](../README.md#documentation)

## Boards and ticket keys

See [board usage](usage.md#boards-and-ticket-keys) for prefix and numbering rules.
Use `GET /api/boards` and `POST /api/boards` (body: `{"name":"Engineering","prefix":"ENG"}`).
Pass `board_id` when creating or listing tasks; omission selects default board 1.
Resolve a key with `GET /api/tasks/by-key/ENG-1`, then use the returned numeric `id`
for existing edit, delete, and lease endpoints. Task responses include `board_id`,
`number`, `key`, and `parent_key`. Text search also accepts a complete ticket key.

## Endpoints

Bearer clients use `Authorization: Bearer <PUNCTUAL_API_KEY>` for `/api/*` and `/mcp/*`.
Configured browser OIDC sessions also authorize the HTTP API; configured
[MCP OAuth](mcp.md#oauth-sign-in) access tokens authorize MCP only.
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
| POST | `/api/tasks/{id}/claim` | JSON: `owner`, optional `seconds`, optional `lease_token` |
| POST | `/api/tasks/{id}/renew` | JSON: `lease_token`, optional `seconds` |
| POST | `/api/tasks/{id}/release` | JSON: `lease_token` |
| POST | `/api/tasks/{id}/force-release` | JSON: current `revision`, public `lease_id`, and `reason`; overrides a stuck lease |
| GET | `/api/tasks/{id}/lease-history` | Durable forced-release records, retained after task deletion |

### Workflow endpoints

These routes use the same service methods as the MCP workflow tools. Read responses
are data objects; write responses include `replayed`. HTTP errors keep the existing
`error` envelope, with optional `details` (such as ambiguous board matches).

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/workflows/tasks` | Compact paged search; required `board` prefix/exact name; optional `status`, `assignee`, `query`, `parent_id`, `available`, `limit`, `cursor` |
| GET | `/api/workflows/tasks/{key}/context` | Full task/parent, board, child counts and compact paged `subtasks` |
| GET | `/api/workflows/boards/overview` | Required `board`, optional sample `limit`; exact counts plus bounded samples |
| GET | `/api/workflows/available-work` | Required `board`; optional `assignee`, `query`, `limit`, `cursor`; unclaimed To Do candidates |
| GET | `/api/workflows/tasks/{id}/lease-history` | Paged forced-release records, even after task deletion |
| POST | `/api/workflows/tasks/{key}/start` | Atomic claim and In Progress transition |
| POST | `/api/workflows/tasks/{key}/complete` | Atomic Complete transition and owned active lease release |
| POST | `/api/workflows/task-trees` | Atomic parent and up to 50 one-level children |

Paged reads default to 50 items, with limits from 1 to 100 and a positive last-row-ID
cursor. Overview samples default to 10. Follow `next_cursor` with unchanged filters;
`truncated` indicates further results. Compact task items omit descriptions and all
general reads omit lease tokens. Prefix resolution takes precedence over exact name
matching; duplicate names require choosing one of the returned prefixes. Cursor
pages are separate snapshots, and availability can change before a claim.

Start body: `revision`, `owner`, `lease_token`, `request_id`, optional `seconds`
(30–86400, default 900), and optional `assignee`. Complete body: `revision`,
`lease_token`, and `request_id`. Both return `{ "task": …, "replayed": false }`.
Starting a completed task is rejected; use an explicit granular edit to reopen it.
Assignee is unchanged unless supplied; parent and child statuses remain independent.

Tree body: `board`, `request_id`, `parent`, and `children`. Parent and children accept
`title`, `description`, `status`, and `assignee`; board and relationships are set by
the operation. The result contains `parent`, `children`, and `replayed`.

Generate and save a fresh random URL-safe request ID of 32–100 characters before
each composite write. Start requires a pre-saved lease token with the same format.
Each composite write checks its expected state and commits the full operation and
receipt inside one short SQLite write transaction. On a lost response, retry with
the same request ID and identical payload: a persisted receipt returns the original
public snapshot with `replayed: true`. It never reapplies the write, even after
later edits or deletion, and contains no lease token. Different input with the same
request ID is rejected. Fetch current context before subsequent work, and retain
your saved token for renewal/completion. Receipts are retained to preserve retry
guarantees; do not manually prune them and then reuse request IDs.

The original `/api/tasks` routes retain their full-detail array contracts for the
UI and CLI. Use workflow reads for bounded agent integrations.

```sh
curl http://localhost:8000/api/tasks \
  -H "Authorization: Bearer $PUNCTUAL_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"title":"First task","status":"To Do"}'
```

`/openapi.json`, `/docs`, and `/redoc` are authenticated too; fetch them with the
same bearer header. `/health` is public. Times are Unix seconds. Validation errors
use HTTP 422 with a `detail` array of `type`, `loc`, and `msg` fields; submitted
values are omitted. Domain errors contain `{ "error": { "code": "…", "message": "…" } }`.

## Coordination guarantees

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

## Recovering a lost claim response or token

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
