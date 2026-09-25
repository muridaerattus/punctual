export function handleShortcut(
  event: KeyboardEvent,
  actions: Record<string, () => unknown>,
  enabled: boolean,
) {
  if (!enabled || event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey) return;
  const target = event.target;
  if (
    target instanceof HTMLElement &&
    target.closest('input, textarea, select, [contenteditable="true"]')
  )
    return;
  const action = actions[event.key];
  if (action) {
    event.preventDefault();
    action();
  }
}
