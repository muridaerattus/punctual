<script lang="ts">
  import { tick } from 'svelte';
  import Brand from '../../shared/ui/Brand.svelte';
  import type { BoardInfo } from '../../entities/board/types';
  let {
    boards,
    boardId,
    busy,
    onselect,
    oncreate,
    owner = $bindable(''),
    onhelp,
    onlogout,
  }: {
    boards: BoardInfo[];
    boardId: number;
    busy: boolean;
    onselect: (id: number) => void;
    oncreate: () => void;
    owner?: string;
    onhelp: () => void;
    onlogout: () => void;
  } = $props();

  let editingIdentity = $state(false);
  let identityTrigger = $state<HTMLButtonElement>();
  let identityInput = $state<HTMLInputElement>();

  export async function focusIdentity() {
    editingIdentity = true;
    await tick();
    identityInput?.focus();
  }

  function closeIdentity() {
    owner = owner.trim() || 'human';
    editingIdentity = false;
    identityTrigger?.focus();
  }

  function handleIdentityKey(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      event.preventDefault();
      event.stopPropagation();
      closeIdentity();
    }
  }
</script>

<aside class="sidebar">
  <Brand />
  <div class="board-picker">
    <label for="board-select">Board</label>
    <select
      id="board-select"
      value={boardId}
      disabled={busy}
      onchange={(event) => onselect(Number(event.currentTarget.value))}
    >
      {#each boards as board}<option value={board.id}>{board.name} ({board.prefix})</option>{/each}
    </select>
    <button class="quiet" disabled={busy} onclick={oncreate}>+ New board</button>
  </div>
  <div class="sidebar-bottom">
    <div class="identity">
      <button
        class="quiet identity-trigger"
        bind:this={identityTrigger}
        aria-expanded={editingIdentity}
        aria-controls={editingIdentity ? 'claim-identity-editor' : undefined}
        onclick={() => (editingIdentity ? closeIdentity() : focusIdentity())}
      >
        <span class="identity-summary">Claim as {owner.trim() || 'human'}</span><kbd>O</kbd>
      </button>
      {#if editingIdentity}
        <form
          id="claim-identity-editor"
          class="identity-editor"
          onsubmit={(event) => {
            event.preventDefault();
            closeIdentity();
          }}
        >
          <label for="owner">Your claim identity</label>
          <input
            id="owner"
            bind:this={identityInput}
            bind:value={owner}
            maxlength="100"
            placeholder="human"
            onkeydown={handleIdentityKey}
          />
          <button type="submit" class="quiet" onkeydown={handleIdentityKey}>Done</button>
        </form>
      {/if}
    </div>
    <button class="quiet" onclick={onhelp}>Keyboard shortcuts <kbd>?</kbd></button>
    <button class="quiet" onclick={onlogout}>Sign out <kbd>⇧ L</kbd></button>
  </div>
</aside>

<style>
  .board-picker {
    margin-top: var(--space-4);
    min-width: 0;
    display: grid;
    gap: var(--space-2);
  }
  select {
    min-width: 0;
    font-size: var(--text-base);
  }
  .sidebar {
    width: 230px;
    flex-shrink: 0;
    background: var(--surface-sidebar);
    border-right: 1px solid var(--border-subtle);
    padding: var(--space-8) var(--space-5);
    display: flex;
    flex-direction: column;
  }
  .sidebar-bottom {
    margin-top: auto;
    padding-top: var(--space-8);
    display: grid;
    gap: var(--space-2);
    min-width: 0;
  }
  .identity {
    min-width: 0;
  }
  .identity-summary {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .identity-editor {
    display: grid;
    gap: var(--space-2);
    margin-top: var(--space-2);
    padding: var(--space-2);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-control);
  }
  input {
    min-width: 0;
    font-size: var(--text-base);
  }
  .quiet {
    width: 100%;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: var(--space-2);
    min-height: 40px;
    padding: var(--space-2);
    font-size: var(--text-base);
    text-align: left;
  }
  kbd {
    flex-shrink: 0;
  }
  @media (max-width: 1100px) {
    .sidebar {
      width: 185px;
      padding: var(--space-7) var(--space-4);
    }
  }
  @media (max-width: 760px) {
    .sidebar {
      width: 100%;
      padding: var(--space-4) var(--space-5);
      flex-direction: row;
      align-items: center;
      flex-wrap: wrap;
      gap: var(--space-4);
      border-right: 0;
      border-bottom: 1px solid var(--border-subtle);
    }
    .board-picker {
      flex: 1 1 220px;
      margin-top: 0;
    }
    .sidebar-bottom {
      padding: 0;
      margin: 0;
      width: 100%;
      display: flex;
      align-items: flex-start;
      flex-wrap: wrap;
      gap: var(--space-2);
    }
    .identity {
      flex: 1 1 100%;
    }
    .quiet {
      width: auto;
      min-height: 44px;
    }
    .identity-trigger {
      width: 100%;
    }
    input,
    select {
      font-size: max(16px, var(--text-base));
    }
  }
</style>
