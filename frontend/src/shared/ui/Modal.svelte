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
    border: 1px solid var(--border-default);
    background: var(--surface-raised);
    border-radius: var(--radius-dialog);
    color: var(--text-primary);
    padding: var(--space-7);
    box-shadow: var(--shadow-dialog);
    max-height: 90vh;
  }
  dialog::backdrop {
    background: var(--overlay);
    backdrop-filter: blur(4px);
  }
  @media (prefers-reduced-motion: no-preference) {
    dialog[open] {
      animation: dialog-enter var(--motion-moderate) var(--motion-ease);
    }
    @keyframes dialog-enter {
      from {
        opacity: 0;
        transform: translateY(6px) scale(0.99);
      }
      to {
        opacity: 1;
        transform: translateY(0) scale(1);
      }
    }
  }
</style>
