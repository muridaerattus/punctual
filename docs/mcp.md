# MCP

[Documentation index](../README.md#documentation)

Connect a **Streamable HTTP** client to `http://localhost:8000/mcp/` with the same
bearer header as the [HTTP API](api.md). This implementation targets the **2026-07-28**
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
uses a shared bearer key, so OAuth registration must be disabled.

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
