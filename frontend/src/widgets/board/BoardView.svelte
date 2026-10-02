<script lang="ts">
  import BoardColumn from './BoardColumn.svelte';
  import BoardToolbar from './BoardToolbar.svelte';
  import TaskActions from './TaskActions.svelte';
  import Toast from './Toast.svelte';
  import type { Board } from './board.svelte';
  import { statuses } from '../../entities/task/types';
  import type { EditorOptions } from '../../features/task-editor/types';
  import OverflowMenu from '../../shared/ui/OverflowMenu.svelte';
  let {
    board,
    onedit,
    ondelete,
  }: {
    board: Board;
    onedit: (options: EditorOptions) => void;
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
    <div class="board-identity">
      <h1 title={board.boardName}>{board.boardName}</h1>
      <OverflowMenu
        label="Board actions"
        items={[
          {
            label: 'Refresh board',
            shortcut: 'G',
            disabled: board.busy,
            onselect: () => board.refresh(),
          },
        ]}
      />
    </div>
    <div class="board-search"><BoardToolbar bind:search={board.search} /></div>
    <button class="primary" onclick={() => onedit({})}>+ New task <kbd>N</kbd></button>
    <Toast message={board.notice} />
  </header>
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
        filtering={!!board.search.trim()}
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
    container-type: inline-size;
  }
  .board-header {
    position: relative;
    min-height: 68px;
    flex-shrink: 0;
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(160px, 270px) auto;
    align-items: center;
    gap: 16px;
    padding: 12px 0;
    border-bottom: 1px solid var(--border-subtle);
  }
  .board-identity {
    position: relative;
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
  }
  .board-identity > :global(.overflow) {
    flex-shrink: 0;
    position: static;
  }
  .board-identity :global(.menu) {
    left: 0;
    right: auto;
  }
  .board-search {
    min-width: 0;
  }
  h1 {
    font-size: var(--text-heading);
    font-family: var(--font-heading);
    line-height: 1.25;
    margin: 0;
    letter-spacing: -0.5px;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .refresh-error {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-top: 10px;
    font-size: var(--text-sm);
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
    font-size: var(--text-sm);
    white-space: nowrap;
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
    padding: 14px 0 12px;
  }
  .action-slot {
    height: 48px;
  }
  .action-slot > :global(.actionbar) {
    margin: 0;
  }
  @container (max-width: 620px) {
    .board-header {
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 10px 12px;
    }
    .board-search {
      grid-column: 1 / -1;
      grid-row: 2;
    }
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
  }
</style>
