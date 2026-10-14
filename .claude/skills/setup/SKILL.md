---
name: setup
description: First-run setup for claude-job-hunter. Collects the user's resumes and history, asks short rounds of questions to build their profile, connects email and a Google Sheet tracker (both recommended, both optional), and fills the tracker from their own list and inbox. Use when the user runs /setup, is new to the repo, or wants to redo part of setup ("set up Google Sheets", "connect my email", "redo my profile").
---

# Setup

Setup builds the user's **profile** and **tracker**. It does **not** search for
new jobs. That's `/find-jobs`, which they run right after. Say this in the
welcome, and again at the end.

If `profile/profile.yaml` already exists, ask which part to redo (files,
profile, email, tracker, fill the tracker) and jump to that step. To set up
just one piece ("connect Gmail", "switch to Google Sheets"), run that step
alone.

## How to talk to the user (every step)

**Shape of every message:**
1. **Progress header** as the first line: `Setup · Step 2 of 6 · Your profile (round 3 of 6)`.
2. One short line on **what this step is for**, the first time a step starts.
3. The question or the content to approve, **in the chat text itself**.
4. **The ask, in bold, as the very last line**, set apart by a blank line:

   👉 **Your turn: reply "looks right", or tell me what to change.**

   The ask must be impossible to miss:
   - **Exactly one ask per message**, and it's the bolded last line. If the
     message has a question in its body, repeat it as the bolded ask.
   - Say **exactly what to do**: the action, plus the accepted answers ("Drag
     in your resume, or paste the text"; "Reply with numbers, or 'all good'").
     Avoid vague asks like "Thoughts?" or "Let me know."
   - Never end on an explanation, a "why it helps", or a status update. Those
     go before the ask.
   - Even when a picker follows, write the bolded ask in the message first, so
     it's clear what the picker is for.

"Why it helps" goes before the ask, never after it.

**Asking:**
- **One question per message.** Wait for the reply before doing anything
  else. Never bundle a follow-up with the next question.
- **Open-ended questions** (files, links, lists, descriptions) go in a plain
  chat message. The user drags in a file, pastes, types, or says "skip".
- **AskUserQuestion is only for real choices** (remote vs. relocate, yes/no on
  email, which tracker). One question per call. Never offer an option that
  means "I'll tell you in my next message"; it swallows the answer. If an
  answer needs content, ask in a plain message.
- **Anything the user approves must be visible in the chat text of that same
  message**: lists, mappings, title patterns, rows to add. Tool output is
  collapsed, so never refer to it as "above". Copy what matters into the
  message.
- **Every question has the same shape:** a plain question about their real
  situation (second person, no jargon) → what counts as an answer, including a
  low-effort option ("just the company names is fine") → why it helps → what
  skipping costs (optional questions only).
- **Examples fit the user.** Build examples from their own resume and field.
  When you don't know enough yet, use neutral ones ("a result you're proud
  of").
- **Never ask for the same thing twice.** Later rounds start from what earlier
  answers gave you and ask only what's missing.
- **Skips:** discourage a skip once (one line on the cost, then "Add it after
  all" / "Skip it"). If they skip, accept it and don't bring it up again.
  **"I don't have one" is an answer, not a skip.** Offer a low-effort
  alternative once, in a sentence, then move on.
- **Don't assume the user's situation.** Most people have one resume, no saved
  postings, and at best a rough list of companies.

**Working:**
- **Anything that takes more than ~30 seconds** (reading files, the inbox
  audit, checking job boards): say what's happening and roughly how long
  before you start. Say when it's done.
- **Corrections overwrite drafts.** When the user corrects a round, re-read
  their reply against each numbered section before writing, and echo what
  changed ("Level: mid only (was mid + senior)").
- **Don't use email or Drive before their step** unless the user points you to
  a specific email or file.
- **Script problems you work around** go in `runs/setup/issues.md`, not in the
  user's chat. Mention once at the end that you logged them.

## Step 0: Prepare (no questions)

```bash
uv --version || echo "uv missing"
mkdir -p profile/uploads data tracker runs/setup drafts
cp -n templates/profile/* profile/
cp -n templates/companies.csv data/companies.csv
```

If uv is missing, have the user install it (`brew install uv`, or
`curl -LsSf https://astral.sh/uv/install.sh | sh`) and restart the terminal.

Welcome (short):
- Setup takes **about 20 minutes**. Most of it is answering questions. The
  inbox check runs on its own for a few minutes.
- Six steps: your files → your profile → email → your tracker → filling the
  tracker → what's next.
- It builds your profile and tracker; finding **new** jobs comes right after,
  with `/find-jobs`.
- They can drag files straight into the chat.

## Step 1 of 6: Your files and history

Five questions, one per message.

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

3. **Roles you interviewed for**
   > Which roles did you apply to and get at least one interview for? Just
   > the **company and role title** is fine, plus how far you got if you
   > remember. Saved postings, links or pasted text work too, but old
   > postings are usually taken down. These are proof of what you're
   > qualified for, and I'll look for more roles like them. If you skip it,
   > I'll research from your company list alone.

   Only roles that got an interview. Postings they merely liked are for Step 2
   round 4.

4. **What you're already tracking**
   > Are you already tracking your job search anywhere: a spreadsheet, a notes
   > doc, a Notion page, bookmarks? Paste a Google Sheets link, drag in a file,
   > or paste the list. I'll bring it in so your applications and the
   > companies you're watching carry over. If you don't have one, that's
   > fine. If you skip it, past applications only show up if you connect
   > email.

   Read what they shared (a Google Sheets link → the Google Sheets connector's
   `get_values`, or the Drive connector's `read_file_content`; files → see
   below). **Describe it back in one or two lines** ("Got it: 23 companies,
   most with a role, and 'applied' next to 9 of them"). Expect something rough;
   that's normal and plenty. Ask only about what you genuinely can't tell, one
   question at a time. Save a copy to `profile/uploads/`. It's imported in
   Step 5.

5. **Where can I see your work?**
   > Is there anywhere I can see your work? Your GitHub profile, specific
   > projects or repos, a portfolio or personal site, a blog, videos, talks
   > you've given. Just paste the links. I'll use them as proof of your
   > skills when I judge roles and write applications. No links? Say
   > "nothing public". That's completely fine.

   Read the public pages (WebFetch; `gh api users/<name>/repos` for GitHub).
   Write the highlights to `profile/work.md` (what it is, what it shows, link;
   label side projects as such). Confirm in a line or two: "I see 3 projects
   that stand out: X, Y, Z. Anything here that doesn't represent you well?"

### Reading files

- PDF / images / text: use the Read tool.
- DOCX: `uv run --with python-docx python -c "import docx,sys; print('\n'.join(p.text for p in docx.Document(sys.argv[1]).paragraphs))" FILE`
- XLSX / CSV: `uv run --with openpyxl python -c ...`, or read the CSV directly.

### Writing what you learned

- `profile/resume.md`: a faithful, complete text version of every resume
  version (roles, dates, bullets, skills, education), plus anything extra from
  LinkedIn, each part marked with where it came from. **Don't improve, reword
  or embellish anything.** It's the factual record the jd-reader checks
  against.
- `profile/signals.md`: the roles from question 3 (company, role, how far,
  outcome).

## Step 2 of 6: Your profile

Six short rounds. Draft from what you already have, then ask the user to
**confirm or correct**. One round per message.

**Round 1: Background** → `profile/background.md`, `profile.yaml → industries, titles`

Show a numbered draft (a few short bullets per section) and ask for
corrections ("3: …"):
1. **Positions you're qualified for today** (titles held, plus roles whose
   day-to-day work they've clearly done)
2. **Industries with significant experience**: real time in the space, enough
   to talk shop with a customer there
3. **What you're strongest at** (3–5 things, with proof)
4. **Tools you've used for real**, and common requirements you **don't** have

**Round 2: Level** → `profile.yaml → level`

A decision, not buried in a draft. State their current level and years in a
line, then AskUserQuestion: "Which levels should I search for?" with options
such as "Mid-level only" / "Mid-level and senior" / "Senior only" (adjusted
to their level).

**Round 3: Interview details and other interest** → `profile/signals.md`, companies with relationship `interviewed` / `door_open`

List the roles from Step 1 question 3 back. Ask only what's missing for each
(how far, outcome, what resonated). Then: any interest that didn't come from
an application, like recruiters who reached out, or companies that said "stay
in touch"? Say that if they connect email, Claude will look for these too, so
a rough answer is fine.

**Round 4: Check your targets** → `profile/targets.md`, `profile.yaml → titles`

A verification, not an open question. From the resume, the interviews and
their list, show the positions in three groups:

> **Proven** (you got interviews): …
> **Plausible** (you applied, and your resume supports it): …
> **Stretch** (your resume doesn't clearly support it; these score lower): …
>
> Companies you're watching: …
>
> 👉 **Your turn: reply "looks right", or move anything between groups (e.g.
> "drop the stretch ones"). Optional: add companies you'd love to work at, or
> postings you've seen and liked.**

Applying alone isn't proof. Stretch positions the user keeps go into
`titles.stretch` (scored lower, never hidden by the level filter). Dropped ones
are removed from `titles.include`.

**Round 5: Work setup and pay** → `profile.yaml → location, comp`

One question per message:
1. Where they live: city (infer the time zone and confirm it).
2. AskUserQuestion, "How do you want to work?":
   **Remote only** · **Remote, or hybrid/in-office near where I live** ·
   **Open to relocating for the right role**.
   - Near home → "Which cities would you go into an office in?"
   - Relocating → "Where would you move? A few cities or regions, or 'anywhere
     in the US'." Then: "Only if they help with moving costs?"
     (`relocate_to`, `relocation_help_required`)
3. "What's the lowest salary you'd consider?" Say, in plain words: "If a
   posting's whole pay range is below that, I'll hide it. Postings without pay
   listed are kept." If their target positions span different kinds of roles,
   ask: "Is that the same for every kind of role you're targeting?" Different
   answers go in `comp.by_title`.

**Round 6: Dealbreakers and warm paths** → `profile/dealbreakers.md`, `profile/warm-networks.md` (+ `profile.yaml → exclude_companies`)

First message: "What would make you say no to a job, no matter how good it
looks?" Anything listed **hides** a role completely. Offer a few examples that
fit **their** field: kinds of companies (crypto, gambling, defense, adtech,
government work), company size, requirements they can't meet, the work itself
(travel, on-call, managing people), specific companies, or postings that say
they don't sponsor visas, if they need sponsorship. A short list is fine.

Second message: "Do you know people who could refer you, or belong to groups
that share jobs?" Examples: former coworkers at other companies, a school
alumni group, a Slack or Discord community, or an investor's job board (many
venture firms list jobs at the startups they've funded) where you know
someone. "No" is a fine answer.

**Then write the files, and show the result in the chat** (not in tool output):
- the title patterns (`titles.include`, `titles.stretch`, `titles.exclude`) as
  a short list of plain-English role names
- levels, location rule, pay floor(s)

**Self-check before moving on:** for each kept position, make a sample title
("Head of Developer Relations") and check it against the title, stretch and
level rules. If a kept role would be filtered out, fix the profile (e.g. put it
in `titles.stretch`) and say so in one line.

## Step 3 of 6: Email (highly recommended)

Explain **in the chat text, before** the yes/no picker:
- It finds every application's real status: confirmations, interview invites,
  rejections (even ones buried as replies in old threads), and ghosting.
- It finds applications missing from their tracker, and companies that said
  "stay in touch".
- The trade-off: Claude reads their mail through the claude.ai Gmail
  connector during sessions, looks only at job-search messages, and never
  sends anything. They can disconnect any time. Skipping is fine if they have
  security concerns.

If yes (see `docs/email-setup.md`):
1. If the Gmail tools aren't available: claude.ai → Settings → Connectors →
   **Gmail**, then restart Claude Code and resume this session with
   `claude --continue`.
2. Run one search ("thank you for applying", last 60 days) and **report the
   count** ("Connected: I can see 33 application emails from the last two
   months"). Don't report the contents.
3. Set `email.enabled: true`.

If they skip email and Step 1 question 4 didn't cover it, ask (plain message):
"Which applications do you have open right now? Company and role is enough."

## Step 4 of 6: Your tracker

AskUserQuestion, "Where should your tracker live?", with a short line of
explanation for each option **in the chat text** first:
- **Google Sheet (recommended)**: updates automatically, opens anywhere
  including your phone, has filters and dropdowns. You can edit it by hand and
  Claude keeps your edits. Uses the claude.ai **Google Sheets connector**: no
  Google Cloud setup.
- **Google Sheet with my own service account**: only for people who already
  have one (see `docs/sheets-setup.md`, advanced).
- **CSV file**: no Google at all. Opens in Excel or Numbers, but it isn't
  live: re-open it after each update.

**Google Sheet (connector).** See `docs/sheets-setup.md`:
1. If the Google Sheets or Google Drive tools aren't available, have the user
   connect both in claude.ai → Settings → Connectors, then restart Claude Code
   and resume with `claude --continue`.
2. Create the sheet with the Drive connector: `create_file`, title "Job Hunt
   Tracker", `contentMimeType: application/vnd.google-apps.spreadsheet`.
3. Set `tracker.backend: connector` and `tracker.sheet_id` in profile.yaml.
   Run `uv run scripts/tracker.py init-sheet` and send the steps in
   `tracker/connector-init.json` with the Sheets connector, in order and
   verbatim.
4. Give the user the link to the sheet.

**Service account.** Set `tracker.backend: sheets`, `sheet_id`, and
`service_account` (the path to their existing key). Share the sheet with the
key's `client_email` as Editor (Drive connector `share_file`), then run
`tracker.py check` and `tracker.py init-sheet`.

**CSV.** Set `tracker.backend: csv`. Tell the user the file is
`tracker/jobs.csv`, and that they can open it with `! open tracker/jobs.csv`.
They can switch to a Google Sheet later with "/setup Google Sheets".

Writing to the tracker always follows CLAUDE.md → **Writing the tracker**.

## Step 5 of 6: Fill your tracker

Say what's about to happen and how long it takes ("I'll bring in your list,
then check your inbox, which takes about 5–10 minutes"). Then do all of it, and
show **one** combined summary for approval.

### 5a. Their own list (if Step 1 question 4 gave one)

Write ops to `runs/setup/import.jsonl`, one per line (`{"op": "add", "row": {...}}`).
Usually a rough list. Handle it simply:
- Company + role → one row. Company only → Category Watchlist, Role empty.
- "applied" or a date applied → Category Applied (waiting), Status Applied.
  Nothing → To apply / Not Applied.
- Dates without a year ("8/12") are fine; the script fills in the year.
- Whatever else they wrote goes in Notes, word for word. A note like "pass" or
  "too much python" is **their decision**: Category Passed.
- **Added by: You** on every row.

If it's a real tracker with its own columns, also:
- split cells that list several roles into one row each
- map their category/status values to ours
- map their own ratings (if any) to a 1–10 Fit, with `"lock": ["Fit"]` on the op

### 5b. The inbox audit (if email is connected)

Set `search_started` without asking: the earliest application date from 5a, or
failing that the earliest application email in the last 12 months, or failing
that 6 months ago. Say it in one line ("I'll search back to July 28, your
earliest application. Tell me if you started earlier.").

Launch the **inbox-auditor**: rows = what 5a will add plus anything already in
the tracker, since = `search_started`, door-open pass over 3 years, output
`runs/<date>/inbox-changes.jsonl`. While it runs, do 5c.

### 5c. Companies

Write every company the user named (interviews, door-open, targets, warm
networks, their list) to JSONL files by relationship and import them. Then
detect job boards:

```bash
uv run scripts/ats.py import runs/setup/interviewed.jsonl --relationship interviewed
uv run scripts/ats.py import runs/setup/targets.jsonl --relationship target
# ... door_open, warm (their list's companies go in as target)
uv run scripts/ats.py detect
```

Look up websites you don't know (WebSearch). To fix a board by hand:
`uv run scripts/ats.py set --company X --ats lever --slug y` (or `--none`).
Manual fixes are never re-guessed.

### 5d. One plan, one approval

```bash
uv run scripts/tracker.py pull
uv run scripts/tracker.py plan --changes runs/setup/import.jsonl runs/<date>/inbox-changes.jsonl --ghosted
```

Show in the chat, before asking:
- **From your list:** N rows (N applied, N to apply, N passed)
- **From your inbox:** N applications you hadn't tracked, N status changes
  (rejections, interviews, door-open), N marked ghosted. Name the most
  important few, e.g. upcoming interviews.
- **Need your input:** rows with no role title, recruiter outreach that isn't
  logged, applications that conflict with a dealbreaker (kept as Applied, with
  a note)
- **Job boards:** "Found job boards for 26 of 31 companies. For Acme,
  Globex and Initech I'll check their careers pages by hand." For any
  `guessed` board, list its link (e.g. `https://jobs.ashbyhq.com/<slug>`) and
  ask whether it's the right company.

Ask once ("Add all of this?"), then apply.

## Step 6 of 6: What's next

Keep it short. Open the tracker for them (CSV: `open tracker/jobs.csv`; Sheet:
give the link).

1. **What's set up**, three lines: profile, email (yes/no), tracker (link or
   path) with its row count.
2. **Your next three things**, taken from the tracker: e.g. an interview
   coming up (offer `/apply` to prep), a follow-up that's due, a door-open
   company worth re-contacting.
3. **The routine**: `/find-jobs` finds new companies and roles (about 15–25
   minutes) · `/refresh-tracker` once or twice a week · `/apply` for any role.
4. If you logged script problems, one line: "I noted a couple of script issues
   in runs/setup/issues.md."
5. Last line, in bold: 👉 **Your turn: run /find-jobs to find new roles that fit you.**
