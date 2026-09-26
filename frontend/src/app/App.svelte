<script lang="ts">
  import { onMount } from 'svelte';
  import Login from '../features/authentication/Login.svelte';
  import { Session } from '../features/authentication/session.svelte';
  import { TaskApi } from '../entities/task/api';
  import { BoardApi } from '../entities/board/api';
  import { LeaseState } from '../entities/task/lease-state.svelte';
  import type { Task } from '../entities/task/types';
  import BoardPage from '../pages/board/BoardPage.svelte';
  import { HttpClient } from '../shared/api/client';

  const session = new Session();
  const leases = new LeaseState();
  const client = new HttpClient(
    () => session.key,
    () => {
      session.authenticated = false;
      error = 'Your session expired. Enter a valid API key.';
    },
  );
  const api = new TaskApi(client);
  const boardApi = new BoardApi(client);
  let initialTasks = $state<Task[]>([]);
  let busy = $state(false);
  let error = $state('');

  async function login() {
    if (busy) return;
    busy = true;
    error = '';
    try {
      initialTasks = await api.list();
      session.remember();
    } catch (cause) {
      error = cause instanceof Error ? cause.message : 'Unable to sign in';
    } finally {
      busy = false;
    }
  }

  function logout() {
    session.clear();
    leases.clear();
    initialTasks = [];
    error = '';
  }

  onMount(() => {
    if (session.key) login();
  });
</script>

{#if session.authenticated}
  <BoardPage {api} {boardApi} {leases} {initialTasks} onlogout={logout} />
{:else}
  <Login bind:apiKey={session.key} {busy} {error} onlogin={login} />
{/if}
