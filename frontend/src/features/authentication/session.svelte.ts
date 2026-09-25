export class Session {
  key = $state(sessionStorage.getItem('punctual.key') || '');
  authenticated = $state(false);

  remember() {
    this.authenticated = true;
    sessionStorage.setItem('punctual.key', this.key);
  }

  clear() {
    this.authenticated = false;
    this.key = '';
    sessionStorage.removeItem('punctual.key');
  }
}
