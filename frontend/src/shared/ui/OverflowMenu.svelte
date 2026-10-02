<script lang="ts" module>
  export interface MenuItem {
    label: string;
    shortcut?: string;
    danger?: boolean;
    disabled?: boolean;
    onselect: () => void;
  }
</script>

<script lang="ts">
  import { tick } from 'svelte';

  let {
    label,
    items,
    placement = 'down',
  }: { label: string; items: MenuItem[]; placement?: 'up' | 'down' } = $props();
  let open = $state(false);
  let root: HTMLElement;
  let trigger: HTMLButtonElement;

  function entries() {
    return Array.from(root.querySelectorAll<HTMLButtonElement>('[role="menuitem"]:not(:disabled)'));
  }
  async function show() {
    open = true;
    await tick();
    entries()[0]?.focus();
  }
  function hide(restoreFocus = true) {
    open = false;
    if (restoreFocus) trigger.focus();
  }
  function choose(item: MenuItem) {
    hide();
    item.onselect();
  }
  function keyboard(event: KeyboardEvent) {
    if (!open) return;
    const list = entries();
    const index = list.indexOf(document.activeElement as HTMLButtonElement);
    const focus = (next: number) => list[(next + list.length) % list.length]?.focus();
    const keys: Record<string, () => void> = {
      Escape: () => hide(),
      ArrowDown: () => focus(index + 1),
      ArrowUp: () => focus(index - 1),
      Home: () => focus(0),
      End: () => focus(list.length - 1),
      Tab: () => hide(false),
    };
    const action = keys[event.key];
    if (!action) return;
    if (event.key !== 'Tab') event.preventDefault();
    event.stopPropagation();
    action();
  }
</script>

<svelte:window
  onpointerdown={(event) => {
    if (open && !root.contains(event.target as Node)) hide(false);
  }}
/>

<div class="overflow" bind:this={root} onkeydown={keyboard} role="presentation">
  <button
    bind:this={trigger}
    class="trigger"
    aria-label={label}
    aria-haspopup="menu"
    aria-expanded={open}
    onclick={() => (open ? hide() : show())}>⋯</button
  >
  {#if open}
    <div class={`menu ${placement}`} role="menu" aria-label={label}>
      {#each items as item}
        <button
          role="menuitem"
          class:danger={item.danger}
          disabled={item.disabled}
          onclick={() => choose(item)}
        >
          <span>{item.label}</span>
          {#if item.shortcut}<kbd>{item.shortcut}</kbd>{/if}
        </button>
      {/each}
    </div>
  {/if}
</div>

<style>
  .overflow {
    position: relative;
  }
  .trigger {
    background: transparent;
    border-color: transparent;
    padding: 5px 9px;
    line-height: 1;
    font-size: 15px;
    color: #9faa9f;
  }
  .menu {
    position: absolute;
    right: 0;
    z-index: 20;
    min-width: 180px;
    display: flex;
    flex-direction: column;
    padding: 5px;
    background: #171e18;
    border: 1px solid #344034;
    border-radius: 7px;
    box-shadow: 0 12px 30px #0b0e0d;
  }
  .down {
    top: calc(100% + 6px);
  }
  .up {
    bottom: calc(100% + 6px);
  }
  [role='menuitem'] {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
    border: 0;
    background: transparent;
    text-align: left;
    font-size: 11px;
    padding: 8px 9px;
  }
  [role='menuitem']:hover,
  [role='menuitem']:focus-visible {
    background: #252f26;
    outline: none;
  }
</style>
