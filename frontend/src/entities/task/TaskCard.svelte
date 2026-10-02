<script lang="ts">
  import type { Task } from './types';
  let {
    task,
    selected,
    subtaskCount,
    onselect,
    onedit,
  }: {
    task: Task;
    selected: boolean;
    subtaskCount: number;
    onselect: (id: number) => void;
    onedit: (task: Task) => void;
  } = $props();

  const hasFooter = $derived(Boolean(task.assignee || subtaskCount || task.lease_owner));
</script>

<button
  id={`task-${task.id}`}
  class:chosen={selected}
  class="task"
  onclick={() => onselect(task.id)}
  onfocus={() => onselect(task.id)}
  ondblclick={() => onedit(task)}
  onkeydown={(event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      onedit(task);
    }
  }}
>
  <span class="task-meta">
    <span class="key">{task.key}</span>
    {#if task.parent_key}<span>↳ {task.parent_key}</span>{/if}
  </span>
  <h3>{task.title}</h3>
  {#if task.description}<p class="task-description">{task.description}</p>{/if}
  {#if hasFooter}
    <span class="task-footer">
      {#if task.assignee}<span class="assignee">@{task.assignee}</span>{/if}
      {#if subtaskCount}<span
          >{subtaskCount}
          {subtaskCount === 1 ? 'subtask' : 'subtasks'}</span
        >{/if}
      {#if task.lease_owner}<span class="lease" title="Claimed by {task.lease_owner}"
          >⌑ {task.lease_owner}</span
        >{/if}
    </span>
  {/if}
</button>

<style>
  .task {
    display: block;
    text-align: left;
    padding: var(--space-3);
    background: var(--surface-card);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-card);
    box-shadow: var(--shadow-card);
    width: 100%;
    min-width: 0;
    transition:
      background-color var(--motion-fast) var(--motion-ease),
      border-color var(--motion-fast) var(--motion-ease),
      box-shadow var(--motion-fast) var(--motion-ease);
  }
  .task:hover {
    background: var(--surface-hover);
    border-color: var(--border-hover);
  }
  .chosen,
  .chosen:hover {
    border-color: var(--border-selected);
    background: var(--surface-selected);
    box-shadow: var(--shadow-selected);
  }
  .task-meta {
    display: flex;
    gap: var(--space-2);
    font-size: var(--text-xs);
    line-height: 1.4;
    color: var(--text-muted);
    margin-bottom: var(--space-1);
    flex-wrap: wrap;
  }
  .key {
    letter-spacing: 0.3px;
  }
  h3 {
    overflow-wrap: anywhere;
    line-height: 1.4;
  }
  .task-description {
    font-size: var(--text-sm);
    color: var(--text-secondary);
    line-height: 1.55;
    margin-top: var(--space-1);
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
  .task-footer {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-1) var(--space-3);
    margin-top: var(--space-2);
    font-size: var(--text-xs);
    line-height: 1.4;
    color: var(--text-muted);
  }
  .assignee {
    color: var(--text-secondary);
  }
  .lease {
    margin-left: auto;
    color: var(--warning);
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  @media (min-width: 1500px) {
    .task {
      padding: 14px;
    }
  }
</style>
