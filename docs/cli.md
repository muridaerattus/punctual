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

## Boards and ticket keys

```sh
punctual boards list
punctual boards create 'Engineering' --prefix ENG
punctual create 'Ship a release' --board ENG
punctual list --board ENG --status 'To Do'
punctual list --board 2 --query ENG-1
punctual --json get ENG-1
punctual create 'Write release notes' --board ENG --parent-id ENG-1
punctual update ENG-1 --revision 1 --status 'In Progress'
```

`list` and `create` accept `--board` with a numeric board ID or exact uppercase
prefix; omitting it still selects board **1**. Board prefixes are unique, immutable,
and contain 1–8 uppercase ASCII letters. `boards list` returns IDs, names, and prefixes.
Use IDs and ticket keys from your own responses in these examples.

Every task command accepts a numeric task ID or a ticket key, including `claim`,
`renew`, `release`, `force-release`, and `lease-history`. `--parent-id` on `create`
and `update` also accepts either form. Numeric task IDs are global; the number in
`ENG-1` is local to that board and need not equal its numeric task ID. Task keys
resolve across boards without `--board`. Parents must belong to the selected board;
specifying a parent does not implicitly select its board.

Key-based writes resolve only the numeric ID and still use your explicit revision
and lease token. Lookup output is suppressed so `--json` produces one result or
structured error per command. Unknown boards/keys fail without retrying a write.
For `lease-history` after a task is deleted, use its numeric ID because ticket-key
lookup requires an existing task.

See [lease recovery](api.md#recovering-a-lost-claim-response-or-token) for recovering
lost claims, and [connection diagnostics](mcp.md#connection-diagnostics) for `punctual doctor`.
