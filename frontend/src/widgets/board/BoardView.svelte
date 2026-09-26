<script lang="ts">
  import BoardColumn from './BoardColumn.svelte';
  import BoardFooter from './BoardFooter.svelte';
  import BoardToolbar from './BoardToolbar.svelte';
  import TaskActions from './TaskActions.svelte';
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
  <header>
    <div class="breadcrumb">Workspace <span>/</span> <strong>{board.boardName}</strong></div>
    <span class="connection"><i></i> Connected · refreshes every 5s</span>
  </header>
  <section class="board-heading">
    <div>
      <h1>Board</h1>
    </div>
    <button class="primary" onclick={() => onedit({})}>+ New task <kbd>N</kbd></button>
  </section>
  <BoardToolbar
    bind:search={board.search}
    busy={board.busy}
    completion={board.completion}
    onrefresh={() => board.refresh()}
  />
  {#if board.error}<div class="error" role="alert">
      {board.error} <button onclick={() => board.refresh()}>Refresh board</button>
    </div>{/if}
  <div class="notice" role="status">
    {board.notice || `${board.filtered.length} tasks · select a card to take action`}
  </div>
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
  <BoardFooter {onhelp} />
</main>

<style>
  .board-main {
    flex: 1;
    min-width: 0;
    padding: 0 38px;
    display: flex;
    flex-direction: column;
  }
  header {
    height: 83px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid #28312a;
    font-size: 11px;
  }
  .breadcrumb {
    color: #7e8c81;
    display: flex;
    gap: 17px;
  }
  strong {
    color: #c3cec5;
    font-weight: 400;
  }
  .connection {
    font-size: 10px;
    color: #8d9e90;
  }
  i {
    width: 6px;
    height: 6px;
    background: #b8dc90;
    border-radius: 50%;
    display: inline-block;
    margin-right: 7px;
  }
  .board-heading {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 42px 0 30px;
  }
  .notice {
    font-size: 10px;
    color: #809082;
    min-height: 40px;
    padding: 14px 0 10px;
  }
  .columns {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 22px;
    flex: 1;
    align-items: start;
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
    .connection {
      display: none;
    }
  }
  @media (max-width: 760px) {
    .board-main {
      padding: 0 18px;
    }
    header {
      height: 50px;
    }
    .board-heading {
      padding: 25px 0;
    }
    h1 {
      font-size: 32px;
    }
    .columns {
      grid-template-columns: 1fr;
    }
  }
</style>
