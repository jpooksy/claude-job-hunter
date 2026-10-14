---
name: setup
description: First-run setup for claude-job-hunter. Collects the user's resume and context files, asks the questions that build their profile, connects email and Google Sheets (both highly recommended, both optional), seeds the company list, and calibrates the fit score. Use when the user runs /setup, is new to the repo, or wants to redo part of setup ("set up Google Sheets", "connect my email", "redo my profile").
---

# Setup

Walk the user through setup one step at a time. **Never dump every question at
once.** Ask a round, wait, write what you learned to the files, then move on.
After every step, say in one line what was saved and what comes next.

If `profile/profile.yaml` already exists, ask which part to redo (profile
questions, email, Google Sheets, companies, calibration) and jump to that step.
To set up only one piece ("connect Gmail", "switch to Google Sheets"), run that
step alone.

## Step 0: Prepare (no questions)

```bash
uv --version || echo "uv missing"
mkdir -p profile/uploads data tracker runs drafts
cp -n templates/profile/* profile/
cp -n templates/companies.csv data/companies.csv
```

If uv is missing, have the user install it (`brew install uv`, or
`curl -LsSf https://astral.sh/uv/install.sh | sh`) and restart the terminal.

Open with a short welcome: what setup does (about 15–25 minutes), and that
email and Google Sheets are recommended but optional.

## Step 1: Files

Collect files **one question at a time**. Ask each one with AskUserQuestion,
wait for the answer, deal with it, then ask the next. Never list all six at
once.

Every question:
- says in one line **why it matters** and **what skipping costs**
- offers these ways to answer: drag a file into the chat (that pastes its path),
  type or paste the information directly, or skip (questions 2–6 only)

Options for a question: "I'll drag in a file", "I'll type it instead", "Skip".
Question 5 also gets "Create a sheet for me to fill in". The user can always
answer in free text instead.

**Handling a file.** Copy it into `profile/uploads/` right away
(`cp "<path>" profile/uploads/`) and confirm in one line ("Got it:
resume.pdf"). If the copy fails with "Operation not permitted" (macOS privacy
protection for ~/Downloads, ~/Desktop, ~/Documents), have the user run it
themselves by typing `! cp "<path>" profile/uploads/` in the prompt, or drag
the file into `profile/uploads/` in Finder.

**Handling a skip.** Discourage it **once**: reply with the one-line cost and
ask "Add it after all, or skip?" If they still skip, accept it and move on.
Never bring it up again during setup.

### The questions

1. **Resume** (required: no skip option)
   *Why:* every posting's required qualifications are checked against it, and
   /apply only claims experience that appears here.
   Accept PDF, DOCX, MD or TXT, or pasted text.

2. **LinkedIn profile PDF**: on LinkedIn, go to your profile → **Resources →
   Save to PDF**.
   *Why:* it fills gaps your resume leaves out (older roles, projects,
   skills). *Skipping:* matches are judged on the resume alone.

3. **Other versions of your resume** (if you target more than one kind of role)
   *Why:* each version shows how you pitch yourself for a different role
   family. *Skipping:* roles outside your main resume's framing score lower.

4. **Job descriptions you liked, or got interviews for** (files, links or pasted text)
   *Why:* they're the clearest signal of what you're a fit for, and the
   researcher looks for more like them. *Skipping:* the research relies only
   on your company list.

5. **Target companies, or an old job-tracking spreadsheet**
   *Why:* it seeds the company list and tracker, so nothing you already know
   about is lost. *Skipping:* the first search starts from your interviews alone.
   Ways to answer:
   - drag in a file (CSV, XLSX), or paste a Google Sheets link (read it with
     the Drive connector)
   - type the companies straight into the chat
   - **"Create a sheet for me to fill in"**:
     - **If the Google Drive connector is already connected** (its tools,
       e.g. `create_file`, are available): create a Google Sheet titled
       "Job Hunt – Target companies" using `create_file` with
       `contentMimeType: text/csv` and `textContent:
       "Company,Website,Roles of interest,Why I'm interested,Notes\n"`. That
       converts it to a native Sheet. Give the user the link, and wait until
       they say they're done. Then read it back with the Drive connector.
     - **Otherwise:** write `profile/uploads/target-companies.csv` with the
       same header, open it (`open profile/uploads/target-companies.csv`),
       and wait until the user says they've saved it.

     Don't connect the Drive connector here just for this. That happens in
     Step 4.

6. **Brag doc, performance reviews, or portfolio**
   *Why:* they give /apply real proof points (results, praise, projects) for
   application answers. *Skipping:* answers rely on resume bullets only.

### Reading the files

- PDF / images / text: use the Read tool.
- DOCX: `uv run --with python-docx python -c "import docx,sys; print('\n'.join(p.text for p in docx.Document(sys.argv[1]).paragraphs))" FILE`
- XLSX / CSV: `uv run --with openpyxl python -c ...`, or read the CSV directly.

### Writing resume.md

Write `profile/resume.md`: a faithful, complete text version (roles, dates,
bullets, skills, education). Merge in anything extra from the LinkedIn PDF and
other resume versions, and mark where it came from. **Don't improve, reword or
embellish anything.** It's the factual record the jd-reader checks against.
Save job descriptions to `profile/uploads/` and summarize what they have in
common in `profile/signals.md` for the researcher. Keep target companies for
Step 5, and brag-doc proof points for /apply.

## Step 2: Profile questions

Draft answers from the resume first, then ask the user to **confirm or
correct**. That's faster than asking from scratch. Keep each round short.

**Round 1: Background** → `profile/background.md`, `profile.yaml → level, industries, titles`
1. Which **positions are you qualified for today**? (Draft them from the
   resume: titles held, plus roles whose day-to-day work they've clearly done.)
2. Which **industries do you have significant experience in**? "Significant"
   means real time in the space: you could talk shop with a customer there.
3. Your current **level** and years of experience. Which levels should we
   target? (Usually your current level, maybe one up.)
4. What are you **strongest at**? (3–5 things, with proof.)
5. Tools and technologies you've used for real, and common requirements you
   **don't** have (so we don't chase roles that need them).

**Round 2: Signals** → `profile/signals.md`, companies with relationship `interviewed` / `door_open`
1. Which **companies have interviewed you** in the last ~2 years? For each:
   the role, how far you got, the outcome, and why you seemed like a fit.
   This is the most valuable input: those companies tell us where you
   actually fit.
2. Any companies that passed but asked you to **stay in touch**?
3. If email will **not** be connected: which applications are open right now?
   (Company, role, date applied, status.)

**Round 3: Targets** → `profile/targets.md`, companies with relationship `target`

Before asking, say this plainly (in your own words):

> List companies and positions you're **actually qualified for today**, not
> where you hope to be in a few years. I'll take this list at face value. If
> it's inflated, I'll find you roles you won't get, and the good matches get
> buried. Honest inputs get you better results.

1. Companies you'd love to work at.
2. Positions you're interested in.

Then **reality-check** every target position against the resume. Write a short
table (position / verdict: qualified, stretch, not yet / one-line reason) and
tell the user honestly. Keep stretch positions only if they want them, and say
they'll score lower. Drop "not yet" positions from `titles.include` unless the
user insists.

**Round 4: Logistics** → `profile.yaml → location, comp, search_started`

Use AskUserQuestion for the multiple-choice parts:
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
2. **Service account + key**: walk the user through the Cloud Console steps in
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

## Step 5: Seed the company list

Write the signal, door-open, target and warm-network companies to a JSONL file
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
