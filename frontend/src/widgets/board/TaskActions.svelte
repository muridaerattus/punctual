<script lang="ts">
  import { statuses, type LeaseAction, type Status, type Task } from '../../entities/task/types';
  import OverflowMenu, { type MenuItem } from '../../shared/ui/OverflowMenu.svelte';
  let {
    task,
    ownsLease,
    onedit,
    onsubtask,
    onmove,
    onlease,
    ondelete,
  }: {
    task: Task;
    ownsLease: boolean;
    onedit: () => void;
    onsubtask: () => void;
    onmove: (status: Status) => void;
    onlease: (action: LeaseAction) => void;
    ondelete: () => void;
  } = $props();

  let now = $state(Date.now() / 1000);
  $effect(() => {
    const timer = setInterval(() => (now = Date.now() / 1000), 15_000);
    return () => clearInterval(timer);
  });

  const remaining = $derived.by(() => {
    if (!task.lease_expires_at) return '';
    const seconds = task.lease_expires_at - now;
    if (seconds <= 0) return 'expired';
    if (seconds < 60) return '<1m left';
    return `${Math.floor(seconds / 60)}m left`;
  });

  const menuItems: MenuItem[] = $derived([
    { label: 'Subtask', shortcut: 'S', disabled: !!task.parent_id, onselect: onsubtask },
    ...(task.lease_owner && ownsLease
      ? [
          { label: 'Renew lease', shortcut: 'R', onselect: () => onlease('renew') },
          { label: 'Release lease', shortcut: 'U', onselect: () => onlease('release') },
        ]
      : []),
    { label: 'Delete task', shortcut: 'X', danger: true, onselect: ondelete },
  ]);
</script>

<section class="actionbar" aria-label="Selected task actions">
  <span class="selected" title={`${task.key} ${task.title}`}>
    <span class="key">{task.key}</span>
    <span class="title">{task.title}</span>
  </span>
  <div class="actions">
    <button onclick={onedit}>Edit</button>
    <label
      >Move
      <select
        aria-label="Move selected task"
        value={task.status}
        onchange={(event) => onmove(event.currentTarget.value as Status)}
      >
        {#each statuses as status}<option value={status}>{status}</option>{/each}
      </select>
    </label>
    {#if !task.lease_owner}
      <button onclick={() => onlease('claim')}>Claim</button>
    {:else}
      <span
        class="lease"
        title={`Claimed by ${task.lease_owner}${remaining ? ` · ${remaining}` : ''}`}
      >
        <span class="lease-owner">Claimed by <strong>{task.lease_owner}</strong></span>
        {#if remaining}<span class="lease-expiry">· {remaining}</span>{/if}
      </span>
    {/if}
    <OverflowMenu label="More task actions" items={menuItems} placement="up" />
  </div>
</section>

<style>
  .actionbar {
    display: flex;
    flex-wrap: nowrap;
    align-items: center;
    gap: 12px;
    min-height: 44px;
    padding: 5px 6px 5px 12px;
    background: var(--surface-raised);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-control);
    min-width: 0;
  }
  .selected {
    flex: 1 1 0;
    min-width: 0;
    display: flex;
    align-items: baseline;
    gap: 9px;
    font-size: var(--text-sm);
    overflow: hidden;
  }
  .key {
    flex: none;
    color: var(--text-selected);
    font-size: var(--text-xs);
  }
  .title {
    color: var(--text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .actions {
    flex: 0 1 auto;
    min-width: 0;
    max-width: calc(100% - 80px);
    display: flex;
    flex-wrap: nowrap;
    align-items: center;
    gap: 6px;
  }
  button {
    font-size: var(--text-xs);
    padding: 6px 8px;
    background: transparent;
    white-space: nowrap;
  }
  label {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: var(--text-xs);
    white-space: nowrap;
  }
  select {
    font-size: var(--text-xs);
    margin: 0;
    padding: 6px 2px;
  }
  .lease {
    display: flex;
    align-items: baseline;
    gap: 4px;
    min-width: 0;
    flex: 0 1 220px;
    font-size: var(--text-xs);
    color: var(--text-muted);
    white-space: nowrap;
    max-width: 220px;
    padding: 0 4px;
  }
  .lease-owner {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .lease-expiry {
    flex: none;
  }
  .lease strong {
    color: var(--text-selected);
    font-weight: 400;
  }
  @media (max-width: 760px) {
    .actionbar {
      position: sticky;
      bottom: 0;
      flex-wrap: wrap;
      gap: 6px;
      box-shadow: var(--shadow-popover);
    }
    .selected {
      flex-basis: 100%;
    }
    .actions {
      flex-wrap: wrap;
      max-width: 100%;
    }
    .lease {
      max-width: 160px;
    }
  }
</style>
