<script lang="ts">
  import { onMount, untrack } from 'svelte';
  import Modal from '../../shared/ui/Modal.svelte';
  import { statuses, type Task, type TaskInput } from '../../entities/task/types';
  import type { EditorOptions } from './types';
  let {
    options,
    tasks,
    busy,
    error,
    onsave,
    onclose,
  }: {
    options: EditorOptions;
    tasks: Task[];
    busy: boolean;
    error: string;
    onsave: (input: TaskInput, original?: Task) => void;
    onclose: () => void;
  } = $props();
  const original = untrack(() => options.task);
  let title = $state(original?.title ?? '');
  let description = $state(original?.description ?? '');
  let status = $state(untrack(() => original?.status ?? options.status ?? 'To Do'));
  let assignee = $state(original?.assignee ?? '');
  let parent = $state<number | null>(
    untrack(() => original?.parent_id ?? options.parentId ?? null),
  );
  let form: HTMLFormElement;
  let titleInput: HTMLInputElement;
  onMount(() => titleInput.focus());

  function save(event: SubmitEvent) {
    event.preventDefault();
    onsave(
      { title, description, status, assignee: assignee.trim() || null, parent_id: parent },
      original,
    );
  }
  function keyboard(event: KeyboardEvent) {
    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
      event.preventDefault();
      form.requestSubmit();
    }
  }
</script>

<svelte:window onkeydown={keyboard} />
<Modal label={original ? 'Edit task' : 'New task'} {onclose}>
  <form bind:this={form} onsubmit={save}>
    <div class="dialog-heading">
      <div>
        {#if original}
          <p class="eyebrow">PUN-{original.id} / REVISION {original.revision}</p>
        {/if}
        <h2>{original ? 'Edit task' : parent ? 'New subtask' : 'New task'}</h2>
      </div>
      <button type="button" class="quiet" onclick={onclose} aria-label="Close editor"
        >✕ <kbd>Esc</kbd></button
      >
    </div>
    <label
      >Title<input
        bind:this={titleInput}
        bind:value={title}
        required
        maxlength="300"
        placeholder="Task title"
      /></label
    >
    <label
      >Description<textarea
        bind:value={description}
        maxlength="50000"
        rows="6"
        placeholder="Task details"></textarea></label
    >
    <div class="form-row">
      <label
        >Status<select bind:value={status}
          >{#each statuses as value}<option>{value}</option>{/each}</select
        ></label
      >
      <label>Assignee<input bind:value={assignee} maxlength="100" placeholder="Unassigned" /></label
      >
    </div>
    <label
      >Parent task
      <select bind:value={parent}>
        <option value={null}>None — top-level task</option>
        {#each tasks.filter((task) => !task.parent_id && task.id !== original?.id) as task}
          <option value={task.id}>PUN-{task.id} · {task.title}</option>
        {/each}
      </select>
    </label>
    {#if error}<p class="error" role="alert">
        {error} Close and reopen the task to load its latest revision; your draft is kept here until you
        close.
      </p>{/if}
    <div class="dialog-actions">
      <button type="button" class="quiet" onclick={onclose}>Cancel</button>
      <button class="primary" disabled={busy}>Save task <kbd>⌘/Ctrl ↵</kbd></button>
    </div>
  </form>
</Modal>

<style>
  form {
    display: grid;
    gap: 18px;
  }
  .eyebrow {
    margin-bottom: 8px;
  }
  .quiet {
    font-size: 11px;
  }
  .form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 15px;
  }
</style>
