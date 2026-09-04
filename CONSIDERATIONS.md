# Considerations

*Nothing open — both parked scope calls were decided 2026-09-04:*
- `templates/account.html` **ported** to the shared Alpine `page()` architecture
  (`static/js/account.js`, styles moved into `static/base.css`).
- `python main.py export` **got a dashboard entry point**: Browse's
  "Export these results" button, reusing the search filters rather than a
  second set of date pickers.
