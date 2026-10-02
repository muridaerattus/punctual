<script lang="ts">
  let { search = $bindable('') }: { search?: string } = $props();
</script>

<label class="search">
  <span aria-hidden="true">⌕</span>
  <input
    id="task-search"
    aria-label="Search tasks"
    placeholder="Search tasks…"
    bind:value={search}
    onkeydown={(event) => {
      if (event.key === 'Escape') {
        search = '';
        event.currentTarget.blur();
      }
    }}
  />
  <kbd>/</kbd>
</label>

<style>
  .search {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
    width: 100%;
  }
  input {
    flex: 1;
    min-width: 0;
    width: 100%;
    border: 0;
    background: transparent;
    margin: 0;
    padding: 6px;
    font-size: var(--text-base);
  }
  .search > span {
    font-size: var(--text-heading);
  }
  kbd {
    flex-shrink: 0;
    font-size: var(--text-xs);
  }
</style>
