// Alpine page() for the Connect stage.

const HINTS = {
  youtube_community: 'YouTube Community posts. No credentials needed.',
  reddit: 'Reddit API credentials. REDDIT_CLIENT_ID/REDDIT_CLIENT_SECRET env vars override these.',
  rss: 'RSS / Atom feed reader. No credentials needed.',
  twitter: 'Twitter connector options. Token comes from env vars.',
  facebook: 'Facebook Graph API token. FB_GRAPH_TOKEN env var overrides this.',
};

// Secrets are rendered as ***. Empty values stay editable as plain text.
const SECRETS = {
  reddit:   ['client_secret'],
  facebook: ['graph_token'],
};

function page() {
  return {
    sources: [],
    active: '',
    draft: {},
    busy: false,
    okMsg: '',
    errorMsg: '',
    hint(s) { return HINTS[s] || ''; },
    isSecret(source, key) {
      return (SECRETS[source] || []).includes(key);
    },
    _clone(o) { return JSON.parse(JSON.stringify(o)); },
    async init() {
      await this.reload();
    },
    async reload() {
      try {
        const data = await fetch('/api/config/sources').then(r => r.json());
        this.sources = data.available || [];
        this.draft = this._clone(data.sources || {});
        if (!this.active && this.sources.length) this.active = this.sources[0];
        this.okMsg = '';
        this.errorMsg = '';
      } catch (err) {
        this.errorMsg = 'Failed to load sources: ' + err.message;
      }
    },
    async save() {
      this.busy = true;
      this.okMsg = '';
      this.errorMsg = '';
      try {
        const r = await fetch('/api/config/sources', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ sources: this._clone(this.draft) }),
        });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(data.error || ('HTTP ' + r.status));
        await this.reload();  // pick up masked-*** -> original substitutions
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