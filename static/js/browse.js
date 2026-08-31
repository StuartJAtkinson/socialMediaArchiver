// Alpine page() for the Browse stage.
// Polls /api/stats every 5 s; renders the same summary tiles + accounts grid
// that the legacy single-page dashboard used to show inline.

function page() {
  return {
    stats: {},
    accounts: [],
    loading: true,
    query: '',
    results: [],
    searchTotal: 0,
    searched: false,
    searching: false,
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
    async search() {
      const q = this.query.trim();
      if (!q) { this.results = []; this.searched = false; return; }
      this.searching = true;
      try {
        const data = await fetch('/api/search?q=' + encodeURIComponent(q)).then(r => r.json());
        this.results = data.results || [];
        this.searchTotal = data.total || 0;
        this.searched = true;
      } catch (err) {
        console.error('search failed:', err);
      } finally {
        this.searching = false;
      }
    },
  };
}

window.page = page;