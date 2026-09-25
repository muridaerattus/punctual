<script lang="ts">
  import { onMount, type Snippet } from 'svelte';
  let { children, onclose, label }: { children: Snippet; onclose: () => void; label: string } =
    $props();
  let dialog: HTMLDialogElement;
  onMount(() => dialog.showModal());
</script>

<dialog bind:this={dialog} aria-label={label} {onclose}>
  {@render children()}
</dialog>

<style>
  dialog {
    width: min(580px, calc(100vw - 32px));
    border: 1px solid #47513f;
    background: #19201b;
    border-radius: 12px;
    color: #e3e7e4;
    padding: 28px;
    box-shadow: 0 30px 100px #0008;
    max-height: 90vh;
  }
  dialog::backdrop {
    background: #050c08b5;
    backdrop-filter: blur(4px);
  }
</style>
