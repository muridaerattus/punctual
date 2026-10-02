<script lang="ts">
  let { message, duration = 3000 }: { message: string; duration?: number } = $props();
  let shown = $state('');

  $effect(() => {
    shown = message;
    if (!message) return;
    const timer = setTimeout(() => (shown = ''), duration);
    return () => clearTimeout(timer);
  });
</script>

<div class="toast-region" role="status" aria-live="polite">
  {#if shown}<div class="toast">{shown}</div>{/if}
</div>

<style>
  .toast-region {
    position: absolute;
    top: calc(100% + 10px);
    left: 50%;
    transform: translateX(-50%);
    z-index: 20;
    pointer-events: none;
  }
  .toast {
    background: #2a352c;
    border: 1px solid #5a7246;
    border-radius: 6px;
    padding: 9px 14px;
    font-size: 11px;
    color: #dce8d4;
    white-space: nowrap;
    box-shadow: 0 8px 24px rgb(0 0 0 / 35%);
    animation: toast-in 140ms ease-out;
  }
  @keyframes toast-in {
    from {
      opacity: 0;
      transform: translateY(-4px);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .toast {
      animation: none;
    }
  }
  @media (max-width: 760px) {
    .toast-region {
      width: max-content;
      max-width: 100%;
    }
    .toast {
      white-space: normal;
    }
  }
</style>
