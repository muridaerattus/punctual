<script lang="ts">
  let {
    search = $bindable(''),
    busy,
    completion,
    onrefresh,
  }: {
    search?: string;
    busy: boolean;
    completion: number;
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
  <button class="quiet" onclick={onrefresh} disabled={busy}>↻ Refresh <kbd>G</kbd></button>
  <span class="progress-label">{completion}% complete</span>
  <div class="progress"><div style={`width:${completion}%`}></div></div>
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
  .quiet {
    font-size: 11px;
  }
  .progress-label {
    margin-left: auto;
    font-size: 10px;
    color: #8e9c90;
  }
  .progress {
    width: 80px;
    height: 4px;
    background: #2a332b;
    border-radius: 5px;
    overflow: hidden;
  }
  .progress > div {
    height: 100%;
    background: #bde991;
  }
  @media (max-width: 1100px) {
    .progress {
      display: none;
    }
  }
  @media (max-width: 760px) {
    .toolbar {
      gap: 6px;
    }
    .progress-label {
      display: none;
    }
    .quiet {
      white-space: nowrap;
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
