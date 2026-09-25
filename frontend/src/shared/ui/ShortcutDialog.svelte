<script lang="ts">
  import Modal from './Modal.svelte';
  let {
    onclose,
    shortcuts,
  }: {
    onclose: () => void;
    shortcuts: readonly (readonly [string, string])[];
  } = $props();
</script>

<Modal label="Keyboard shortcuts" {onclose}>
  <div class="dialog-heading">
    <h2>Stay on the keyboard.</h2>
    <button onclick={onclose} aria-label="Close shortcuts">✕</button>
  </div>
  <p class="muted">Shortcuts work outside text fields. Tab reaches every control.</p>
  <div class="shortcuts">
    {#each shortcuts as [shortcut, action]}
      <div><span>{action}</span><kbd>{shortcut}</kbd></div>
    {/each}
  </div>
</Modal>

<style>
  p {
    margin-top: 16px;
  }
  .shortcuts {
    margin-top: 20px;
  }
  .shortcuts > div {
    display: flex;
    justify-content: space-between;
    gap: 15px;
    border-bottom: 1px solid #303b31;
    padding: 10px 0;
    font-size: 12px;
    color: #a7b4a3;
  }
</style>
