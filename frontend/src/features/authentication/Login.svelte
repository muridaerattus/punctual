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
  <h1>Sign in</h1>
  {#if oidc}
    <p>Sign in with your team account to access the shared workspace.</p>
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
    padding: 24px;
  }
  h1 {
    font-size: 44px;
    margin: 60px 0 16px;
  }
  form {
    margin: 30px 0 20px;
    display: grid;
    gap: 20px;
  }
  small {
    font-size: 11px;
  }
  @media (max-width: 760px) {
    .login {
      margin-top: 4vh;
    }
  }
</style>
