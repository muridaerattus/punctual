<script lang="ts">
  let { onhelp }: { onhelp: () => void } = $props();
</script>

<footer>
  <span><span class="accent">●</span> One fewer dimension.</span>
  <span>
    <kbd>J</kbd> <kbd>K</kbd> navigate <span class="divider">/</span>
    <kbd>Enter</kbd> open <span class="divider">/</span>
    <button onclick={onhelp}><kbd>?</kbd> all shortcuts</button>
  </span>
</footer>

<style>
  footer {
    display: flex;
    justify-content: space-between;
    gap: 10px;
    padding: 23px 0;
    font-size: 10px;
    color: #7f927a;
  }
  kbd {
    font-size: 9px;
  }
  .accent {
    font-size: 8px;
    margin-right: 7px;
  }
  .divider {
    color: #455641;
    margin: 0 9px;
  }
  button {
    border: 0;
    background: transparent;
    padding: 0;
    color: inherit;
    font-size: inherit;
  }
  @media (max-width: 760px) {
    footer {
      flex-wrap: wrap;
    }
  }
</style>
