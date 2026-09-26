# CLI

[Documentation index](../README.md#documentation)

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

Replace example task IDs and revisions with values from your responses. Use
`punctual --help` or `punctual update --help` for all options. `--json` is a
global flag placed before the command. Output is JSON on stdout in this mode,
including structured errors. Exit codes: **0** success, **1** request/configuration
failure, **2** command usage error, **3** task/revision/lease conflict. Updates and
deletes require an explicit expected revision; the CLI does not silently fetch a
new revision or retry a stale write. `--clear-assignee` and `--clear-parent` unset
those fields. Tokens can also be supplied using `--lease-token`.

CLI listing and creation target the default board; numeric-ID commands work across
boards. Use the [HTTP API](api.md) or [MCP tools](mcp.md) to create/list in other boards
and resolve ticket keys.

See [lease recovery](api.md#recovering-a-lost-claim-response-or-token) for recovering
lost claims, and [connection diagnostics](mcp.md#connection-diagnostics) for `punctual doctor`.
