// Alpine page() for the Browse stage.
// Polls /api/stats every 5 s; renders the same summary tiles + accounts grid
// that the legacy single-page dashboard used to show inline.

function page() {
  return {
    stats: {},
    accounts: [],
    loading: true,
    _timer: null,
    async init() {
      await this._sync();
      this._timer = setInterval(() => this._sync(), 5000);
    },
    async _sync() {
      try {
        const data = await fetch('/api/stats').then(r => r.json());
        this.stats = data;
        this.accounts = data.accounts || [];
        this.loading = false;
      } catch (err) {
        console.error('browse sync failed:', err);
        this.loading = false;
      }
    },
  };
}

window.page = page;