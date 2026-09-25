<script lang="ts">
  import { statuses, type LeaseAction, type Status, type Task } from '../../entities/task/types';
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
</script>

<section class="actionbar" aria-label="Selected task actions">
  <span class="selected-label">PUN-{task.id}</span>
  <button onclick={onedit}>Edit <kbd>E</kbd></button>
  <button disabled={!!task.parent_id} onclick={onsubtask}>Subtask <kbd>S</kbd></button>
  <label
    >Move
    <select
      aria-label="Move selected task"
      value={task.status}
      onchange={(event) => onmove(event.currentTarget.value as Status)}
    >
      {#each statuses as status, index}<option value={status}>{status} ({index + 1})</option>{/each}
    </select>
  </label>
  {#if task.lease_owner}
    <button onclick={() => onlease('renew')} disabled={!ownsLease}>Renew <kbd>R</kbd></button>
    <button onclick={() => onlease('release')} disabled={!ownsLease}>Release <kbd>U</kbd></button>
  {:else}
    <button onclick={() => onlease('claim')}>Claim <kbd>C</kbd></button>
  {/if}
  <button class="danger" onclick={ondelete}>Delete <kbd>X</kbd></button>
</section>

<style>
  .actionbar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 7px;
    margin: 25px 0 10px;
    padding: 12px;
    background: #171e18;
    border: 1px solid #303c30;
    border-radius: 7px;
  }
  button {
    font-size: 10px;
    padding: 7px 8px;
    background: transparent;
  }
  .selected-label {
    font-size: 10px;
    color: #b2c9a1;
    padding: 0 8px;
  }
  label {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 10px;
  }
  select {
    font-size: 10px;
    margin: 0;
    padding: 7px 2px;
  }
  .danger {
    margin-left: auto;
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
      box-shadow: 0 -10px 30px #101414;
    }
  }
</style>
