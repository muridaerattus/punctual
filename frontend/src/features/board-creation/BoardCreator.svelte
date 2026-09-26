<script lang="ts">
  import { onMount } from 'svelte';
  import Modal from '../../shared/ui/Modal.svelte';
  let {
    busy,
    error,
    oncreate,
    onclose,
  }: {
    busy: boolean;
    error: string;
    oncreate: (name: string, prefix: string) => void;
    onclose: () => void;
  } = $props();
  let name = $state('');
  let prefix = $state('');
  let nameInput: HTMLInputElement;
  onMount(() => nameInput.focus());
</script>

<Modal label="New board" {onclose}>
  <form
    onsubmit={(event) => {
      event.preventDefault();
      oncreate(name, prefix);
    }}
  >
    <h2>New board</h2>
    <label
      >Name<input
        bind:this={nameInput}
        bind:value={name}
        required
        maxlength="100"
        pattern=".*\S.*"
      /></label
    >
    <label
      >Ticket prefix<input
        bind:value={prefix}
        required
        maxlength="8"
        pattern={'[A-Z]{1,8}'}
        aria-describedby="prefix-help"
      /></label
    >
    <p id="prefix-help" class="muted">
      1–8 capital letters, unique to this board. Prefixes cannot be changed.
    </p>
    {#if error}<p class="error" role="alert">{error}</p>{/if}
    <div class="dialog-actions">
      <button type="button" class="quiet" onclick={onclose}>Cancel</button>
      <button class="primary" disabled={busy}>Create board</button>
    </div>
  </form>
</Modal>

<style>
  form {
    display: grid;
    gap: 18px;
  }
</style>
