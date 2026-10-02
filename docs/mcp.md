# MCP

[Documentation index](../README.md#documentation)

Connect a **Streamable HTTP** client to `http://localhost:8000/mcp/` with the same
bearer header as the [HTTP API](api.md), or use OAuth when configured below.
This implementation targets the **2026-07-28**
specification using FastMCP 4 / MCP SDK 2. Requests are stateless, carry per-request
version and capability metadata, and do not use a session ID or initialization handshake.

Tools share the HTTP `TaskService`, revision checks, and lease rules. Results have
`{ "ok": true, "data": … }` or
`{ "ok": false, "error": { "code": …, "message": … } }`; agents must check `ok`.
Domain failures also set MCP `isError`. Workflow results include a concise `summary`.
Schema validation failures use `invalid_arguments` with field paths/types, omitting
submitted values. Claim and renewal are the only tools that return lease tokens;
renewal, release, edit, delete, and completion accept existing legacy tokens.

| Tool | Purpose |
| --- | --- |
| `list_boards`, `create_board` | Discover or create boards and immutable prefixes |
| `get_task`, `get_task_by_key` | Full task detail, revision, and public lease metadata |
| `list_tasks` | Bounded compact task search by numeric board ID |
| `query_tasks` | Bounded compact search by board prefix/name, with parent and availability filters |
| `get_task_context` | Task, board, parent, and a bounded page of subtasks |
| `board_overview` | Exact status/claim counts and bounded samples, distinguishing top-level tasks and subtasks |
| `find_available_work` | Unclaimed To Do candidates, ordered by numeric ID |
| `start_task` | Atomically claim a task and set In Progress |
| `complete_task` | Atomically complete a task and release its owned active lease |
| `create_task_tree` | Atomically create a parent and up to 50 one-level children |
| `create_task`, `update_task`, `delete_task` | Granular creation, revision-checked edits, and deletion |
| `claim_task`, `renew_lease`, `release_lease` | Granular claim lifecycle |
| `force_release_lease` | Explicit override with revision, public lease ID, and recorded reason |
| `get_lease_history` | Bounded forced-release records, including for deleted numeric task IDs |

Use `list_boards` to choose a board, or `create_board(board)` to create one.
`list_tasks(board_id=...)` and `create_task(task={..., "board_id": ...})` scope work;
omission selects board 1. New workflows accept an explicit board prefix or exact
board name, or an exact ticket key. Duplicate board names produce structured
candidate matches; use a unique prefix to continue. Granular mutations still take
numeric task IDs obtained from `get_task_by_key(key)`.

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

## Agent workflows

Recommended flow: choose board → find available work → get task context → start →
renew while working → complete. `start_task` combines claim and status update in
one transaction; `complete_task` combines completion and release. Pass the revision
you actually read. A conflict means fetch and reconsider the change, rather than
automatically retrying with a newer revision. Claim owner and assignee are separate;
starting only changes assignee when explicitly requested. Completing a parent does
not complete its children.

Save a random lease token **and a distinct request ID** before a composite write
(for example, generate each with `secrets.token_urlsafe(32)`). Keep them outside
version control. The request ID is required for `start_task`, `complete_task`, and
`create_task_tree`; start also requires a client-supplied token. Retry a lost response
with the identical request ID and input. Durable receipts survive restart and
prevent repeated edits or duplicate task trees. Reusing an ID with different input
is an error. Replays return the original public result with `replayed: true`, not
a fresh view of the task; fetch current context before further work. Receipt results
contain no lease token. Use a new request ID for every new intended operation.

Completion requires your active lease. Expired leases must be claimed again; see
[lease recovery](api.md#recovering-a-lost-claim-response-or-token) for granular claims.
Lease renewal still uses `renew_lease` with the numeric task ID and saved token.
Availability is a snapshot, not a reservation: another agent may claim a candidate
before your start request.

### Bounded reads and migration

**MCP `list_tasks` now returns a page object in `data`, rather than an array.** Read
`data.items`, and pass `data.next_cursor` to the next call with the same filters.
Pages have `truncated: true` when further matches exist; a final page has a null
cursor. Lists default to 50 items, with a hard maximum of 100. Compact list items
omit descriptions; use `get_task`, `get_task_by_key`, or `get_task_context` for full
detail. Existing HTTP `/api/tasks` and CLI list output retain their contracts.

`get_task_context` pages its `subtasks` independently of full task/parent detail.
Counts and `board_overview` aggregates cover the entire matching set even when
samples are truncated. Cursor ordering is ascending numeric ID, not priority.
Task pages, context, and overviews include an `as_of` Unix timestamp used consistently
for lease activity checks. Pages fetched at different times are separate snapshots. Expired leases are
presented as unclaimed, and general read responses never include lease tokens.

`get_lease_history` accepts a numeric task ID because forced-release records survive
deletion. It contains only explicit forced releases, not normal claim/release events
or a complete task timeline.

### Native behavior and scope

The workflow audit reviewed the current service, documentation, and project changes.
Revision/lease enforcement, expired-lease availability, recoverable claims, stable
numbering, parent validation, and forced-release recording are already native domain
behavior. Workflows reuse these rules; there is no need for an expired-lease cleanup
tool or a second rules engine in the MCP adapter.

Before extending automation, review the project's latest documentation and product
changes for native AI features or automation rules, including deployment-specific
integrations. No AI classification, notification engine, or conditional automation
engine was found in the audited implementation.

[Linear's documented MCP workflows](https://linear.app/docs/mcp#common-use-cases),
[community integration patterns](https://github.com/wrsmith108/linear-claude-skill),
and [an agent workflow guide](https://www.builder.io/blog/linear-mcp-server) inform
the context, planning, and overview use cases. They are analogous examples, not
Punctual usage telemetry. Punctual's current model cannot provide a full activity
timeline, reliable completed-by-period reporting, or dependency/blocker analytics.
Those require separate data-model work; `updated_at` is not a completion timestamp
and a parent relationship is not a dependency edge.

## OpenCode (bearer authentication)

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
uses a shared bearer key in this example, so OAuth is disabled for that connection.

## OAuth sign-in

Punctual uses FastMCP's `RemoteAuthProvider` for RFC 9728 protected-resource
discovery and bearer challenges. The identity provider owns authorization,
consent, client registration, authorization codes and S256 PKCE. Punctual is only
a resource server: no browser cookies or ID tokens authorize MCP, and MCP access
tokens do not authorize the HTTP API. Existing API keys continue to work.

Enable all of these server environment settings together:

| Setting | Example / contract |
| --- | --- |
| `PUNCTUAL_MCP_ISSUER` | `https://identity.example/application/o/tasks-mcp/`; exact token issuer and discoverable authorization server |
| `PUNCTUAL_MCP_JWKS_URL` | `https://identity.example/application/o/tasks-mcp/jwks/`; trusted public signing keys |
| `PUNCTUAL_MCP_RESOURCE` | `https://tasks.example/mcp`; canonical resource **and required audience** |
| `PUNCTUAL_MCP_GROUP` | `Team`; exact member of signed `groups` array |
| `PUNCTUAL_MCP_SCOPES` | `tasks:access`; space-separated required scopes |
| `PUNCTUAL_MCP_TOKEN_PROFILE` | `rfc9068` (default) or `authentik` |

Only RS256 access tokens with a valid signature, exact issuer, resource audience,
subject, issued-at and expiry are accepted; future `nbf`/`iat` are rejected.
Required scopes are advertised in discovery/challenges and enforced with 403.
Group failures and invalid/expired tokens receive 401. JWKS is cached by PyJWT
for five minutes and refreshed for an unknown signing key.

The default profile requires the signed `at+jwt` (or `application/at+jwt`) header.
The Authentik profile instead requires nonempty signed `uid`, `azp`, and `scope`
claims, which Authentik 2026.8.3 adds only when serializing access tokens. **Do not
create scope mappings that add those claims to ID tokens.** Provision a dedicated
MCP provider/client, separate issuer, audience mapping and group policy; never
reuse the browser confidential client or distribute its secret. A custom MCP
scope mapping can supply the fixed resource `aud` and the user's current `groups`.
Authentik normally uses the client ID as audience, which is insufficient here.

Public metadata is at `/.well-known/oauth-protected-resource/mcp` (or `/mcp/`
suffix if that is the configured resource). Its URLs come from trusted settings,
not request Host/forwarded headers. The issuer must publish OAuth/OIDC discovery
with S256 support. Clients send the resource in authorization and token requests.
Do not map arbitrary client-supplied resource values into token audiences.

### Client registration and OpenCode

Authentik 2026.8 DCR requires an already-authorized DCR bearer token, and creates
separate providers with copied policies. It does not provide anonymous MCP
onboarding. Use a pre-registered **public** authorization-code client with exact
loopback redirects, required S256, explicit consent and the team policy. This
avoids an application-owned OAuth bridge. CIMD/DCR support is issuer-dependent;
Punctual does not claim to implement either.

OpenCode V2 example for such a pre-registered client:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "servers": {
      "punctual-oauth": {
        "type": "remote",
        "url": "https://tasks.example/mcp/",
        "protocol": "2026-07-28",
        "oauth": {
          "client_id": "tasks-mcp",
          "scope": "tasks:access offline_access",
          "callback_port": 19876,
          "redirect_uri": "http://127.0.0.1:19876/callback"
        }
      }
    }
  }
}
```

Open `/mcps`, select this connection and sign in; approve consent in the identity
provider. Check that the connection becomes connected. No client secret or
Authorization header is needed. This is an example, not an automatic edit to your
existing client. The callback must reach the machine running the OpenCode service.

Token lifetime, refresh and revocation are issuer policy. Enable Authentik's
`refresh_token` grant and built-in `offline_access` scope mapping alongside the
resource scope; clients must request both scopes. OpenCode refreshes automatically.
Existing access-only grants need one new sign-in to obtain a refresh token.

The deployed Authentik configuration keeps five-minute access tokens and uses
30-day refresh tokens with rotation on every use (`refresh_token_threshold` set
to `seconds=0`). The resource scope mapping caps token expiry at the original
authentication time plus 30 days, so sliding refresh rotation cannot grant
indefinite access. After that bound, obtain a fresh identity-provider login and
MCP grant. No client secret is needed for this public client.

Authentik 2026.8 does not rerun application policies on refresh. Recompute current
groups in the scope mapping on every issuance, omitting groups for inactive
accounts. Punctual then rejects refreshed tokens after team removal; disabling
an account also prevents refresh. Revoke MCP refresh tokens when offboarding.
Already-issued access tokens remain usable until their five-minute expiry.
Native refresh revocation and rotation replay rejection are verified; this is
not a token-family revocation guarantee. For immediate shutdown disable the MCP
OAuth settings and restart (existing API-key access remains available).

References: [MCP authorization](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization),
[FastMCP remote OAuth](https://gofastmcp.com/servers/auth/remote-oauth),
[Authentik DCR](https://docs.goauthentik.io/add-secure-apps/providers/oauth2/dynamic-client-registration/),
[OpenCode V2 MCP](https://opencode.ai/v2/docs/mcp-servers).

For this example, set `PUNCTUAL_ALLOWED_HOSTS=localhost:8000` on the **Punctual
server**. Preserve other allowed hosts as comma-separated values. Docker
environment changes require recreating the container, not just `docker restart`.

## Connection diagnostics

From `backend/`, with `PUNCTUAL_API_KEY` set:

```sh
uv run punctual --url http://localhost:8000 doctor
uv run punctual --url http://localhost:8000 --json doctor
```

Use the base URL, without `/mcp/`. `doctor` checks health, frontend availability,
authenticated API access, MCP discovery for `2026-07-28`, and all twenty tools.
It performs no writes and prints neither keys nor task contents. Exit code is
zero on success and one on failure. Errors distinguish connection failures,
401 (key mismatch), 404/405 (wrong endpoint), 421 (disallowed host), unsupported
protocol, and missing tools. `doctor --host localhost:8000` overrides the HTTP Host
header while retaining the connection URL, for local deployment checks.
