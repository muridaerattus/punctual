<script lang="ts">
  import TaskCard from '../../entities/task/TaskCard.svelte';
  import type { Status, Task } from '../../entities/task/types';
  let {
    status,
    index,
    tasks,
    filtering = false,
    subtaskCounts,
    selected,
    onselect,
    onedit,
    oncreate,
  }: {
    status: Status;
    index: number;
    tasks: Task[];
    filtering?: boolean;
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
      <p class="empty">{filtering ? 'No matching tasks' : 'No tasks yet'}</p>
    {/if}
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
    font-family: var(--font-body);
    font-size: var(--text-sm);
    font-weight: 500;
    letter-spacing: 0;
  }
  .status-dot {
    flex-shrink: 0;
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
  .column-header button {
    margin-left: auto;
    background: transparent;
    border: 0;
    padding: 0 3px;
    color: var(--text-muted);
    font-size: var(--text-heading);
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
  .empty {
    padding: var(--space-3) 0;
    color: var(--text-muted);
    font-size: var(--text-sm);
  }
  @media (max-width: 760px) {
    .column {
      margin-bottom: 20px;
    }
    .cards {
      overflow-y: visible;
    }
  }
</style>
