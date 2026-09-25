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
  <div class="task-meta">
    <span>PUN-{task.id}</span>
    {#if task.parent_id}<span>↳ PUN-{task.parent_id}</span>{/if}
    {#if task.lease_owner}<span class="lease">⌑ {task.lease_owner}</span>{/if}
  </div>
  <h3>{task.title}</h3>
  {#if task.description}<p class="task-description">{task.description}</p>{/if}
  <div class="task-footer">
    <span>{task.assignee ? `@${task.assignee}` : 'Unassigned'}</span>
    {#if subtaskCount}<span>↳ {subtaskCount} subtasks</span>{/if}
    <span>r{task.revision}</span>
  </div>
</button>

<style>
  .task {
    display: block;
    text-align: left;
    padding: 16px;
    background: #19201b;
    border: 1px solid #303a31;
    border-radius: 8px;
    width: 100%;
    min-width: 0;
  }
  .chosen {
    border-color: #8aa86d;
    background: #1e291e;
    box-shadow: 0 0 0 1px #8aa86d18;
  }
  .task:hover {
    background: #242e25;
    transform: translateY(-1px);
  }
  .task-meta {
    display: flex;
    gap: 8px;
    font-size: 9px;
    color: #94a28e;
    margin-bottom: 11px;
    flex-wrap: wrap;
  }
  .lease {
    margin-left: auto;
    color: #dac88e;
  }
  .task-description {
    font-size: 11px;
    color: #8a988b;
    line-height: 1.7;
    margin-top: 7px;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
  h3 {
    overflow-wrap: anywhere;
  }
  .task-footer {
    border-top: 1px solid #30392f;
    display: flex;
    gap: 8px;
    justify-content: space-between;
    margin-top: 17px;
    padding-top: 12px;
    font-size: 9px;
    color: #8d9d86;
  }
  .task-footer span:last-child {
    margin-left: auto;
    color: #64775f;
  }
  @media (min-width: 1500px) {
    .task {
      padding: 20px;
    }
  }
</style>
