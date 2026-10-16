---
name: setup
description: First-run setup for lookalike-job-hunter. Collects the user's resumes and history, asks short rounds of questions to build their profile, connects email and a Google Sheet tracker (both recommended, both optional), and fills the tracker from their own list and inbox. Use when the user runs /setup, is new to the repo, or wants to redo part of setup ("set up Google Sheets", "connect my email", "redo my profile").
---

# Setup

Setup builds the user's **profile** and **tracker**. It does **not** search for
new jobs. That's `/find-jobs`, which they run right after. Say this in the
welcome, and again at the end.

If `profile/profile.yaml` already exists, ask which part to redo (files,
email and tracker, profile, search history) and jump to that step. To set up
just one piece ("connect Gmail", "switch to Google Sheets"), run that step
alone.

## How to talk to the user (every step)

CLAUDE.md → Talking to the user applies throughout. Setup adds the rules
below.

### The shape of every message

```
Setup · Step 3 of 5 · Your profile · question 2 of 3
✓ Files · ✓ Connect · ▸ Profile · ○ Your search · ○ Next     ← only when a new step starts

From your resume: Denver, remote in your last two roles.        ← what you already know (guesses marked)
<One plain question, second person, about their real situation.>
<What counts as an answer, including the low-effort one.>
<Why it helps, in one sentence.>  <What skipping costs, for optional questions only.>

👉 **Your turn: <exactly what to do, and the accepted answers>**
```

- **Progress:** the header on every message, with a question count inside a
  step ("question 2 of 3") so progress never looks stuck. The named step line
  (✓ done · ▸ current · ○ to come) appears only when a new step starts.
- **The ask** names the accepted answers ("Drag in your resume, or paste the
  text"; "Reply 'yes', or fix by number"). Never end on a status update or a
  vague "Thoughts?". Even before a picker, write the bolded ask first.
- **Fits a terminal:** lines under ~80 characters, no nested bullets, no
  tables wider than the terminal.
- **Anything the user approves is in the chat text of that same message.** Tool
  output is collapsed, so never point to it ("above"). Copy what matters in.

### Asking well

- **One question per message**, and wait for the reply. Never bundle a
  follow-up with the next question.
- **Pickers (AskUserQuestion):** one question per call. Never offer an option
  that means "I'll tell you next"; it swallows the answer. Open questions
  (files, links, lists) go in plain chat.
- **Make broad questions easy.** For open questions like dealbreakers, offer a
  multi-select picker of 3–4 likely answers for **their** field (with "Other"
  for typing), instead of a blank prompt.
- **Examples fit the user**, from their own resume and field, or are neutral.
- **Never ask for the same thing twice.** Start from what earlier answers gave
  you.
- **A question budget:** setup asks only what changes results. Everything else
  is a stated default, shown in the profile review where it can be changed.
- **Skips:** discourage a skip once (the one-line cost, then "Add it after all" /
  "Skip it"); then accept it, and list it at the end with how to add it later.
  **"I don't have one" is an answer**, not a skip: offer a low-effort
  alternative once and move on.
- **Don't assume their situation.** Most people have one resume, no saved
  postings, and at best a rough list of companies.

### When things don't go to plan

- **A reply you still can't use** after the narrower version: give two
  examples from their resume, or switch to a picker. After that, save a
  sensible default marked **(my guess)** and say "you can change this in the
  review".
- **Corrections, at any time,** including to earlier steps ("change my salary to
  130k"): apply them, echo what changed ("Pay floor: $130k (was $150k)"), and
  carry on from where you were.
- **"back", "skip", "pause", "why?"** always work. Mention them once, in the
  welcome. "pause" saves progress (below) and tells them how to resume.

### Working

- **Save as you go.** Write each answer to its profile file right away, and keep
  `runs/setup/state.json` up to date after every step:
  `{"done": ["files", "connect"], "next": "profile", "skipped": ["linkedin"], "updated": "<date>"}`.
  When setup starts and state.json exists, offer to pick up at `next`:
  "Welcome back. ✓ Files ✓ Connect · Next: your profile."
- **Anything that takes more than ~30 seconds:** say what's happening and how
  long it will take before you start, and say when it's done. While waiting:
  "Nothing for you to do right now. I'll message you when it's done (about N
  minutes)."
- **Never go silent between steps.** Never run two pickers back to back, or
  change steps, without a chat message that says what just happened and
  what's next.
- **Don't use email or Drive before their step** unless the user points you to
  a specific email or file.
- **Script problems you work around** go in `runs/setup/issues.md`, not in the
  chat. Mention once at the end that you logged them.

## Step 0: Prepare (no questions)

```bash
uv --version || echo "uv missing"
mkdir -p profile/uploads data tracker runs/setup drafts
cp -n templates/profile/* profile/
cp -n templates/companies.csv data/companies.csv
test -f runs/setup/state.json || echo '{"done": [], "next": "files"}' > runs/setup/state.json
```

If uv is missing, have the user install it (`brew install uv`, or
`curl -LsSf https://astral.sh/uv/install.sh | sh`) and restart the terminal.

If `runs/setup/state.json` exists, don't start over: show what's done and
offer to pick up at `next` ("Welcome back. ✓ Files ✓ Connect · Next: your
profile. 👉 **Your turn: reply 'continue', or name a part to redo.**").

Otherwise, a welcome of **three lines**, then go straight to the first question
in the same message:

> Setup takes about 25 minutes: your files, connect email and a tracker, a few
> profile questions, then a quick check of your search so far. Finding new jobs
> comes right after, with /find-jobs.
> Any time you can say **back**, **skip**, **pause**, or **why?**

## Step 1 of 5: Your files

Three questions, one per message.

**Handling a file.** Copy it into `profile/uploads/` right away
(`cp "<path>" profile/uploads/`) and confirm in one line ("Got it:
resume.pdf"). If the copy fails with "Operation not permitted" (macOS privacy
protection for ~/Downloads, ~/Desktop, ~/Documents), have the user type
`! cp "<path>" profile/uploads/` in the prompt, or drag the file into
`profile/uploads/` in Finder.

1. **Resumes** (required, so no skip)
   > Let's start with your resume. Drag the file in (PDF, Word or text), or
   > paste the text. If you use different versions for different kinds of
   > roles, drop them all in. Everything gets checked against them: each
   > posting's requirements, and anything I write for your applications.

   If they give the same file twice, say so and ask whether there's another
   version.

2. **LinkedIn profile**
   > Can you add your LinkedIn profile as a PDF? On LinkedIn, open your
   > profile → **Resources → Save to PDF**, then drag the file in. (I can't
   > open LinkedIn links myself, since it needs a login. If the download is a
   > hassle, paste the text of your Experience section instead.) It catches
   > things your resume leaves out, like older roles, projects and skills. If
   > you skip it, I'll judge matches on your resume alone.

3. **Where can I see your work?**

   First pull any links already in the resume or LinkedIn (GitHub, portfolio,
   site) and lead with them: "From your resume: github.com/… and a portfolio
   at …". Then ask only for anything else.

   > Is there anywhere else I can see your work? Your GitHub profile, specific
   > projects or repos, a portfolio or personal site, a blog, videos, talks
   > you've given. Just paste the links. I'll use them as proof of your
   > skills when I judge roles and write applications. No links? Say
   > "nothing public". That's completely fine.

   Read the public pages (WebFetch; `gh api users/<name>/repos` for GitHub).
   Write the highlights to `profile/work.md` (what it is, what it shows, link;
   label side projects as such). **Don't stop to ask about them.** Open the
   next message (Step 2) with one line: "Saved your work: X, Y and Z stand
   out. Say 'drop X' any time if one doesn't represent you."

**Reading files:** PDF / images / text → the Read tool. DOCX →
`uv run --with python-docx python -c "import docx,sys; print('\n'.join(p.text for p in docx.Document(sys.argv[1]).paragraphs))" FILE`.
XLSX / CSV → `uv run --with openpyxl python -c ...`, or read the CSV directly.
Never use plain `python`/`python3`.

**Write `profile/resume.md`:** a faithful, complete text version of every
resume version (roles, dates, bullets, skills, education), plus anything extra
from LinkedIn, each part marked with where it came from. **Don't improve,
reword or embellish anything.** It's the factual record the jd-reader checks
against.

## Step 2 of 5: Connect email and your tracker

Connections come early so Claude can build the user's history in the
background while they answer the profile questions. Three parts, each with its
own message.

### 2a. Email (highly recommended)

Explain **in the chat text, before** the yes/no picker:
- It finds every application's real status: confirmations, interview invites,
  rejections (even ones buried as replies in old threads), and ghosting.
- It finds applications you forgot to track, and companies that said "stay in
  touch". You'll just confirm what it found instead of typing your history.
- The trade-off: Claude reads your mail through the claude.ai **Gmail**
  connector during sessions (nothing else: not your calendar or files), looks
  only at job-search messages from the last 12 months, and never sends
  anything. You can disconnect
  any time. Skipping is fine if you have security concerns.

If yes (see `docs/email-setup.md`):
1. If the Gmail tools aren't available: claude.ai → Settings → Connectors →
   **Gmail**, then restart Claude Code and resume with `claude --continue`.
2. Run one search ("thank you for applying", last 60 days). Put the count at
   the top of the next message, the tracker one ("Connected: I can see about
   50 application emails from the last two months."). Never skip it: it's
   how the user knows email works.
3. Set `email.enabled: true`.

If no: "No problem. Say **connect my email** any time and I'll pick it up from
there." Then carry on. Step 4 builds the history from their list instead.

### 2b. Your tracker

First a chat message with one line per option, then AskUserQuestion, "Where
should your tracker live?":
- **Google Sheet (recommended)**: updates automatically, opens anywhere
  including your phone, has filters and dropdowns. You can edit it by hand and
  Claude keeps your edits. Uses the claude.ai **Google Sheets** connector: no
  Google Cloud setup.
- **Google Sheet with my own service account**: only for people who already
  have one (advanced; see `docs/sheets-setup.md`).
- **CSV file**: no Google at all. Opens in Excel or Numbers, but it isn't
  live: re-open it after each update.

**Google Sheet (connector).**
1. If the Google Sheets or Google Drive tools aren't available, have the user
   connect both in claude.ai → Settings → Connectors, then restart Claude Code
   and resume with `claude --continue`.
2. Create the sheet with the Drive connector: `create_file`, title "Job Hunt
   Tracker", `contentMimeType: application/vnd.google-apps.spreadsheet`.
3. Set `tracker.backend: connector` and `tracker.sheet_id` in profile.yaml.
   Run `uv run scripts/tracker.py init-sheet` and send the steps in
   `tracker/connector-init.json` with the Sheets connector, in order and
   verbatim.
4. **Give the user the link right away, as a clickable link**: "Here's your
   tracker: [Job Hunt Tracker](https://docs.google.com/spreadsheets/d/<id>/edit).
   It's empty for now; it fills in shortly." Never just say it's "set up".

**Service account.** Set `tracker.backend: sheets`, `sheet_id`, and
`service_account` (the path to their existing key). Share the sheet with the
key's `client_email` as Editor (Drive connector `share_file`), then run
`tracker.py check` and `tracker.py init-sheet`. Send the link.

Lead with the recommended option: put "Google Sheet (Recommended)" first in the
picker.

**CSV.** Set `tracker.backend: csv`. Tell the user the file is
`tracker/jobs.csv`, and that they can open it with `! open tracker/jobs.csv`.

### 2c. What you're already tracking

> Are you already tracking your job search anywhere: a spreadsheet, a notes
> doc, a Notion page, bookmarks? Paste a Google Sheets link, drag in a file, or
> paste the list. Rough is fine. Your applications and the companies you're
> watching carry over, so you don't start from scratch.
>
> 👉 **Your turn: share your list, or say "I don't have one".**

Read it (Google Sheets link → the Sheets connector's `get_values`; files → as
above), save a copy to `profile/uploads/`, and describe it back in one line
("Got it: 23 companies, most with a role, 'applied' next to 17").

### 2d. Start the background work, then move on

In **one** message: say what's running and that they don't need to wait ("I'm
checking your inbox and finding each company's job board in the background.
That takes about 5–10 minutes. Let's do your profile in the meantime."). Then:

1. **Their list → `runs/setup/import.jsonl`** (`{"op": "add", "row": {...}}`
   per line). Don't apply yet. Rules:
   - Company + role → one row. Company only → Category Watchlist, Role empty.
   - "applied" or a date → Applied (waiting) / Applied. Nothing → To apply / Not Applied.
   - Dates without a year ("8/12") are fine; the script fills in the year.
   - Their words go in Notes, word for word. "pass" or "too much python" →
     Category Passed (**their** decision).
   - Keep every row from their list for now. Rows that hit a dealbreaker are
     left out in 4c, once the dealbreakers are known.
   - **Added by: You** on every row.
   - A real tracker with its own columns: split multi-role cells, map their
     values to ours, and map their own ratings to Fit with `"lock": ["Fit"]`.
2. **`search_started`:** set it without asking. Use the earliest application
   date in the list, but no earlier than 12 months ago (failing that, 6 months
   ago). The inbox audit refines it.
3. **Inbox audit** (if email is on): launch the **inbox-auditor** with
   `run_in_background: true`. Rows = the import plus anything already tracked;
   since = `search_started`; door-open pass on; email is searched back
   12 months at most (`email.history_months`); output
   `runs/<date>/inbox-changes.jsonl`.
4. **Companies:** import the list's companies (`--relationship target`), then
   run `uv run scripts/ats.py detect` in the background (Bash
   `run_in_background`).

## Step 3 of 5: Your profile

Five short rounds, one message each. Draft from what you already have, and ask
the user to confirm or correct.

**Round 1: Background** → `profile/background.md`, `profile.yaml → industries, titles`

A numbered draft (a few short bullets per section); corrections by number:
1. **Positions you're qualified for today** (titles held, plus roles whose
   day-to-day work they've clearly done)
2. **Industries with significant experience**: real time in the space, enough
   to talk shop with a customer there
3. **What you're strongest at** (3–5 things, with proof)
4. **Tools you've used for real**, and common requirements you **don't** have

**Round 2: Level** → `profile.yaml → level`

A chat line first, for example: "From your resume, you're mid-level: about 4
years in customer-facing technical roles." Then AskUserQuestion, "Which levels
should I search for?" ("Mid-level only" / "Mid-level and senior" /
"Senior only", adjusted to their level).

Set `level.target` from the answer, and `level.exclude` to every level **two or
more above** their highest target (target mid → exclude staff, principal,
director, vp; target senior → exclude principal, director, vp). Never remove a
level from `exclude` to let a stretch role through. `titles.stretch` already
lets those titles pass on their own.

**Round 3: Work setup and pay** → `profile.yaml → location, comp`

One question per message, each starting from what the files show:
1. Where they live and how they want to work, in **one** message. Lead with
   what you know ("From your resume: Denver (Mountain time); your last two
   roles were remote."), then AskUserQuestion, "How do you want to work?". Put
   the option the resume points to first, marked "(Recommended)": **Remote
   only** · **Remote, or hybrid/in-office near where I live** · **Open to
   relocating for the right role**. If the city isn't in the files, ask for it
   in that same message.
   - Near home → "Which cities would you go into an office in?"
   - Relocating → "Where would you move? A few cities or regions, or 'anywhere
     in the US'." Then: "Only if they help with moving costs?"
2. "What's the lowest salary you'd consider? If a posting's whole pay range is
   below that, I'll hide it. Postings without pay listed are kept." If their
   positions span different kinds of roles: "Is that the same for every kind
   of role?" Different answers go in `comp.by_title`.

**Round 4: Dealbreakers** → `profile/dealbreakers.md` (+ `profile.yaml → exclude_companies`)

"What would make you say no to a job, no matter how good it looks?" Anything
listed **hides** a role completely. Make it easy to answer: a short chat line,
then a **multi-select** AskUserQuestion with the 3–4 dealbreakers most likely
for **their** field and history (e.g. from roles they passed on in their list:
"too much python" → "Heavy coding roles"). "Other" lets them type the rest.
Other common ones to draw from: kinds of companies (crypto, gambling, defense,
adtech, government work), company size, requirements they can't meet, the
work itself (travel, on-call, managing people), specific companies, and
postings that don't sponsor visas, if they need sponsorship.

**Round 5: Job boards** → `profile/job-sources.md`

> Here's where I look for jobs:
> - **Companies' own career pages.** Every role is checked live there before
>   it goes in your tracker.
> - **Web searches** for companies like the ones that interviewed you
> - **Startup job lists** anyone can open, like Y Combinator's
>
> Is there a job board you use that isn't listed? An industry community's
> board, a newsletter's job list, an investor's portfolio board…
>
> 👉 **Your turn: say "that's it" (most people do), or paste any job board links.**

Check each link right away (WebFetch) and say plainly whether you can read it.
For login-walled or blocked boards (LinkedIn Jobs, Wellfound, Otta): "I can't
open that one, but you can paste listings from it any time." Record each one
in `job-sources.md`.

**Profile review** (one message, before leaving Step 3): everything from this
step on one screen, numbered, with defaults you didn't ask about stated
outright, so they can be changed:

> Setup · Step 3 of 5 · Your profile · review
>
> 1. Roles: Solutions Engineer, Sales Engineer, Developer Advocate
> 2. Level: mid-level only
> 3. Where: remote, or hybrid in Denver
> 4. Lowest salary: $150k
> 5. Dealbreakers: crypto, security, heavy coding roles
> 6. Job boards: career pages, web search, YC's list (default)
> 7. Hidden by default: internships, director and VP roles
>
> 👉 **Your turn: reply "looks right", or fix by number (e.g. "4: $130k").**

After a fix, show the same block again with the changed line marked
("4. Lowest salary: $130k ← changed"). Don't replay the rounds. Then write
the files, update `runs/setup/state.json`, and move on.

## Step 4 of 5: Your search so far

If the inbox audit is still running, say so: "Your inbox check is almost done.
Nothing for you to do; I'll show you what it found in about N minutes."

### 4a. Confirm your history (one message)

Build it from the list and the audit (`inbox-changes.jsonl`), then show it as a
**numbered** list, grouped:

> **Interviewing now**: 1. Acme · Solutions Engineer: 2nd round next week …
> **Interviewed before**: 4. Globex · Sales Engineer: 3–4 rounds, rejected …
> **They said "stay in touch"**: 7. …
>
> Plus N applications still waiting and N rejections, all going into your
> tracker.
>
> 👉 **Your turn: reply "looks right", fix anything by number (e.g. "4: made
> it to the final"), or add interviews I missed.**

- No email: build it from their list alone. No list either: first ask "Which
  roles did you apply to and get at least one interview for? Company and role
  is enough", then confirm in the same format.
- Afterwards, write interviews to `profile/signals.md`, and set relationships:
  `uv run scripts/ats.py set --company X --relationship interviewed` (or
  `door_open`). Import any new companies first (the audit's too), then run
  `uv run scripts/ats.py detect` in the background so /find-jobs doesn't
  have to.

### 4b. Check your targets (one message)

From the resume and the **confirmed** interviews, show positions in three
groups:

> **Proven** (you got interviews): …
> **Plausible** (you applied, and your resume supports it): …
> **Stretch** (your resume doesn't clearly support it; these score lower): …
>
> 👉 **Your turn: reply "looks right", or move anything between groups. Optional:
> add companies you'd love to work at, or postings you've seen and liked.**

Applying alone isn't proof. Kept stretch positions go into `titles.stretch`
(scored lower, never hidden by the level filter); dropped ones are removed.
Then **show the final title list and levels in the chat**, and run the
self-check: for each kept position, make a sample title ("Head of Developer
Relations") and check it against the title, stretch and level rules. Fix and
mention any that would be filtered out.

### 4c. Fill the tracker (one approval)

Connector backend: read the sheet first (CLAUDE.md → Writing the tracker).

```bash
uv run scripts/tracker.py pull
uv run scripts/tracker.py plan --changes runs/setup/import.jsonl runs/<date>/inbox-changes.jsonl runs/<date>/changes.jsonl --ghosted
```

Before planning, apply these defaults without asking:
- **No role title** → left out. The tracker is for roles.
- **Interviews quiet for 30+ days** (no reply, unanswered follow-up) →
  Category Closed, Status Ghosted, with a note ("no reply since 9/17; reopen
  if they get back to you").
- **Hits a dealbreaker** (from Round 4) → left out, unless the process is
  still active (In Conversation, Interviewing, Offer). Add those companies to
  `profile.yaml → exclude_companies`, so /find-jobs doesn't bring them back.
- **Guessed job boards** (detect's "guessed without a name check") → check
  each one yourself (WebFetch the careers page; does it link to that board?)
  and fix any wrong ones with `ats.py set`. Don't ask the user.

Queue the user's corrections from 4a as `tracker.py change` ops, then plan.
Show **in the chat**, one approval:
- **Adding:** N from your list, N found in your inbox, by category (N
  interviewing, N waiting, N door open, N closed…).
- **Left out:** N with no title (name them in one line), N that hit a
  dealbreaker (name them; "they're excluded from searches too").
- **Marked closed (stalled):** the companies, in one line.
- Job boards: "checked the N I had to guess; fixed N" (one line).

👉 **Your turn: reply "add it all", or tell me what to change (e.g. "keep
Snowflake").** Then apply, finish the write, and send the link again: "Your
tracker now has 78 rows: [Job Hunt Tracker](…)".

## Step 5 of 5: What's next

Keep it short. Open the tracker for them (CSV: `open tracker/jobs.csv`; Sheet:
the clickable link, and offer `! open "<link>"`).

1. **What's set up**, three lines: profile, email (yes/no), tracker (link or
   path) with its row count.
2. **Your next three things**, from the tracker: e.g. an interview coming up
   (offer `/apply` to prep), a follow-up that's due, a door-open company worth
   re-contacting.
3. **The routine**: `/find-jobs` finds new companies and roles · `/refresh-tracker`
   once or twice a week · `/apply` for any role.
4. **Skipped or left for later**, if anything, each with how to add it ("LinkedIn
   PDF: drag it in any time and say 'add my LinkedIn'"; "Email: say 'connect my
   email'").
5. If you logged script problems: "I noted a couple of script issues in
   runs/setup/issues.md."
6. Last line, in bold: 👉 **Your turn: run /find-jobs to find new roles that fit you.**

Set `runs/setup/state.json` to `"next": "done"`.
