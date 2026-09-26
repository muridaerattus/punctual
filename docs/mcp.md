# MCP

[Documentation index](../README.md#documentation)

Connect a **Streamable HTTP** client to `http://localhost:8000/mcp/` with the same
bearer header as the [HTTP API](api.md), or use OAuth when configured below.
This implementation targets the **2026-07-28**
specification using FastMCP 4 / MCP SDK 2. Requests are stateless, carry per-request
version and capability metadata, and do not use a session ID or initialization handshake.

Tools: `list_boards`, `create_board`, `get_task_by_key`, `list_tasks`, `get_task`, `create_task`, `update_task`, `delete_task`,
`claim_task`, `renew_lease`, `release_lease`, `force_release_lease`. Tools share exactly the HTTP service
and lock checks. Results have `{ "ok": true, "data": … }` or
`{ "ok": false, "error": { "code": …, "message": … } }`; agents must check `ok`.

Use `list_boards` to choose a board, or `create_board(board)` to create one.
`list_tasks(board_id=...)` and `create_task(task={..., "board_id": ...})` scope work;
omission selects board 1. Resolve ticket keys with `get_task_by_key(key)`, then use
numeric task IDs for mutations.

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

Recommended agent workflow: choose board → list → get → claim → update with revision
and token → renew while working → complete → release. Save a random lease token
before claiming; see [lease recovery](api.md#recovering-a-lost-claim-response-or-token).
An expired lease must be claimed again.

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
          "scope": "tasks:access",
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

Token lifetime, refresh and revocation are issuer policy. The initial Authentik
deployment uses five-minute access tokens and code-only grants; sign in again on
expiry. It does not issue refresh tokens. Removing team membership prevents new
authorization; already-issued tokens remain usable until expiry. Browser logout
does not revoke MCP tokens. For immediate shutdown disable the MCP OAuth settings
and restart (existing API-key access remains available).

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
authenticated API access, MCP discovery for `2026-07-28`, and all twelve tools.
It performs no writes and prints neither keys nor task contents. Exit code is
zero on success and one on failure. Errors distinguish connection failures,
401 (key mismatch), 404/405 (wrong endpoint), 421 (disallowed host), unsupported
protocol, and missing tools. `doctor --host localhost:8000` overrides the HTTP Host
header while retaining the connection URL, for local deployment checks.
