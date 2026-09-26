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
      error = 'Your session expired. Please sign in again.';
    },
  );
  const api = new TaskApi(client);
  const boardApi = new BoardApi(client);
  let initialTasks = $state<Task[]>([]);
  let busy = $state(true);
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

  async function logout() {
    try {
      await session.logout();
      leases.clear();
      initialTasks = [];
      error = '';
    } catch (cause) {
      window.alert(cause instanceof Error ? cause.message : 'Unable to sign out');
    }
  }

  onMount(() => {
    void (async () => {
      try {
        const authenticated = await session.initialize();
        const url = new URL(window.location.href);
        if (url.searchParams.has('auth_error')) {
          error = 'Sign-in failed. Check your team membership and try again.';
          window.history.replaceState(null, '', '/');
        }
        busy = false;
        if (authenticated) await login();
      } catch {
        busy = false;
        error = 'Unable to reach the server. Reload to try again.';
      }
    })();
  });
</script>

{#if session.authenticated}
  <BoardPage {api} {boardApi} {leases} {initialTasks} onlogout={logout} />
{:else}
  <Login bind:apiKey={session.key} oidc={session.oidc} {busy} {error} onlogin={login} />
{/if}
