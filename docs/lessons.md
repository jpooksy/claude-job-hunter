# Lessons learned

This template came out of a real job search run with Claude Code: a
Solutions Engineer looking for remote roles at data and devtools companies.
These are the mistakes and fixes from that search. Each one is built into the
workflow.

| What went wrong | What the template does |
|---|---|
| A quick "last 4 days" email search missed a rejection sent as a **reply in an old thread**, plus an application that was never tracked | The inbox-auditor goes **company by company** back to the search start date, checks sent mail, and runs a separate pass for untracked applications |
| Claude "fixed" rows the user had set to Closed on purpose, reverting real decisions | `tracker.py` diffs against what it last wrote; hand-edited fields are locked in `tracker/locks.json` and never overwritten without asking. "Passed" was added for "I chose not to apply" |
| Dealbreakers started as small score penalties, so an onsite-only role still scored 8/10 | Dealbreakers are **hard filters**: `profile.yaml` rules in `filter.py`, judgment rules quoted by the jd-reader |
| Industry scoring followed buzzwords: an industrial "data" company scored high although its buyers were plant managers | The jd-reader judges industry by **what the company sells and who buys it** |
| Stale postings (especially on third-party job boards) | Every role needs a URL fetched in the current run; `ats.py verify` re-checks each one against the company's own board |
| Agents browsing careers pages one by one were slow, costly and sometimes died mid-run | Scripts pull whole job boards through public APIs in seconds; agents only read the postings that survive the filter, and write results to files as they go |
| The same postings got re-read every run | `data/seen.jsonl` records every judged posting |
| Dates stored as text ("~Sep 20") broke sorting | Dates are always real `YYYY-MM-DD` values (real dates in Google Sheets) |
| Ambiguous labels ("Application" as a source) | Fixed vocabularies for Category, Status and Source, with dropdowns in the sheet |
| Uploading an `.xlsx` through Drive corrupted it; OAuth "publishing" required a homepage and privacy policy | A native Google Sheet created through the Drive connector, written by a service account. No OAuth app to publish |
| A service account can't create spreadsheets (no Drive storage) | The sheet is created in the user's own Drive and shared with the service account |
| Several roles crammed into one cell made scoring and filtering messy | **One row per role** |
| Generic application answers that reused earlier text | `/apply` writes for this company and role only, grounded in the resume, in the user's voice |
| A slug guess matched a different company with the same name | `ats.py detect` prefers board links found on the company's own careers page, and flags guesses for review |
| Inflated self-assessments produce flattering but useless matches | Setup asks for roles you're qualified for **today** and reality-checks targets against the resume |
