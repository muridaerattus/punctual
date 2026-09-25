export class LeaseState {
  owner = $state(localStorage.getItem('punctual.owner') || 'human');
  tokens = $state<Record<number, string>>(this.readTokens());

  private readTokens(): Record<number, string> {
    try {
      const value = JSON.parse(sessionStorage.getItem('punctual.leases') || '{}');
      return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
    } catch {
      return {};
    }
  }

  saveToken(id: number, token?: string) {
    if (token) this.tokens[id] = token;
    else delete this.tokens[id];
    sessionStorage.setItem('punctual.leases', JSON.stringify(this.tokens));
    localStorage.setItem('punctual.owner', this.owner);
  }

  clear() {
    this.tokens = {};
    sessionStorage.removeItem('punctual.leases');
  }
}
