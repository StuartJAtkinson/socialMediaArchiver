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
    searchError: '',
    searchLimit: 20,
    searchOffset: 0,
    hasMore: false,
    filters: { platform: '', account: '', since: '', until: '' },
    exporting: false,
    exportMsg: '',
    _timer: null,
    // Some sources already store the leading @; don't render "@@name".
    handle(name) {
      return String(name || '').startsWith('@') ? name : '@' + name;
    },
    get platforms() {
      return [...new Set(this.accounts.map(a => a.platform))].sort();
    },
    async init() {
      await this._sync();
      this._timer = setInterval(() => this._sync(), 5000);
      // Infinite scroll: the sentinel sits below the results list and is
      // display:none until there are results, so it can only intersect once
      // the user has scrolled to the bottom of a non-empty list.
      this.$nextTick(() => {
        new IntersectionObserver(
          entries => { if (entries[0].isIntersecting) this.moreResults(); },
          { root: this.$refs.scroller, rootMargin: '200px' }
        ).observe(this.$refs.sentinel);
      });
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
      if (!q) { this.results = []; this.searched = false; this.hasMore = false; return; }
      await this._fetchResults(0);
    },
    // Called by the scroll sentinel; a no-op unless there is another page.
    async moreResults() {
      if (this.searching || !this.hasMore) return;
      await this._fetchResults(this.searchOffset + this.searchLimit);
    },
    async _fetchResults(offset) {
      this.searching = true;
      try {
        const params = new URLSearchParams({
          q: this.query.trim(),
          limit: this.searchLimit,
          offset,
          ...this._activeFilters(),
        });
        const data = await fetch('/api/search?' + params).then(r => r.json());
        const page = data.results || [];
        this.results = offset === 0 ? page : this.results.concat(page);
        this.searchTotal = data.total || 0;
        this.searchOffset = data.offset ?? offset;
        this.hasMore = !!data.has_more;
        // Without this, "no index yet" reads as an honest "0 matches".
        this.searchError = data.error || '';
        this.searched = true;
      } catch (err) {
        console.error('search failed:', err);
      } finally {
        this.searching = false;
      }
    },
    _activeFilters() {
      return Object.fromEntries(
        Object.entries(this.filters).filter(([, v]) => v.trim())
      );
    },
    async exportResults() {
      this.exporting = true;
      this.exportMsg = '';
      try {
        const res = await fetch('/api/export', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ q: this.query.trim(), ...this._activeFilters() }),
        });
        const data = await res.json();
        if (data.error) {
          this.exportMsg = 'Export failed: ' + data.error;
        } else {
          this.exportMsg = 'Exported to ' + data.path;
          window.open(data.url, '_blank');
        }
      } catch (err) {
        this.exportMsg = 'Export failed: ' + err;
      } finally {
        this.exporting = false;
      }
    },
  };
}

window.page = page;