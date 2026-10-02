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
    padding: 12px;
    background: #19201b;
    border: 1px solid #303a31;
    border-radius: 8px;
    width: 100%;
    min-width: 0;
    transition:
      background-color 0.12s ease,
      border-color 0.12s ease;
  }
  .task:hover {
    background: #222b23;
    border-color: #3d4a3e;
  }
  .chosen,
  .chosen:hover {
    border-color: #8aa86d;
    background: #1e291e;
    box-shadow: 0 0 0 1px #8aa86d18;
  }
  .task-meta {
    display: flex;
    gap: 8px;
    font-size: 9px;
    line-height: 1.4;
    color: #75846f;
    margin-bottom: 4px;
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
    font-size: 11px;
    color: #8a988b;
    line-height: 1.55;
    margin-top: 4px;
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
    gap: 4px 10px;
    margin-top: 8px;
    font-size: 9px;
    line-height: 1.4;
    color: #8d9d86;
  }
  .assignee {
    color: #a7b6a0;
  }
  .lease {
    margin-left: auto;
    color: #dac88e;
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
