// Bindings and help text share one registry; form-local shortcuts are documentation-only.
const definitions = [
  { keys: ['n'], display: 'N', label: 'New task', action: 'create' },
  { keys: ['j', 'ArrowDown'], display: 'J / ↓', label: 'Next task', action: 'next' },
  { keys: ['k', 'ArrowUp'], display: 'K / ↑', label: 'Previous task', action: 'previous' },
  { keys: ['ArrowLeft'], display: '←', label: 'Move to previous status', action: 'moveLeft' },
  { keys: ['ArrowRight'], display: '→', label: 'Move to next status', action: 'moveRight' },
  { keys: ['e'], display: 'E / Enter on card', label: 'Edit selected task', action: 'edit' },
  { keys: ['s'], display: 'S', label: 'Create subtask', action: 'subtask' },
  { keys: ['1'], display: '1', label: 'Move to To Do', action: 'todo' },
  { keys: ['2'], display: '2', label: 'Move to In Progress', action: 'inProgress' },
  { keys: ['3'], display: '3', label: 'Move to Complete', action: 'complete' },
  { keys: ['c'], display: 'C', label: 'Claim for 15 minutes', action: 'claim' },
  { keys: ['r'], display: 'R', label: 'Renew your lease', action: 'renew' },
  { keys: ['u'], display: 'U', label: 'Release your lease', action: 'release' },
  { keys: ['x', 'Delete'], display: 'X / Delete', label: 'Delete selected task', action: 'delete' },
  { keys: ['/'], display: '/', label: 'Search', action: 'search' },
  { keys: ['g'], display: 'G', label: 'Refresh board', action: 'refresh' },
  { keys: ['o'], display: 'O', label: 'Edit claim identity', action: 'identity' },
  { keys: ['L'], display: 'Shift L', label: 'Sign out', action: 'logout' },
  { keys: ['?'], display: '?', label: 'Show shortcuts', action: 'help' },
] as const;

type BoardAction = (typeof definitions)[number]['action'];

export function boardShortcuts(actions: Record<BoardAction, () => unknown>) {
  return Object.fromEntries(
    definitions.flatMap(({ keys, action }) => keys.map((key) => [key, actions[action]])),
  );
}

export const shortcutReference = [
  ...definitions.map(({ display, label }) => [display, label] as const),
  ['Ctrl / ⌘ Enter', 'Save task in editor'],
  ['Escape', 'Close dialog / clear search'],
] as const;
