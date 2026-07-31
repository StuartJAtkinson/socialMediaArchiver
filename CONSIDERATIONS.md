# Considerations

- Secondary nav link styling disagrees between templates: `templates/account.html:319-323` gives "← Back to Dashboard" a neutral/transparent style, while `templates/index.html:311-321` gives the equivalent secondary link ("View Posts") the same indigo/primary treatment as the actual primary CTA ("Start Archiving"). Needs a human call on which secondary-link style is correct — right now the two pages disagree on what "secondary" looks like.
- Two different "key stats" layouts for the same content (post/image/video counts): `templates/account.html:353-359` `.stats-bar` is a borderless flex row of label/value pairs; `templates/index.html:261-268` `.stats-grid` is a bordered grid with hairline dividers. Pick one presentation.
- Decorative emoji used in headings on `templates/index.html` (📚/🚀/📁, lines 427/451/458) but not on `templates/account.html`. Decide whether emoji headings are part of the visual language or should be dropped.
