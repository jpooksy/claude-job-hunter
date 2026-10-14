---
name: setup
description: First-run setup for claude-job-hunter. Collects the user's resume and context files, asks the questions that build their profile, connects email and Google Sheets (both highly recommended, both optional), seeds the company list, and calibrates the fit score. Use when the user runs /setup, is new to the repo, or wants to redo part of setup ("set up Google Sheets", "connect my email", "redo my profile").
---

# Setup

Walk the user through setup one step at a time. After every step, say in one
line what was saved and what comes next.

If `profile/profile.yaml` already exists, ask which part to redo (profile
questions, email, Google Sheets, companies, calibration) and jump to that step.
To set up only one piece ("connect Gmail", "switch to Google Sheets"), run that
step alone.

## How to ask (applies to every step)

- **One question per message.** Ask, then wait for the user's reply before
  doing anything else. Never bundle a follow-up ("what was the Dataiku role?")
  with the next question. Ask the follow-up on its own and wait.
- **Open-ended questions** (files, links, lists, descriptions) go in a
  **plain chat message**, never AskUserQuestion. The user answers by dragging
  in a file, pasting text or a link, typing, or saying "skip".
- **AskUserQuestion only for real choices**: remote vs. hybrid, yes/no on email
  and Google Sheets, "add it or skip?". Never offer an option that means "I'll
  give you the content next" (like "I'll type it"). The picker records only the
  label, and the user never gets to type. If an answer needs content, ask for
  it in a plain message and wait for the next reply.
- **Every question has the same shape:**
  1. a plain question about the user's real situation, in the second person,
     with no jargon ("Which roles did you…", "Are you already tracking…")
  2. **what counts as an answer**, always including a low-effort option ("just
     the company names is fine")
  3. **why it helps**, in terms of their results
  4. **what skipping costs**, in one line (optional questions only)
- **Never ask for the same thing twice.** Later rounds start from what earlier
  answers already gave you, and ask only what's missing.
- **Skips:** discourage a skip **once**. Reply with the one-line cost and ask
  (AskUserQuestion) "Add it after all" / "Skip it". If they skip, accept it and
  never bring it up again.

## Step 0: Prepare (no questions)

```bash
uv --version || echo "uv missing"
mkdir -p profile/uploads data tracker runs/setup drafts
cp -n templates/profile/* profile/
cp -n templates/companies.csv data/companies.csv
```

If uv is missing, have the user install it (`brew install uv`, or
`curl -LsSf https://astral.sh/uv/install.sh | sh`) and restart the terminal.

Open with a short welcome: what setup does (about 15–25 minutes), and that
email and Google Sheets are recommended but optional. Mention that they can
drag files straight into the chat.

## Step 1: Your files and history

Six questions, one per message, in this order. Use the wording below as a
guide (keep the shape; your own words are fine).

**Handling a file.** Copy it into `profile/uploads/` right away
(`cp "<path>" profile/uploads/`) and confirm in one line ("Got it:
resume.pdf"). If the copy fails with "Operation not permitted" (macOS privacy
protection for ~/Downloads, ~/Desktop, ~/Documents), have the user type
`! cp "<path>" profile/uploads/` in the prompt, or drag the file into
`profile/uploads/` in Finder.

1. **Resume** (required, so no skip)
   > Let's start with your resume. Drag the file in (PDF, Word or text), or
   > paste the text. Everything gets checked against it: each posting's
   > requirements, and anything I write for your applications.

2. **LinkedIn profile**
   > Can you add your LinkedIn profile as a PDF? On LinkedIn, open your
   > profile → **Resources → Save to PDF**, then drag the file in. Pasting
   > your profile URL also works if downloading is a hassle. It catches things
   > your resume leaves out, like older roles, projects and skills. If you
   > skip it, I'll judge matches on your resume alone.

3. **Other resume versions**
   > Do you have other versions of your resume, for a different kind of role?
   > Drag them in, or say "just the one". Each version shows how you pitch
   > yourself for that kind of role. If you skip it, roles outside your main
   > resume's framing will score lower.

4. **Roles you interviewed for**
   > Which roles did you apply to and get at least one interview for? A saved
   > posting, a link, pasted text, or just the **company and role title** all
   > work. Old postings are usually taken down, so titles are fine. Add how
   > far you got if you remember. These are proof of what you're qualified
   > for, and I'll look for more roles like them. If you skip it, I'll
   > research from your company list alone.

   Only roles that got an interview. Postings they merely liked belong in
   Round 3 (Targets), where they get the reality check. If the user gives
   both, keep the liked ones for Round 3.

5. **What you're already tracking**
   > Are you already tracking your job search anywhere: a spreadsheet, a notes
   > doc, a Notion page, bookmarks? Paste a Google Sheets link, drag in a file,
   > or paste the list. I'll bring it in so your applications and the
   > companies you're watching carry over instead of starting from scratch.
   > If you don't have one, I can give you a blank sheet to fill in. If you
   > skip it, you start with an empty tracker, and past applications only
   > show up if you connect email.

   If they want a blank sheet:
   - **If the Google Drive connector is already connected** (its tools, e.g.
     `create_file`, are available): create a Google Sheet titled "Job Hunt –
     My list" using `create_file` with `contentMimeType: text/csv` and
     `textContent: "Company,Role,Status,Date applied,Link,Notes\n"`. That
     converts it to a native Sheet. Send the link and wait until they say
     they're done.
   - **Otherwise:** write `profile/uploads/my-list.csv` with the same header,
     `open` it, and wait until they say they've saved it.
   Don't connect the Drive connector here. That happens in Step 4.

   Read what they shared (Google Sheets link → Drive connector
   `read_file_content`; files → see below), then **describe it back in two or
   three lines** ("About 110 rows: companies, roles, a status column and your
   own fit scores. Some cells list several roles."). Ask only about what you
   genuinely can't tell, one question at a time. Save a copy to
   `profile/uploads/`. It's imported into the tracker in Step 5.

6. **Proof points**
   > Last file: do you have a brag doc, performance reviews, or a portfolio?
   > Drag them in, or paste a few wins (results, praise, projects). I'll use
   > them as real proof in your application answers. If you skip it, answers
   > will rely on your resume bullets only.

### Reading the files

- PDF / images / text: use the Read tool.
- DOCX: `uv run --with python-docx python -c "import docx,sys; print('\n'.join(p.text for p in docx.Document(sys.argv[1]).paragraphs))" FILE`
- XLSX / CSV: `uv run --with openpyxl python -c ...`, or read the CSV directly.

### Writing what you learned

- `profile/resume.md`: a faithful, complete text version (roles, dates,
  bullets, skills, education). Merge in anything extra from the LinkedIn PDF
  and other resume versions, and mark where it came from. **Don't improve,
  reword or embellish anything.** It's the factual record the jd-reader checks
  against.
- `profile/signals.md`: the roles from question 4 (company, role, how far,
  outcome), plus what they have in common, for the researcher.
- Proof points from question 6 → `profile/background.md` (strengths section).

## Step 2: Profile questions

Draft answers from what you already have (resume, the interview list, their
tracker), then ask the user to **confirm or correct**. That's faster than
asking from scratch. One round per message.

**Round 1: Background** → `profile/background.md`, `profile.yaml → level, industries, titles`

Show your draft and ask them to correct it:
1. **Positions you're qualified for today** (titles held, plus roles whose
   day-to-day work they've clearly done)
2. **Industries with significant experience**: real time in the space, enough
   to talk shop with a customer there
3. **Current level** and years of experience, and the levels to target
   (usually the current level, maybe one up)
4. **What you're strongest at** (3–5 things, with proof)
5. **Tools you've used for real**, and common requirements you **don't** have
   (so we don't chase roles that need them)

**Round 2: Fill in the interview details** → `profile/signals.md`, companies with relationship `interviewed` / `door_open`

Don't ask for the interview list again; question 4 already gave it to you.
List the roles back and ask only what's missing for each: how far they got,
the outcome, and what seemed to resonate. Then ask:
- Any **interest that didn't come from an application**: recruiters who
  reached out, or companies that passed but said **"stay in touch"**? (If
  email will be connected, say the inbox audit will look for these too.)
- If email will **not** be connected, and question 5 didn't cover it: which
  applications are open right now? (Company, role, date applied, status.)

**Round 3: Targets** → `profile/targets.md`, companies with relationship `target`

Before asking, say this plainly (in your own words):

> List companies and positions you're **actually qualified for today**, not
> where you hope to be in a few years. I'll take this list at face value. If
> it's inflated, I'll find you roles you won't get, and the good matches get
> buried. Honest inputs get you better results.

Start from what you have: the companies in their tracker (question 5) and any
postings they said they liked. ("Your list already has 40 companies. Any to
add, or any you've lost interest in?") Then ask:
1. Companies you'd love to work at that aren't on the list yet.
2. Positions you're interested in, and any postings you've seen and liked.

Then **reality-check** every target position (and liked posting) against the
resume. Write a short table (position / verdict: qualified, stretch, not yet /
one-line reason) and tell the user honestly. Keep stretch positions only if
they want them, and say they'll score lower. Drop "not yet" positions from
`titles.include` unless the user insists.

**Round 4: Logistics** → `profile.yaml → location, comp, search_started`

Ask one at a time. Use AskUserQuestion only for the multiple-choice part
(remote required / preferred / flexible); the rest are plain questions:
- Where you live (city, time zone), and whether remote is required,
  preferred or flexible. If hybrid or onsite is OK, in which metros?
- Lowest acceptable pay. Explain: "a posted range whose **top** is at or
  below this gets dropped".
- Work authorization: if they need sponsorship, add it to dealbreakers.md as a
  check ("posting says no sponsorship").
- When they started this search. The first inbox audit looks back to then.

**Round 5: Dealbreakers** → `profile/dealbreakers.md` (+ `profile.yaml → exclude_companies, level.exclude`)

Ask for hard no's. Offer examples so they think broadly:
industries or company types (e.g. security, adtech, crypto, gambling,
defense, government/public sector), buyers they can't sell to or work with,
requirements they can't meet (e.g. "5+ years as a software engineer",
"enterprise quota-carrying"), company size (too big or too small), travel,
on-call, specific companies. Explain that these **remove** roles; they don't
just lower the score.

**Round 6: Warm networks (optional)** → `profile/warm-networks.md`

VC portfolio job boards they have a contact at, alumni or community groups,
former colleagues who offered referrals.

**Write the files**, then generate `titles.include` regexes from the
qualified positions (broad enough for variants, e.g.
`'solutions? (engineer|architect|consultant)'`, `'sales engineer'`). Set
`titles.exclude` from obviously wrong look-alikes ("intern", or
"account executive" for an SE). Show the user the title list and confirm it.

## Step 3: Email (highly recommended)

Explain what it gives them:
- Finds every application's real status: confirmations, interview invites,
  rejections (even ones buried as replies in old threads), and ghosting.
- Finds applications missing from the tracker.
- Finds companies that rejected them but said "stay in touch" (door-open
  leads, often the warmest opportunities).

Explain the trade-off honestly: Claude reads their mail through the claude.ai
Gmail connector during sessions. The inbox-auditor looks only at job-search
messages, never sends anything, and they can disconnect any time. If they
have security concerns, it's fine to skip. They'll update statuses by
telling Claude ("I got rejected by Acme").

If yes, follow `docs/email-setup.md`:
1. claude.ai → Settings → Connectors → connect **Gmail**.
2. Claude Code must be signed in with the same claude.ai account (`/login`).
   Restart Claude Code so the connector loads.
3. Verify: run one Gmail search ("thank you for applying", last 60 days) and
   report the count, not the contents.
4. Set `email.enabled: true` in profile.yaml.

Other email providers: any email connector or MCP that can search and read
threads works. The inbox-auditor's queries may need adapting.

## Step 4: Google Sheets (highly recommended)

Explain why it beats CSV: the tracker **updates automatically** in a real
spreadsheet you can open anywhere (including your phone), with filters,
dropdowns, color-coded fit scores, and sorting. You can edit it by hand and
Claude keeps your edits. The CSV option works, but you have to re-open the
file after every update, and it's easy to edit a stale copy.

Security: the scripts use a Google **service account** that can only touch
spreadsheets you explicitly share with it. Nothing else in your Drive.

If they decline: set `tracker.backend: csv` and tell them the tracker lives in
`tracker/jobs.csv` (opens in Excel, Numbers or Google Sheets import). They
can switch later with "/setup Google Sheets".

If yes, follow `docs/sheets-setup.md`. Go one step at a time and wait for the
user each time:

1. **Google Drive connector**: claude.ai → Settings → Connectors → Google
   Drive (restart Claude Code if newly connected). Claude uses it to create the
   sheet in the user's own Drive and share it with the service account.
2. **Service account + key**: if the user already has a service-account
   JSON key they want to reuse, set its path in `tracker.service_account` and
   skip to step 3. Otherwise, walk the user through the Cloud Console steps in
   `docs/sheets-setup.md` (create project → enable Sheets API → create service
   account → create JSON key). Then move the key into place:
   ```bash
   mkdir -p ~/.config/claude-job-hunter
   mv ~/Downloads/<key-file>.json ~/.config/claude-job-hunter/service-account.json
   chmod 600 ~/.config/claude-job-hunter/service-account.json
   ```
   If macOS blocks reading ~/Downloads, have the user run the `mv` themselves
   by typing `! mv ...` in the Claude Code prompt.
   Read only the `client_email` field from the key; **never print the private key**:
   `uv run python -c "import json,os;print(json.load(open(os.path.expanduser('~/.config/claude-job-hunter/service-account.json')))['client_email'])"`
3. **Create the sheet** with the Drive connector: `create_file` with title
   "Job Hunt Tracker" and contentMimeType
   `application/vnd.google-apps.spreadsheet`. Then `share_file` it with the
   `client_email` as `writer`. (A service account can't create the file
   itself: it has no Drive storage, so creating as the user is required.)
   No Drive connector? Have the user open https://sheets.new, name it, click
   Share, add the `client_email` as Editor, and paste the URL.
4. Put the sheet ID into profile.yaml (`tracker.backend: sheets`,
   `tracker.sheet_id`), then:
   ```bash
   uv run scripts/tracker.py check
   uv run scripts/tracker.py init-sheet
   ```
   Give the user the sheet link.

Troubleshooting is in `docs/sheets-setup.md` (403 = not shared or API not
enabled; 404 = wrong ID).

## Step 5: Seed the company list (and import their old tracker)

### 5a. Import what they were already tracking (if question 5 gave you something)

Turn it into tracker rows, **one row per role**:
- **Split** cells that list several roles (separated by "•", ";", "/" or new
  lines) into separate rows with the same company.
- **Map their columns** to ours (Company, Role, Status, Applied, Comp,
  Location, URL, Notes, Fit). Keep their columns we don't have in Notes.
- **Map their category and status values** to ours (Category: Interviewing,
  Applied (waiting), Door open (reapply), To apply, Watchlist, Passed, Closed;
  Status: Not Applied, Applied, In Conversation, Interviewing, Offer,
  Rejected, Ghosted, Hiring Freeze, Closed). A free-text note in a category
  or status cell ("onsite in NYC, passed") is **the user's decision**: map it
  to the closest value (here Passed) and copy the note into Notes.
- **Their own scores** go in Fit, with `"lock": ["Fit"]` on the op so later
  runs never overwrite them.
- Dates become YYYY-MM-DD. Source is "My list". Keep URLs; posting links from
  Greenhouse, Ashby or Lever get IDs automatically, so `/refresh-tracker` can
  re-check them.
- Rows that are just a company with no role → Category Watchlist, Role empty.

Before writing anything, **show the mapping** in a short table (their value →
our value, with row counts) and the 5 trickiest rows, and ask for a yes. Then
write the ops to `runs/setup/import.jsonl`, one per line:
`{"op": "add", "row": {...}, "lock": ["Fit"]}`, and run:

```bash
uv run scripts/tracker.py pull
uv run scripts/tracker.py plan --changes runs/setup/import.jsonl
uv run scripts/tracker.py apply
```

### 5b. Seed the company list

Write the signal, door-open, target and warm-network companies (plus every
company from the imported tracker, as `target`, unless it's already a signal)
to a JSONL file
(`{"company": ..., "domain": ...}` per line, one file per relationship) and
import each with its relationship:

```bash
uv run scripts/ats.py import runs/setup/interviewed.jsonl --relationship interviewed
uv run scripts/ats.py import runs/setup/targets.jsonl --relationship target
# ... door_open, warm
uv run scripts/ats.py detect
```

Look up domains you don't know (WebSearch). Report which companies have no
supported job board (`no_ats`), and ask the user to confirm any marked
`guessed`: the slug might belong to a different company with the same name.

## Step 6: First inbox audit (if email is connected)

```bash
uv run scripts/tracker.py pull
```

Launch the **inbox-auditor** agent: rows file `tracker/snapshot.csv`, since =
`search_started`, include the door-open pass (3 years), output
`runs/<date>/inbox-changes.jsonl`. Then:

```bash
uv run scripts/tracker.py plan --changes runs/<date>/inbox-changes.jsonl
```

Show the plan, get a yes, `apply`, and set `email.last_audit` to today. Add
any door-open companies it found to data/companies.csv (relationship
`door_open`) with `ats.py import` + `detect`.

## Step 7: Calibrate the fit score

Score real postings before the full search, so the rubric matches the user's
judgment from day one:

```bash
uv run scripts/ats.py fetch
uv run scripts/filter.py
```

Pick up to 10 candidates spread across companies. Run one **jd-reader** on a
batch file with them (write a `runs/<date>/batches/calibration.jsonl` if
needed), then `uv run scripts/score.py --dry-run`.

Show a table: company, role, score, the reasoning line. Ask the user for
**their** score for each and what's off. Adjust `profile/fit-score.yaml`,
`dealbreakers.md` or `titles` to match, and re-run `score.py --dry-run`.
Stop when most scores are within ±1 of theirs (two or three rounds at most).
Then run `score.py` without `--dry-run`, and `tracker.py plan --scored ...` →
confirm → `apply`, so these roles land in the tracker.

## Step 8: Wrap up

Summarize what's set up (profile, email yes/no, tracker type + link,
companies seeded), then offer to run **/find-jobs** now. Mention the routine:
`/refresh-tracker` once or twice a week, and `/apply` for any role they want
to go after.
