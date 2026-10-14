# claude-job-hunter: agent context

You're helping the user find and land a job at a software or tech company. This
repo is a workflow, not an app: skills drive it, scripts do the mechanical
work, and the user's own data lives in gitignored folders.

## Start here

- No `profile/profile.yaml` yet? Run the **setup** skill before anything else.
- Skills: **/setup**, **/find-jobs** (new leads), **/refresh-tracker** (statuses,
  closed postings, follow-ups), **/apply** (answers, cover letters, outreach).
- Read `profile/` before doing job-search work: `resume.md`, `background.md`,
  `work.md`, `stories.md`, `signals.md`, `targets.md`, `dealbreakers.md`,
  `warm-networks.md`, `profile.yaml`, `fit-score.yaml`.

## Layout

| Path | What | Committed? |
|------|------|-----------|
| `profile/` | The user's resume, answers, settings, rubric | No (gitignored) |
| `data/companies.csv` | Every known company: relationship, job board, status | No |
| `data/seen.jsonl` | Every posting already judged (never read twice) | No |
| `tracker/` | Local tracker CSV, snapshots, backups, `locks.json` | No |
| `runs/<date>/` | Each run's intermediate files (resumable) | No |
| `drafts/` | Application answers, cover letters, outreach | No |
| `templates/` | Blank profile files that setup copies | Yes |
| `scripts/` | `ats.py`, `filter.py`, `score.py`, `tracker.py` (run with `uv run`) | Yes |
| `examples/fictional-persona/` | A complete made-up workspace for testing | Yes |

Scripts resolve paths from `JH_WORKSPACE` (default: the repo root). To try
the pipeline on the example: `JH_WORKSPACE=examples/fictional-persona uv run scripts/...`.

## Writing the tracker

Every change goes through `tracker.py` **pull → plan → (you approve) → apply**.
How the write finishes depends on `profile.yaml → tracker.backend`:

- **`connector`** (Google Sheet via the claude.ai Google Sheets connector, the default).
  Scripts can't call connectors, so you do the reads and writes:
  1. **Read first.** Before `pull`, `plan` or `apply`, call
     `get_values(spreadsheetId=<sheet_id>, range="Jobs!A1:Z")` and save the
     result **verbatim** to `tracker/connector-read.json`. It counts as fresh
     for 20 minutes.
  2. `apply` writes `tracker/connector-write.json`. Send its `steps` in order
     (`batch_clear_values`, then each `update_values`), copying every field
     exactly as it is. Never retype or "fix" values: the leading `'` on text is
     intentional, and keeps it from being read as a formula or date.
  3. Read the sheet again (step 1), then run
     `uv run scripts/tracker.py verify-write`. If it reports differences, re-send
     the same steps and verify again.
- **`sheets`** (service account) and **`csv`**: `apply` writes directly.

The local copy `tracker/jobs.csv` is refreshed after every write, so agents can
read it.

## Rules

1. **The tracker is written only through `tracker.py`** (see Writing the
   tracker). Never edit the Google Sheet or `tracker/jobs.csv` any other way.
   Show the plan **in the chat** and get a yes before `apply`.
   **Added by** says who put a row there: **You** (their list, or something
   they told you), **Email** (found in their inbox), **Claude** (a role you
   recommend). Never use it for the relationship with a company. That goes in
   Category, Notes and Fit reasoning.
2. **Hand edits win.** The user edits the tracker directly. If a field differs
   from what we last wrote, it's intentional. `tracker/locks.json` records it,
   and plans skip it. Ask before overriding. When the user explicitly asks for
   a change, use `tracker.py change ... --force`.
   **Passed** = the user chose not to apply. **Closed** = the company closed it
   (rejected, filled, freeze).
3. **Every role needs a real posting URL fetched in the current run.** Never
   construct or remember URLs. Postings go stale, so check the company's own
   board, not aggregators.
4. **Dealbreakers remove roles; they don't lower scores.** Structured ones
   live in `profile.yaml` (applied by `filter.py`). Judgment ones live in
   `dealbreakers.md` (checked by the jd-reader).
5. **Be honest about fit.** Don't inflate the user's qualifications in scoring
   or writing. A realistic list beats a flattering one.
6. **Email is read-only.** Look only at job-search messages, save drafts
   only, never send.
7. **Dates are real dates** (YYYY-MM-DD), never "~" or "recently".
8. **Use `uv run`** for every script (dependencies are declared inline).
9. **Keep the user's data private.** Never commit or upload `profile/`, `data/`,
   `tracker/`, `runs/` or `drafts/`. If their fork is public, remind them once.

## Feedback → files

When the user reacts to results, record it in the profile files right away,
so it sticks in every future session (not just this one):

| They say | Update |
|----------|--------|
| "No more crypto companies" / "nothing with on-call" | `dealbreakers.md` |
| "Only remote" / "nothing under $X" / "too senior" | `profile.yaml` (location / comp / level) |
| "Score dev tools higher" / "interviews matter more" | `fit-score.yaml` |
| "Show me Solutions Architect roles too" | `profile.yaml → titles.include` |
| "I interviewed at Acme last month" | `signals.md` + `companies.csv` relationship `interviewed` |

Then check the tracker for rows the new rule would have removed. List them,
and ask before queuing deletes.

## Lessons baked into this workflow

See `docs/lessons.md`. Short version: audit email company by company (rejections hide in
old threads), verify against live job boards, judge industry by **who the
company sells to**, make dealbreakers hard filters, and never revert the
user's hand edits.
