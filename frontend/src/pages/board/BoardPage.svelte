<script lang="ts">
  import { onMount, tick, untrack } from 'svelte';
  import BoardView from '../../widgets/board/BoardView.svelte';
  import DeleteTaskDialog from '../../features/task-deletion/DeleteTaskDialog.svelte';
  import ShortcutDialog from '../../shared/ui/ShortcutDialog.svelte';
  import Sidebar from '../../widgets/sidebar/Sidebar.svelte';
  import TaskEditor from '../../features/task-editor/TaskEditor.svelte';
  import BoardCreator from '../../features/board-creation/BoardCreator.svelte';
  import { Board } from '../../widgets/board/board.svelte';
  import { handleShortcut } from '../../shared/keyboard/shortcuts';
  import type { EditorOptions } from '../../features/task-editor/types';
  import type { Status, Task, TaskInput } from '../../entities/task/types';
  import type { TaskApi } from '../../entities/task/api';
  import type { BoardApi } from '../../entities/board/api';
  import type { LeaseState } from '../../entities/task/lease-state.svelte';
  import { boardShortcuts, shortcutReference } from './shortcuts';

  let {
    api,
    boardApi,
    leases,
    initialTasks,
    onlogout,
  }: {
    api: TaskApi;
    boardApi: BoardApi;
    leases: LeaseState;
    initialTasks: Task[];
    onlogout: () => void;
  } = $props();
  const board = untrack(() => new Board(api, boardApi, leases, initialTasks));
  let editor = $state<EditorOptions | null>(null);
  let deleting = $state<Task | null>(null);
  let help = $state(false);
  let creatingBoard = $state(false);
  const modalOpen = $derived(!!editor || !!deleting || help || creatingBoard);

  function openEditor(options: EditorOptions = {}) {
    board.error = '';
    editor = options;
  }
  function askDelete() {
    board.error = '';
    deleting = board.current ?? null;
  }
  async function focusCard() {
    await tick();
    const card = document.getElementById(`task-${board.selected}`);
    card?.focus({ preventScroll: true });
    card?.scrollIntoView({ block: 'nearest' });
  }
  async function navigate(delta: number) {
    board.navigate(delta);
    await focusCard();
  }
  async function move(status: Status) {
    await board.move(status);
    await focusCard();
  }
  async function save(input: TaskInput, original?: Task) {
    if (await board.save(input, original)) {
      editor = null;
      await focusCard();
    }
  }
  async function remove() {
    if (deleting && (await board.remove(deleting))) {
      deleting = null;
      await focusCard();
    }
  }
  function keyboard(event: KeyboardEvent) {
    handleShortcut(
      event,
      boardShortcuts({
        create: () => openEditor(),
        edit: () => board.current && openEditor({ task: board.current }),
        subtask: () =>
          board.current && !board.current.parent_id && openEditor({ parentId: board.current.id }),
        search: () => document.getElementById('task-search')?.focus(),
        help: () => (help = true),
        next: () => navigate(1),
        previous: () => navigate(-1),
        todo: () => move('To Do'),
        inProgress: () => move('In Progress'),
        complete: () => move('Complete'),
        claim: () => board.lease('claim'),
        renew: () => board.lease('renew'),
        release: () => board.lease('release'),
        delete: askDelete,
        refresh: () => board.refresh(),
        identity: () => document.getElementById('owner')?.focus(),
        logout: onlogout,
      }),
      !modalOpen,
    );
  }
  onMount(() => {
    board.loadBoards();
    const timer = setInterval(() => {
      if (!board.busy && !modalOpen) board.poll();
    }, 5000);
    return () => clearInterval(timer);
  });
</script>

<svelte:window onkeydown={keyboard} />

<div class="workspace">
  <Sidebar
    count={board.tasks.length}
    boards={board.boards}
    boardId={board.boardId}
    busy={board.busy || modalOpen}
    onselect={(id) => board.selectBoard(id)}
    oncreate={() => {
      board.error = '';
      creatingBoard = true;
    }}
    bind:owner={board.leases.owner}
    onhelp={() => (help = true)}
    {onlogout}
  />
  <BoardView {board} onedit={openEditor} onhelp={() => (help = true)} ondelete={askDelete} />
</div>
{#if creatingBoard}
  <BoardCreator
    busy={board.busy}
    error={board.error}
    oncreate={async (name, prefix) => {
      if (await board.createBoard(name, prefix)) creatingBoard = false;
    }}
    onclose={() => (creatingBoard = false)}
  />
{/if}
{#if editor}
  <TaskEditor
    options={editor}
    tasks={board.tasks}
    busy={board.busy}
    error={board.error}
    onsave={save}
    onclose={() => (editor = null)}
  />
{/if}
{#if deleting}
  <DeleteTaskDialog
    task={deleting}
    busy={board.busy}
    error={board.error}
    ondelete={remove}
    onclose={() => (deleting = null)}
  />
{/if}
{#if help}<ShortcutDialog shortcuts={shortcutReference} onclose={() => (help = false)} />{/if}

<style>
  .workspace {
    display: flex;
    height: 100vh;
    height: 100dvh;
    overflow: hidden;
  }
  .workspace > :global(.sidebar) {
    overflow-y: auto;
    scrollbar-width: thin;
    scrollbar-color: #303b31 transparent;
  }
  @media (max-width: 760px) {
    .workspace {
      display: block;
      height: auto;
      overflow: visible;
    }
    .workspace > :global(.sidebar) {
      overflow-y: visible;
    }
  }
</style>
