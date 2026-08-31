// Alpine page() for the Configure stage.

function page() {
  return {
    rows: [],
    sources: [],
    draft: { source: '', target: '' },
    busy: false,
    loading: true,
    okMsg: '',
    errorMsg: '',
    get canAdd() {
      return this.draft.source.trim() !== '' && this.draft.target.trim() !== '';
    },
    async init() {
      await Promise.all([this.reload(), this.loadSources()]);
    },
    async loadSources() {
      try {
        const data = await fetch('/api/config/sources').then(r => r.json());
        this.sources = data.available || [];
      } catch (err) {
        this.errorMsg = 'Failed to load sources: ' + err.message;
      }
    },
    async reload() {
      try {
        const data = await fetch('/api/config/targets').then(r => r.json());
        this.rows = data.targets || [];
        this.loading = false;
        this.okMsg = '';
        this.errorMsg = '';
      } catch (err) {
        this.errorMsg = 'Failed to load targets: ' + err.message;
        this.loading = false;
      }
    },
    async add() {
      this.busy = true;
      this.okMsg = '';
      this.errorMsg = '';
      try {
        const r = await fetch('/api/config/targets/add', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            source: this.draft.source.trim(),
            target: this.draft.target.trim(),
          }),
        });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(data.error || ('HTTP ' + r.status));
        this.rows = data.targets || [];
        this.draft = { source: '', target: '' };
        this.okMsg = 'Added.';
      } catch (err) {
        this.errorMsg = 'Add failed: ' + err.message;
      } finally {
        this.busy = false;
      }
    },
    async remove(row) {
      this.busy = true;
      this.okMsg = '';
      this.errorMsg = '';
      try {
        const r = await fetch('/api/config/targets/remove', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ source: row.source, target: row.target }),
        });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(data.error || ('HTTP ' + r.status));
        this.rows = data.targets || [];
        this.okMsg = 'Removed.';
      } catch (err) {
        this.errorMsg = 'Remove failed: ' + err.message;
      } finally {
        this.busy = false;
      }
    },
  };
}

window.page = page;