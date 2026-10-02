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
    { label: 'Delete task', shortcut: 'X', danger: true, onselect: ondelete },
  ]);
</script>

<section class="actionbar" aria-label="Selected task actions">
  <span class="selected" title={`${task.key} ${task.title}`}>
    <span class="key">{task.key}</span>
    <span class="title">{task.title}</span>
  </span>
  <div class="actions">
    <button onclick={onedit}>Edit <kbd>E</kbd></button>
    <label
      >Move
      <select
        aria-label="Move selected task"
        value={task.status}
        onchange={(event) => onmove(event.currentTarget.value as Status)}
      >
        {#each statuses as status, index}<option value={status}>{status} ({index + 1})</option
          >{/each}
      </select>
    </label>
    <button disabled={!!task.parent_id} onclick={onsubtask}>Subtask <kbd>S</kbd></button>
    {#if !task.lease_owner}
      <button onclick={() => onlease('claim')}>Claim <kbd>C</kbd></button>
    {:else if ownsLease}
      <button onclick={() => onlease('renew')}>Renew <kbd>R</kbd></button>
      <button onclick={() => onlease('release')}>Release <kbd>U</kbd></button>
      {#if remaining}<span class="lease">{remaining}</span>{/if}
    {:else}
      <span class="lease" title={`Claimed by ${task.lease_owner}`}>
        Claimed by <strong>{task.lease_owner}</strong>{#if remaining}&nbsp;· {remaining}{/if}
      </span>
    {/if}
    <OverflowMenu label="More task actions" items={menuItems} placement="up" />
  </div>
</section>

<style>
  .actionbar {
    display: flex;
    align-items: center;
    gap: 12px;
    min-height: 44px;
    padding: 5px 6px 5px 12px;
    background: #171e18;
    border: 1px solid #303c30;
    border-radius: 7px;
    min-width: 0;
  }
  .selected {
    flex: 1 1 auto;
    min-width: 60px;
    display: flex;
    align-items: baseline;
    gap: 9px;
    font-size: 11px;
    overflow: hidden;
  }
  .key {
    flex: none;
    color: #b2c9a1;
    font-size: 10px;
  }
  .title {
    color: #c3cec5;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .actions {
    flex: none;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  button {
    font-size: 10px;
    padding: 6px 8px;
    background: transparent;
    white-space: nowrap;
  }
  label {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 10px;
    white-space: nowrap;
  }
  select {
    font-size: 10px;
    margin: 0;
    padding: 6px 2px;
  }
  .lease {
    font-size: 10px;
    color: #8d9e90;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 220px;
    padding: 0 4px;
  }
  .lease strong {
    color: #b2c9a1;
    font-weight: 400;
  }
  @media (max-width: 1100px) {
    kbd {
      display: none;
    }
  }
  @media (max-width: 760px) {
    .actionbar {
      position: sticky;
      bottom: 0;
      flex-wrap: wrap;
      gap: 6px;
      box-shadow: 0 -10px 30px #101414;
    }
    .selected {
      flex-basis: 100%;
    }
    .actions {
      flex-wrap: wrap;
    }
    .lease {
      max-width: 160px;
    }
  }
</style>
