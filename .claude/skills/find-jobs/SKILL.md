---
name: find-jobs
description: Find new roles that fit the user. Researches companies similar to their signal companies, pulls every job board with scripts, filters cheaply, has jd-reader agents read the survivors against the resume, scores them with the rubric, and adds the results to the tracker after the user confirms. Use when the user runs /find-jobs or asks for new leads, similar companies, or more jobs.
---

# Find jobs

The pipeline keeps LLM work to the parts that need judgment:

```
research companies (agents) → import + detect boards (script) → fetch all postings (script)
→ filter (script) → read postings (jd-reader agents) → score (script) → plan → confirm → apply
```

Everything lands in `runs/<date>/`, so a crashed step can be re-run without
redoing the rest. Use today's date for `<date>`.

## 0. Preflight

```bash
test -f profile/profile.yaml || echo "run /setup first"
uv run scripts/tracker.py pull
uv run scripts/tracker.py exclude
```

Mention any hand edits `pull` reports, in one line ("you marked 3 roles
Passed since last time; I'll leave them alone").

If the user only wants **new roles at companies already on the list** ("any
new postings?"), skip to step 3.

## 1. Research new companies

Read `profile/signals.md`, `targets.md`, `background.md` and
`warm-networks.md`. Group the signal and target companies into **2–4 themes**
by what they sell and who buys it (e.g. "modern data stack tools sold to
analytics engineers", "developer APIs sold to app developers"). If
warm-networks.md lists portfolio job boards, add a "warm networks" theme.
Tell the user the themes, one line each.

Launch one **company-researcher** agent per theme, **all in one message** so
they run in parallel. Give each one:
- the theme, plus the signal companies it's based on
- `data/exclude.txt`
- output file `runs/<date>/research/<theme-slug>.jsonl`
- count: 15–25

When they finish:

```bash
uv run scripts/ats.py import runs/<date>/research/*.jsonl
uv run scripts/ats.py detect
```

If an agent produced nothing or died, re-run just that theme.

## 2. Companies without a supported job board

`detect` marks companies with no Greenhouse, Ashby, Lever or Workable board as
`no_ats`. For up to ~10 of them, most promising first, open the careers page
(`careers_url` or the domain + /careers) with WebFetch and look for titles
matching `profile.yaml → titles.include`. For each match, fetch the posting and
append a line to `runs/<date>/postings-manual.jsonl`:

```json
{"id": "web:<company-slug>:<role-slug>", "company": "...", "title": "...", "url": "<posting URL you opened>", "location": "...", "workplace": "remote|hybrid|onsite|unknown", "comp_min": null, "comp_max": null, "comp_currency": null, "description": "<posting text>"}
```

Only add postings you actually opened. Never construct a URL you didn't visit.

## 3. Fetch, filter

```bash
uv run scripts/ats.py fetch
uv run scripts/filter.py
```

`filter.py` prints what it dropped and why. If a big bucket looks wrong (e.g.
"title: not a target title" dropped roles the user would want), fix
`titles.include` in profile.yaml and re-run filter. Mention the fix.

More than ~12 batches (120+ candidates)? Process the 12 batches from the
companies with the strongest relationship first. The rest stay unjudged and
get picked up next run.

## 4. Read the postings

Launch one **jd-reader** per batch file, up to 6 at a time, all in one message.
Each gets its batch path and output path `runs/<date>/extract/<batch-name>.jsonl`.
If there are more batches, run a second wave after the first finishes.

## 5. Score

```bash
uv run scripts/score.py
```

If it reports postings "not read yet", re-run the jd-reader for the batches
whose extract files are missing or short, then run score.py again. It only
scores what hasn't been scored.

## 6. Plan → confirm → apply

```bash
uv run scripts/tracker.py plan --scored runs/<date>/scored.jsonl
```

Show the user:
- how many companies were researched / new, postings fetched, candidates read
- the top roles (score, company, role, one-line reasoning)
- the main drop reasons, with counts. Call out any dealbreaker that removed a
  lot, in case it's too broad.

Ask before applying. Adding everything is the default; the user may want to
skip low scores. To skip a row, remove its line from scored.jsonl and re-plan.
Then:

```bash
uv run scripts/tracker.py apply
```

Give the tracker link (sheet URL, or `tracker/jobs.csv`).

## Rules

- Every row needs a posting URL fetched **in this run**. No URL, no row.
- Don't re-score or edit rows already in the tracker here. That's
  /refresh-tracker's job.
- If the user reacts to results ("no crypto", "that's too senior", "score dev
  tools higher"), update the profile files right away (see CLAUDE.md →
  Feedback), then re-run `score.py` / `filter.py` as needed.
