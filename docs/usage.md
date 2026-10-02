# Board usage

[Documentation index](../README.md#documentation)

## Boards and ticket keys

Each board has a name and a unique, immutable prefix of 1–8 uppercase ASCII letters
(`^[A-Z]{1,8}$`). Create and select boards in the sidebar. Tasks display stable keys
such as `ENG-12345`; numbering starts at 1 independently in each board, includes
subtasks, and never reuses deleted ticket numbers. Prefixes and task boards cannot
be changed. Parents must belong to the same board; subtasks support one level.

Existing tasks migrate into board **1**, named **Default**, with prefix **PUN**.
Their keys remain `PUN-<existing numeric ID>`. Numeric IDs, revisions, relationships,
and active leases are preserved. Boards share the instance's authentication;
they organize work rather than define access permissions.

See the [HTTP API](api.md) for board scoping and key lookup, and
[database development](development.md#database-development) for migration details.

## Keyboard first

Press **?** on the board for the complete reference. Shortcuts are disabled while
typing in a field. All controls are also reachable with Tab; dialogs trap focus
and close with Escape.

| Key | Action |
| --- | --- |
| N | New task |
| J / K or ↓ / ↑ | Next / previous card |
| ← / → | Move selected task to previous / next status |
| Enter (on card) / E | Open / edit task |
| S | New subtask of selected top-level task |
| 1 / 2 / 3 | Move to To Do / In Progress / Complete |
| C | Claim selected task for 15 minutes |
| R / U | Renew / release your lease |
| X / Delete | Delete, with confirmation |
| / | Focus search |
| G | Refresh (also in the ⋯ menu beside the board name) |
| O | Open claim identity editing |
| Shift L | Sign out |
| Ctrl/Cmd Enter | Save task in editor |
| Escape | Close dialog / clear focused search |

Search and **New task** sit in the board header. Each column also has a **+** button
to create a task with that status. Select a card to edit it, change its status, or
claim it from the bottom action bar. The bar's **⋯** menu contains subtask creation,
lease renewal/release for your own claims, and deletion. Active claims show their
owner and remaining time.

Use **Claim as …** in the sidebar (or **O**) to edit your claim identity. The
sidebar's **Keyboard shortcuts** button opens the same reference as **?**.

The board refreshes every five seconds, pausing during editing. If a refresh fails,
a short alert keeps the last loaded tasks on screen and offers Retry; it clears after
the next successful refresh. Revision conflicts
preserve the open draft and show an error; close and reopen to load the new revision.
Parent and subtask statuses are independent.
