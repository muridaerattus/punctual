<script lang="ts">
  let { onhelp }: { onhelp: () => void } = $props();
</script>

<footer>
  <span class="hint"><kbd>J</kbd> <kbd>K</kbd> navigate</span>
  <span class="divider">/</span>
  <span class="hint"><kbd>Enter</kbd> open</span>
  <span class="divider">/</span>
  <button onclick={onhelp} aria-label="Show all keyboard shortcuts"><kbd>?</kbd> shortcuts</button>
</footer>

<style>
  footer {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: 7px;
    padding: 4px 0;
    font-size: 10px;
    line-height: 1;
    color: #7f927a;
    white-space: nowrap;
  }
  kbd {
    font-size: 9px;
    padding: 1px 4px;
  }
  .divider {
    color: #455641;
  }
  button {
    border: 0;
    background: transparent;
    padding: 0;
    color: inherit;
    font-size: inherit;
  }
  @media (max-width: 760px) {
    .hint,
    .divider {
      display: none;
    }
  }
</style>
