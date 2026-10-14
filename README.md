# claude-job-hunter

A [Claude Code](https://claude.com/claude-code) workspace for finding jobs at
software and tech companies **you're actually a fit for**, and keeping your
applications organized while you go after them.

You give it your resume and the companies that have already shown interest in
you. It finds similar companies, pulls their live job boards, reads every
promising posting against your resume, scores each role honestly, and keeps a
tracker (Google Sheet or CSV) up to date: statuses from your inbox, closed
postings removed, follow-ups flagged. When you find a role you want, it helps
you write the application.

It's built from a real job search. The mistakes from that search are now
guardrails in the workflow ([docs/lessons.md](docs/lessons.md)).

---

## What it does

| Command | What happens |
|---------|-------------|
| **`/setup`** | A guided first run: add your resume(s) and LinkedIn PDF, answer a few short rounds of questions, connect email and a Google Sheet (both recommended, both optional), and fill your tracker from your own list and inbox. It doesn't search for new jobs; that's the next command |
| **`/find-jobs`** | Researches companies like the ones that interviewed you, fetches every job board, filters out what doesn't fit, reads the rest against your resume, scores them, and adds them to your tracker after you confirm |
| **`/refresh-tracker`** | Re-checks every posting (live / changed / gone), audits your inbox for rejections, interviews and ghosting, picks up new roles at known companies, and lists follow-ups due |
| **`/apply`** | Writes application answers, cover letters, resume tweaks and outreach or follow-up drafts, specific to the company and grounded in your real resume. Marks the role Applied when you submit |

### How a search works

```
your signals ─► company-researcher agents ─► companies.csv
                                                  │
                    ats.py fetch (public job-board APIs: Greenhouse, Ashby, Lever, Workable)
                                                  │
                    filter.py: titles, level, location, pay floor, already seen   (free, instant)
                                                  │
                    jd-reader agents: required quals vs. your resume, dealbreakers, industry by buyer
                                                  │
                    score.py: your rubric, every point explained
                                                  │
                    tracker.py plan ─► you confirm ─► apply ─► Google Sheet / CSV
```

Scripts do the mechanical work (fast, free, the same answer every time).
Claude only does what needs judgment: which companies are similar, and whether
you meet a posting's requirements.

---

## Quickstart

**You need:** [Claude Code](https://docs.claude.com/en/docs/claude-code), a
claude.ai account, and [uv](https://docs.astral.sh/uv/) (`brew install uv`).

1. **Make your own copy.** Click **Use this template** → *Create a new repository*,
   and **make it private**. Your profile and tracker are gitignored, but private
   is the safe default for a job search. Or just clone it:
   ```bash
   git clone https://github.com/jpooksy/claude-job-hunter.git
   cd claude-job-hunter
   ```
2. **Start Claude Code** in the folder. It greets you and points you to setup:
   ```bash
   claude          # then type /setup
   ```
   Or start setup straight away with `claude "/setup"`.
3. Have these ready:
   - your **resume(s)** (PDF, DOCX, or text), all versions if you have more than one. **Required.**
   - your **LinkedIn profile PDF** (your profile → Resources → Save to PDF). Recommended.
   - the roles that got you **interviews** recently: the company and title are enough.
   - optional: whatever you already use to track your search (a sheet, a list), and links to your work (GitHub, portfolio, blog, videos).

Setup takes about 20 minutes, most of it short questions. Then run
`/find-jobs` (about 15–25 minutes) to get your first recommendations.

### Be honest in setup

When setup asks which positions and companies interest you, list the ones
you're **qualified for today**, not where you hope to be in three years.
Claude takes your answers at face value. Overstate your experience and it will
happily find roles you won't get, and the good matches get buried. Setup
checks your targets against your resume and tells you which ones are a
stretch.

---

## Recommended: email + Google Sheets

Both are optional. Setup explains the trade-offs and walks you through each one.

**Email (Gmail connector).** Lets Claude find every application's real status:
confirmations, interviews, rejections (including ones buried as replies in
old threads), ghosting, and companies that said "stay in touch" (your
warmest leads). Read-only, job-search messages only, never sends. Skip it if
you have security concerns, and tell Claude about changes yourself.
→ [docs/email-setup.md](docs/email-setup.md)

**Google Sheets.** The tracker updates automatically in a real spreadsheet
you can open anywhere, with filters, dropdowns and color-coded scores. Connect
the claude.ai **Google Sheets** and **Google Drive** connectors, and Claude
creates and fills the sheet. There's no Google Cloud setup. Every write is read
back and checked. The CSV alternative works, but you have to re-open the file
after every update. (Already have a Google service account? That works too.)
→ [docs/sheets-setup.md](docs/sheets-setup.md)

---

## The tracker

One row per role:

| Column | |
|--------|-|
| Category | Interviewing · Applied (waiting) · Door open (reapply) · To apply · Watchlist · **Passed** (you chose not to apply) · **Closed** (they closed it) |
| Fit | 1–10, from your rubric. Type your own number and it sticks |
| Company · Role · URL | The posting, verified live |
| Status | Not Applied · Applied · In Conversation · Interviewing · Offer · Rejected · Ghosted · Hiring Freeze · Closed |
| Applied · Last updated | Real dates |
| Comp · Location | From the posting |
| **Added by** | Who put the row there: **You** (your list, or something you told Claude) · **Email** (found in your inbox) · **Claude** (a role Claude recommends) |
| Notes · Fit reasoning | Dated notes; how each point of the score was earned |

**Your edits win.** Edit the sheet whenever you like. Claude diffs against what
it last wrote, treats differences as intentional, and never overwrites them
without asking.

---

## Make it yours

Everything personal lives in `profile/` (created by setup, gitignored):

| File | What it controls |
|------|------------------|
| `resume.md` | The factual record every posting is checked against |
| `background.md` | Positions you're qualified for, industries, strengths, gaps |
| `signals.md` | Companies that interviewed you or kept the door open |
| `targets.md` | Companies and positions you're interested in |
| `dealbreakers.md` | Hard no's. These remove roles; they don't just lower the score |
| `warm-networks.md` | VC portfolio boards, alumni groups, referral paths |
| `profile.yaml` | Titles, levels, location rules, pay floor, email/tracker settings |
| `fit-score.yaml` | The scoring rubric: change the numbers, change the ranking |

You rarely need to edit these by hand. Tell Claude ("no more crypto
companies", "score dev tools higher", "I interviewed at Acme last week") and
it updates the right file.

---

## Try it without your own data

`examples/fictional-persona/` is a complete made-up profile (a mid-level
Solutions Engineer at developer-API companies). Run the mechanical half of the
pipeline against real job boards:

```bash
export JH_WORKSPACE=examples/fictional-persona
uv run scripts/ats.py detect     # find each company's job board
uv run scripts/ats.py fetch      # pull every posting
uv run scripts/filter.py         # cheap filters -> batches for the jd-reader
```

---

## Repo layout

```
.claude/
  skills/   setup/  find-jobs/  refresh-tracker/  apply/
  agents/   company-researcher.md  jd-reader.md  inbox-auditor.md
  settings.json                  # pre-approves the read-only script commands
scripts/    ats.py  filter.py  score.py  tracker.py  common.py   (run with uv run)
templates/  profile/*  companies.csv                      # copied by /setup
docs/       sheets-setup.md  email-setup.md  lessons.md
examples/   fictional-persona/
CLAUDE.md   rules the agent follows
# created by setup, gitignored:
profile/  data/  tracker/  runs/  drafts/
```

## Limits

- Built for **software and tech companies**. Job boards are fetched from
  Greenhouse, Ashby, Lever and Workable (most startups and scale-ups). For
  other companies, Claude checks the careers page by hand, up to ~10 per run.
- Job boards change. If a company's board moves, `ats.py detect --company X`
  finds it again.
- It's a co-pilot, not an auto-applier. It never submits applications or
  sends email.

## License

MIT
