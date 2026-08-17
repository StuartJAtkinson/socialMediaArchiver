// Alpine page() for the Run stage.

function page() {
  return {
    phase: 'idle',
    run_id: '',
    started_at: '',
    finished_at: '',
    trigger: '',
    errorMsg: '',
    targets: [],
    history: [],
    busy: false,
    _timer: null,
    async init() {
      await this._sync();
      this._timer = setInterval(() => this._sync(), 2000);
    },
    async _sync() {
      try {
        const data = await fetch('/api/run/status').then(r => r.json());
        this.phase = data.phase || 'idle';
        this.run_id = data.run_id || '';
        this.started_at = data.started_at || '';
        this.finished_at = data.finished_at || '';
        this.trigger = data.trigger || '';
        this.errorMsg = data.error || '';
        this.targets = data.targets || [];
        this.history = data.history || [];
      } catch (err) {
        console.error('run sync failed:', err);
      }
    },
    async start() {
      this.busy = true;
      try {
        const r = await fetch('/api/run/start', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ trigger: 'manual' }),
        });
        await this._sync();
      } catch (err) {
        this.errorMsg = 'Start failed: ' + err.message;
      } finally {
        this.busy = false;
      }
    },
    phaseClass(p) {
      return {
        idle: 'idle', running: 'running', done: 'done', error: 'error',
      }[p] || 'idle';
    },
    statusClass(s) {
      return {
        waiting: 'idle', running: 'running', done: 'done', error: 'error',
      }[s] || 'idle';
    },
    fmt(iso) { if (!iso) return ''; return iso.replace('T', ' ').slice(0, 19); },
  };
}

window.page = page;