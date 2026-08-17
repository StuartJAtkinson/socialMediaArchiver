// Alpine page() for the landing dashboard.
// Polls /api/stats + /api/run/history every 5 s for live tiles + recent-runs panel.

function page() {
  return {
    stats: {},
    recent: [],
    _timer: null,
    async init() {
      await this._sync();
      this._timer = setInterval(() => this._sync(), 5000);
    },
    async _sync() {
      try {
        const [s, h] = await Promise.all([
          fetch('/api/stats').then(r => r.json()),
          fetch('/api/run/history').then(r => r.json()),
        ]);
        this.stats = s;
        this.recent = (h.runs || []).slice(0, 5);
      } catch (err) {
        console.error('dashboard sync failed:', err);
      }
    },
    fmt(iso) {
      if (!iso) return '';
      return iso.replace('T', ' ').slice(0, 19);
    },
  };
}

window.page = page;