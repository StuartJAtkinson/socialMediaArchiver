// Alpine page() for the account view.
// Loads the post list from /api/posts and pages it in; the summary stats above
// it are server-rendered, since they never change while the page is open.

function page() {
  return {
    posts: [],
    offset: 0,
    limit: 20,
    hasMore: false,
    loading: true,
    errorMsg: '',
    platform: '',
    account: '',
    async init() {
      this.platform = document.body.dataset.platform;
      this.account = document.body.dataset.account;
      await this._fetch(0);
    },
    async more() {
      if (this.loading || !this.hasMore) return;
      await this._fetch(this.offset + this.limit);
    },
    async _fetch(offset) {
      this.loading = true;
      this.errorMsg = '';
      try {
        const url = `/api/posts/${encodeURIComponent(this.platform)}/${this.account}`
          + `?limit=${this.limit}&offset=${offset}`;
        const data = await fetch(url).then(r => r.json());
        if (data.error) { this.errorMsg = data.error; return; }
        this.posts = offset === 0 ? (data.posts || []) : this.posts.concat(data.posts || []);
        this.offset = data.offset ?? offset;
        this.hasMore = !!data.has_more;
      } catch (err) {
        this.errorMsg = String(err);
      } finally {
        this.loading = false;
      }
    },
    // Archived text can carry markup and HTML entities from the source (Reddit
    // sends &#32;). Parsing to a detached document strips tags and decodes
    // entities in one step, and never executes anything.
    postText(post) {
      const html = (post.text || '').replace(/<br\s*\/?>/gi, '\n');
      const doc = new DOMParser().parseFromString(html, 'text/html');
      return (doc.body.textContent || '').trim();
    },
    fmtDate(value) {
      return value ? value.substring(0, 19).replace('T', ' ') : 'Unknown date';
    },
  };
}

window.page = page;
