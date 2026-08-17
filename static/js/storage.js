// Alpine page() for the Storage stage.

function page() {
  return {
    backends: ['filesystem', 's3', 'gcs', 'azure'],
    draft: {
      backend: 'filesystem',
      output_dir: './output',
      images_dir: './output/images',
      s3:  { bucket: '', prefix: '', region: '', endpoint_url: '' },
      gcs: { bucket: '', prefix: '', project: '' },
      azure: { container: '', prefix: '', connection_string: '' },
    },
    busy: false,
    okMsg: '',
    errorMsg: '',
    async init() {
      await this.reload();
    },
    _clone(s) { return JSON.parse(JSON.stringify(s)); },
    async reload() {
      try {
        const data = await fetch('/api/config/storage').then(r => r.json());
        const block = data.storage || {};
        this.draft = this._clone({
          backend: block.backend || 'filesystem',
          output_dir: block.output_dir || './output',
          images_dir: block.images_dir || './output/images',
          s3:   block.s3   || { bucket: '', prefix: '', region: '', endpoint_url: '' },
          gcs:  block.gcs  || { bucket: '', prefix: '', project: '' },
          azure: block.azure || { container: '', prefix: '', connection_string: '' },
        });
        this.okMsg = '';
        this.errorMsg = '';
      } catch (err) {
        this.errorMsg = 'Failed to load storage: ' + err.message;
      }
    },
    async save() {
      this.busy = true;
      this.okMsg = '';
      this.errorMsg = '';
      try {
        const r = await fetch('/api/config/storage', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ storage: this._clone(this.draft) }),
        });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(data.error || ('HTTP ' + r.status));
        // Reload to pick up any masked-*** -> original substitutions server did.
        await this.reload();
        this.okMsg = 'Saved to config.yaml.';
      } catch (err) {
        this.errorMsg = 'Save failed: ' + err.message;
      } finally {
        this.busy = false;
      }
    },
  };
}

window.page = page;