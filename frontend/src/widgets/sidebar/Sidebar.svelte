<script lang="ts">
  import Brand from '../../shared/ui/Brand.svelte';
  import type { BoardInfo } from '../../entities/task/types';
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
    <span class="online"></span>
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
    margin-top: 16px;
    min-width: 0;
  }
  .sidebar {
    width: 230px;
    flex-shrink: 0;
    background: #131816;
    border-right: 1px solid #28312b;
    padding: 32px 22px;
    display: flex;
    flex-direction: column;
  }
  .workspace-label {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 40px 0 35px;
    font-size: 12px;
  }
  .online {
    width: 6px;
    height: 6px;
    background: #b8dc90;
    border-radius: 50%;
    margin-left: auto;
  }
  .eyebrow {
    margin-bottom: 14px;
    font-size: 9px;
  }
  .nav-active {
    display: flex;
    align-items: center;
    gap: 12px;
    background: #283321;
    color: #d4e9bf;
    padding: 11px 12px;
    border-radius: 6px;
  }
  .count {
    margin-left: auto;
  }
  .sidebar-bottom {
    margin-top: auto;
    padding-top: 80px;
  }
  input {
    font-size: 12px;
    margin: 8px 0 20px;
  }
  .quiet {
    width: 100%;
    display: flex;
    justify-content: space-between;
    padding: 9px 0;
    font-size: 11px;
  }
  .version {
    border-top: 1px solid #2a322c;
    margin-top: 24px;
    padding-top: 20px;
    font-size: 8px;
    letter-spacing: 1px;
    color: #758172;
  }
  .version span {
    float: right;
    color: #4e5d52;
  }
  @media (max-width: 1100px) {
    .sidebar {
      width: 185px;
      padding: 28px 15px;
    }
  }
  @media (max-width: 760px) {
    .sidebar {
      width: 100%;
      padding: 16px 20px;
      flex-direction: row;
      align-items: center;
      flex-wrap: wrap;
      gap: 16px;
      border-bottom: 1px solid #28312a;
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
