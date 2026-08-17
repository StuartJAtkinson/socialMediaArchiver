// Alpine page() for the Schedule stage.

function page() {
  return {
    yamlValue: 0,
    activeValue: 0,
    draft: 0,
    saving: false,
    okMsg: '',
    errorMsg: '',
    get restartNeeded() {
      return this.yamlValue !== this.activeValue;
    },
    async init() {
      await this.reload();
    },
    async reload() {
      try {
        const data = await fetch('/api/config/schedule').then(r => r.json());
        this.yamlValue = data.yaml_value || 0;
        this.activeValue = data.active_value || 0;
        this.draft = this.yamlValue;
        this.okMsg = '';
        this.errorMsg = '';
      } catch (err) {
        this.errorMsg = 'Failed to load schedule: ' + err.message;
      }
    },
    async save() {
      this.saving = true;
      this.okMsg = '';
      this.errorMsg = '';
      try {
        const r = await fetch('/api/config/schedule', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ interval_minutes: this.draft }),
        });
        if (!r.ok) {
          const err = await r.json().catch(() => ({ error: r.statusText }));
          throw new Error(err.error || 'HTTP ' + r.status);
        }
        const data = await r.json();
        this.yamlValue = data.yaml_value;
        this.activeValue = data.active_value;
        this.okMsg = 'Saved to config.yaml.';
      } catch (err) {
        this.errorMsg = 'Save failed: ' + err.message;
      } finally {
        this.saving = false;
      }
    },
  };
}

window.page = page;