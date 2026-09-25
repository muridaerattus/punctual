<script lang="ts">
  import Brand from '../../shared/ui/Brand.svelte';
  let {
    apiKey = $bindable(''),
    busy,
    error,
    onlogin,
  }: {
    apiKey?: string;
    busy: boolean;
    error: string;
    onlogin: () => void;
  } = $props();
</script>

<main class="login">
  <Brand />
  <p class="eyebrow">LESS PROCESS. MORE PROGRESS.</p>
  <h1>Small board.<br />Clear direction.</h1>
  <p class="muted">A shared workspace for humans and agents.</p>
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
  {#if error}<p role="alert" class="error">{error}</p>{/if}
  <small class="muted">Your key is kept for this browser tab’s session.</small>
</main>

<style>
  .login {
    max-width: 420px;
    margin: 10vh auto;
    padding: 24px;
  }
  .eyebrow {
    margin-top: 60px;
  }
  h1 {
    font-size: 44px;
    margin: 16px 0;
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
