<script lang="ts">
  import Brand from '../../shared/ui/Brand.svelte';
  let {
    apiKey = $bindable(''),
    busy,
    error,
    onlogin,
    oidc = false,
  }: {
    apiKey?: string;
    busy: boolean;
    error: string;
    onlogin: () => void;
    oidc?: boolean;
  } = $props();
</script>

<main class="login">
  <Brand />
  <header>
    <h1>Sign in</h1>
    {#if oidc}<p>Sign in with your team account to access the shared workspace.</p>{/if}
  </header>
  {#if oidc}
    <button
      class="primary"
      disabled={busy}
      onclick={() => window.location.assign('/api/auth/login')}
      >Sign in with SSO <span>↗</span></button
    >
  {:else}
    <form
      onsubmit={(event) => {
        event.preventDefault();
        onlogin();
      }}
    >
      <label
        >Workspace API key
        <input
          type="password"
          bind:value={apiKey}
          required
          autocomplete="current-password"
          placeholder="Enter your shared API key"
        />
      </label>
      <button class="primary" disabled={busy}>Enter workspace <span>↗</span></button>
    </form>
  {/if}
  {#if error}<p role="alert" class="error">{error}</p>{/if}
  {#if !oidc}<small class="muted">Your key is kept for this browser tab’s session.</small>{/if}
</main>

<style>
  .login {
    max-width: 420px;
    margin: 10vh auto;
    padding: var(--space-6);
    display: grid;
    gap: var(--space-6);
  }
  header {
    display: grid;
    gap: var(--space-3);
    margin-top: var(--space-6);
  }
  h1 {
    font-size: var(--text-title);
    line-height: 1.2;
  }
  header p {
    color: var(--text-secondary);
    line-height: 1.6;
  }
  form {
    display: grid;
    gap: var(--space-5);
  }
  .primary {
    width: 100%;
    min-height: 44px;
  }
  .error {
    margin: 0;
  }
  small {
    font-size: var(--text-xs);
    line-height: 1.6;
  }
  @media (max-width: 760px) {
    .login {
      margin-top: 4vh;
    }
  }
</style>
