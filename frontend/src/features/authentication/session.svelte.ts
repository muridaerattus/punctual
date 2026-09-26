export class Session {
  key = $state(sessionStorage.getItem('punctual.key') || '');
  authenticated = $state(false);
  oidc = $state(false);

  async initialize() {
    const response = await fetch('/api/auth/session', { credentials: 'same-origin' });
    if (!response.ok) throw new Error('Unable to check sign-in status');
    const status = await response.json();
    this.oidc = status.mode === 'oidc';
    if (this.oidc) this.clear();
    return status.authenticated || (!this.oidc && !!this.key);
  }

  async logout() {
    if (this.oidc) {
      const response = await fetch('/api/auth/logout', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'X-Punctual-CSRF': '1' },
      });
      if (!response.ok) throw new Error('Sign out failed. Please try again.');
      const result = await response.json();
      this.clear();
      window.location.assign(result.redirect);
    } else this.clear();
  }

  remember() {
    this.authenticated = true;
    if (!this.oidc) sessionStorage.setItem('punctual.key', this.key);
  }

  clear() {
    this.authenticated = false;
    this.key = '';
    sessionStorage.removeItem('punctual.key');
  }
}
