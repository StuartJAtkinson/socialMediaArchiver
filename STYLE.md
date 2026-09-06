# Style questions

Visual calls that need a human eye. Each bullet is one numbered question in
`STYLE.html`; answer there and atelier records the decision into `ISSUES.md`.

- Connect's source selector and Storage's backend selector are both built out of `.status` pills, while `static/base.css:331-353` carries an unused `.source-tabs` underline-tab component written for exactly this job. Which presentation should both selectors use — the pills that ship today, or the tab strip the stylesheet already describes?
- Empty states are presented two different ways: Browse and the account page draw a bordered `.panel` with a heading and a sentence of guidance, while Configure, Run and Schedule print a single line of faint text. Which should be the convention for an empty list?
