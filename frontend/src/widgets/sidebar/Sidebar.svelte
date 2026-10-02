<script lang="ts">
  import Brand from '../../shared/ui/Brand.svelte';
  import type { BoardInfo } from '../../entities/board/types';
  let {
    count,
    boards,
    boardId,
    busy,
    onselect,
    oncreate,
    owner = $bindable(''),
    onhelp,
    onlogout,
  }: {
    count: number;
    boards: BoardInfo[];
    boardId: number;
    busy: boolean;
    onselect: (id: number) => void;
    oncreate: () => void;
    owner?: string;
    onhelp: () => void;
    onlogout: () => void;
  } = $props();
</script>

<aside class="sidebar">
  <Brand />
  <div class="workspace-label">
    <div>Workspace</div>
  </div>
  <p class="eyebrow">WORKSPACE</p>
  <div class="nav-active"><span>▦</span> Board <span class="count">{count}</span></div>
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
    <label for="owner">Your claim identity <kbd>O</kbd></label>
    <input id="owner" bind:value={owner} maxlength="100" placeholder="human" />
    <button class="quiet" onclick={onhelp}>Keyboard shortcuts <kbd>?</kbd></button>
    <button class="quiet" onclick={onlogout}>Sign out <kbd>⇧ L</kbd></button>
    <div class="version">PUNCTUAL <span>0.1</span></div>
  </div>
</aside>

<style>
  .board-picker {
    margin-top: var(--space-4);
    min-width: 0;
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
  .workspace-label {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 40px 0 35px;
    font-size: var(--text-sm);
  }
  .eyebrow {
    margin-bottom: 14px;
    font-size: var(--text-xs);
  }
  .nav-active {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    background: var(--surface-selected);
    color: var(--text-selected);
    padding: var(--space-3);
    border-radius: var(--radius-control);
    box-shadow: var(--shadow-selected);
  }
  .count {
    margin-left: auto;
  }
  .sidebar-bottom {
    margin-top: auto;
    padding-top: 80px;
  }
  input {
    font-size: var(--text-sm);
    margin: var(--space-2) 0 var(--space-5);
  }
  .quiet {
    width: 100%;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--space-2);
    font-size: var(--text-xs);
  }
  .version {
    border-top: 1px solid var(--border-subtle);
    margin-top: var(--space-6);
    padding-top: var(--space-5);
    font-size: 8px;
    letter-spacing: 1px;
    color: var(--text-muted);
  }
  .version span {
    float: right;
    color: var(--text-muted);
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
      border-bottom: 1px solid var(--border-subtle);
    }
    .eyebrow,
    .workspace-label,
    .nav-active,
    .version {
      display: none;
    }
    .sidebar-bottom {
      padding: 0;
      margin: 0 0 0 auto;
      display: flex;
      gap: 12px;
    }
    .sidebar-bottom label,
    input,
    kbd {
      display: none;
    }
    .quiet {
      width: auto;
    }
  }
</style>
