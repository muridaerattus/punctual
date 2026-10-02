<script lang="ts">
  import BoardColumn from './BoardColumn.svelte';
  import BoardFooter from './BoardFooter.svelte';
  import BoardToolbar from './BoardToolbar.svelte';
  import TaskActions from './TaskActions.svelte';
  import Toast from './Toast.svelte';
  import type { Board } from './board.svelte';
  import { statuses } from '../../entities/task/types';
  import type { EditorOptions } from '../../features/task-editor/types';
  let {
    board,
    onedit,
    onhelp,
    ondelete,
  }: {
    board: Board;
    onedit: (options: EditorOptions) => void;
    onhelp: () => void;
    ondelete: () => void;
  } = $props();
  const subtaskCounts = $derived.by(() => {
    const counts = new Map<number, number>();
    for (const task of board.tasks) {
      if (task.parent_id) counts.set(task.parent_id, (counts.get(task.parent_id) || 0) + 1);
    }
    return counts;
  });
</script>

<main class="board-main">
  <header class="board-header">
    <h1><span class="workspace">Workspace /</span> {board.boardName}</h1>
    <button class="primary" onclick={() => onedit({})}>+ New task <kbd>N</kbd></button>
    <Toast message={board.notice} />
  </header>
  <BoardToolbar bind:search={board.search} busy={board.busy} onrefresh={() => board.refresh()} />
  {#if board.error}<div class="error" role="alert">
      {board.error} <button onclick={() => board.refresh()}>Refresh board</button>
    </div>{/if}
  {#if board.refreshError}<div class="refresh-error" role="alert" title={board.refreshError}>
      Unable to refresh — showing last loaded tasks ·
      <button onclick={() => board.refresh()}>Retry</button>
    </div>{/if}
  <div class="columns">
    {#each statuses as status, index}
      <BoardColumn
        {status}
        {index}
        tasks={board.filtered.filter((task) => task.status === status)}
        {subtaskCounts}
        selected={board.selected}
        onselect={(id) => (board.selected = id)}
        onedit={(task) => onedit({ task })}
        oncreate={(status) => onedit({ status })}
      />
    {/each}
  </div>
  <div class="board-bottom">
    <div class="action-slot">
      {#if board.current}
        <TaskActions
          task={board.current}
          ownsLease={!!board.leases.tokens[board.current.id]}
          onedit={() => onedit({ task: board.current })}
          onsubtask={() => onedit({ parentId: board.current?.id })}
          onmove={(status) => board.move(status)}
          onlease={(action) => board.lease(action)}
          {ondelete}
        />
      {/if}
    </div>
    <BoardFooter {onhelp} />
  </div>
</main>

<style>
  .board-main {
    flex: 1;
    min-width: 0;
    padding: 0 38px;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }
  .board-header {
    position: relative;
    height: 60px;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
  }
  h1 {
    font-size: 21px;
    letter-spacing: -0.5px;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .workspace {
    color: var(--text-muted);
    font-weight: 400;
  }
  .refresh-error {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-top: 10px;
    font-size: 10px;
    color: var(--warning);
  }
  .refresh-error button {
    padding: 0;
    border: 0;
    background: none;
    color: inherit;
    font: inherit;
    text-decoration: underline;
    cursor: pointer;
  }
  .board-header .primary {
    flex-shrink: 0;
    padding: 8px 13px;
  }
  .columns {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 22px;
    flex: 1;
    min-height: 0;
    margin-top: 18px;
  }
  .board-bottom {
    flex-shrink: 0;
    padding-top: 14px;
  }
  .action-slot {
    height: 46px;
  }
  .action-slot > :global(.actionbar) {
    margin: 0;
  }
  .board-bottom > :global(footer) {
    padding: 8px 0 12px;
  }
  @media (min-width: 1500px) {
    .board-main {
      padding: 0 60px;
    }
    .columns {
      gap: 28px;
    }
  }
  @media (max-width: 1100px) {
    .board-main {
      padding: 0 22px;
    }
    .columns {
      gap: 12px;
    }
  }
  @media (max-width: 760px) {
    .board-main {
      padding: 0 18px;
    }
    .board-header {
      height: 56px;
    }
    h1 {
      font-size: 18px;
    }
    .workspace {
      display: none;
    }
    .columns {
      grid-template-columns: 1fr;
      flex: none;
    }
    .board-bottom,
    .action-slot {
      display: contents;
    }
    .action-slot > :global(.actionbar) {
      margin: 25px 0 10px;
    }
    .board-bottom > :global(footer) {
      padding: 23px 0;
    }
  }
</style>
