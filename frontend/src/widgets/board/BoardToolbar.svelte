<script lang="ts">
  import OverflowMenu from '../../shared/ui/OverflowMenu.svelte';

  let {
    search = $bindable(''),
    busy,
    onrefresh,
  }: {
    search?: string;
    busy: boolean;
    onrefresh: () => void;
  } = $props();
</script>

<div class="toolbar">
  <label class="search">
    <span>⌕</span>
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
  <div class="actions">
    <OverflowMenu
      label="Board actions"
      items={[{ label: 'Refresh board', shortcut: 'G', disabled: busy, onselect: onrefresh }]}
    />
  </div>
</div>

<style>
  .toolbar {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 13px 0;
    border-top: 1px solid #28312a;
    border-bottom: 1px solid #28312a;
  }
  .search {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 160px;
    width: 270px;
  }
  input {
    border: 0;
    background: transparent;
    margin: 0;
    padding: 6px;
    font-size: 12px;
  }
  .search > span {
    font-size: 21px;
  }
  .actions {
    margin-left: auto;
  }
  @media (max-width: 760px) {
    .toolbar {
      gap: 6px;
    }
    .search {
      width: auto;
      flex: 1;
    }
    input {
      min-width: 0;
    }
  }
</style>
