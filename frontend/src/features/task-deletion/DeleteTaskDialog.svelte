<script lang="ts">
  import Modal from '../../shared/ui/Modal.svelte';
  import type { Task } from '../../entities/task/types';
  let {
    task,
    busy,
    error,
    ondelete,
    onclose,
  }: {
    task: Task;
    busy: boolean;
    error: string;
    ondelete: () => void;
    onclose: () => void;
  } = $props();
</script>

<Modal label="Delete task" {onclose}>
  <h2>Delete PUN-{task.id}?</h2>
  <p>This permanently deletes “{task.title}”.</p>
  {#if error}<p class="error" role="alert">{error}</p>{/if}
  <div class="dialog-actions">
    <button onclick={onclose}>Cancel <kbd>Esc</kbd></button>
    <button class="danger" disabled={busy} onclick={ondelete}>Delete task</button>
  </div>
</Modal>

<style>
  p {
    margin-top: 16px;
    line-height: 1.6;
  }
</style>
