<script lang="ts">
  import TaskCard from '../../entities/task/TaskCard.svelte';
  import type { Status, Task } from '../../entities/task/types';
  let {
    status,
    index,
    tasks,
    subtaskCounts,
    selected,
    onselect,
    onedit,
    oncreate,
  }: {
    status: Status;
    index: number;
    tasks: Task[];
    subtaskCounts: Map<number, number>;
    selected: number | null;
    onselect: (id: number) => void;
    onedit: (task: Task) => void;
    oncreate: (status: Status) => void;
  } = $props();
</script>

<section class="column" aria-label={status}>
  <div class="column-header">
    <span class={`status-dot dot-${index}`}></span>
    <h2>{status}</h2>
    <span class="count">{tasks.length}</span>
    <span class="column-key"><kbd>{index + 1}</kbd></span>
    <button aria-label={`New ${status} task`} onclick={() => oncreate(status)}>+</button>
  </div>
  <div class="cards">
    {#each tasks as task (task.id)}
      <TaskCard
        {task}
        selected={selected === task.id}
        subtaskCount={subtaskCounts.get(task.id) || 0}
        {onselect}
        {onedit}
      />
    {/each}
    {#if !tasks.length}
      <div class="empty">
        <span>＋</span>
        <p>No tasks to display.</p>
      </div>
    {/if}
    <button class="add-task" onclick={() => oncreate(status)}>+ Add task</button>
  </div>
</section>

<style>
  .column {
    min-width: 0;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }
  .column-header {
    display: flex;
    align-items: center;
    gap: 9px;
    padding: 8px 0 16px;
    border-bottom: 1px solid var(--border-default);
    margin-bottom: 10px;
    flex-shrink: 0;
  }
  h2 {
    font:
      500 12px 'DM Sans',
      sans-serif;
    letter-spacing: 0;
  }
  .status-dot {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    border: 1px solid var(--text-muted);
  }
  .dot-1 {
    background: var(--warning);
    border-color: var(--warning);
    box-shadow: inset 3px 0 var(--surface-canvas);
  }
  .dot-2 {
    background: var(--accent);
    border-color: var(--accent);
  }
  .column-key {
    margin-left: auto;
  }
  .column-header button {
    background: transparent;
    border: 0;
    padding: 0 3px;
    color: var(--text-muted);
    font-size: 18px;
  }
  .cards {
    display: flex;
    flex-direction: column;
    gap: 10px;
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    overscroll-behavior: contain;
    scroll-padding: 6px 0;
    margin: 0 -6px;
    padding: 4px 6px 12px;
    scrollbar-width: thin;
    scrollbar-color: var(--border-default) transparent;
  }
  .cards > :global(*) {
    flex-shrink: 0;
  }
  .add-task {
    border: 1px dashed var(--border-default);
    background: transparent;
    text-align: left;
    color: var(--text-muted);
    font-size: 11px;
    padding: 12px;
  }
  .empty {
    border: 1px dashed var(--border-subtle);
    border-radius: var(--radius-control);
    padding: 38px 8px;
    text-align: center;
    color: var(--text-muted);
    font-size: 10px;
  }
  .empty > span {
    font-size: 25px;
    font-weight: 400;
    display: block;
    margin-bottom: 12px;
  }
  @media (max-width: 760px) {
    .column {
      margin-bottom: 20px;
    }
    .cards {
      overflow-y: visible;
    }
    .column-key {
      display: none;
    }
  }
</style>
