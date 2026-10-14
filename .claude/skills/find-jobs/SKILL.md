---
name: find-jobs
description: Find new roles that fit the user. Researches companies similar to their signal companies, pulls every job board with scripts, filters cheaply, has jd-reader agents read the survivors against the resume, scores them with the rubric, and adds the results to the tracker after the user confirms. Use when the user runs /find-jobs or asks for new leads, similar companies, or more jobs.
---

# Find jobs

The pipeline keeps LLM work to the parts that need judgment, and runs
independent work **at the same time** instead of one stage after another:

```
                 ┌─ research new companies (agents, ~5 min) ─→ import + detect → fetch --new → filter --append → read → ┐
preflight → fetch known boards → filter → read postings (jd-readers) ──────────────────────────────────────────────────→ score → plan + gut check → apply
                 └─ careers pages of companies without a board (agent) → filter --append → read ────────────────────────┘
```

Everything lands in `runs/<date>/`, so a crashed step can be re-run without
redoing the rest. Use today's date for `<date>`.

Tell the user up front what this does and how long it takes ("I'll look for
companies like the ones that interviewed you and read their open roles against
your resume. About 10–15 minutes. Nothing for you to do until I show you the
results."). Give a one-line status when each stage finishes. Every role found
here is a **recommendation**: it goes in the tracker with **Added by: Claude**,
and only after the user says yes.

**Agents run in the background** (`run_in_background: true`). Launch
independent agents in **one message**, keep working while they run, and pick
up each result when it arrives. Never sit idle waiting for one agent if other
work is ready.

## 0. Preflight

Connector backend: read the sheet first (CLAUDE.md → Writing the tracker).

```bash
test -f profile/profile.yaml || echo "run /setup first"
uv run scripts/tracker.py pull
uv run scripts/tracker.py exclude
```

Mention any hand edits `pull` reports, in one line ("you marked 3 roles
Passed since last time; I'll leave them alone").

If the user only wants **new roles at companies already on the list** ("any
new postings?"), do step 1 only, then steps 4–6.

## 1. Start everything that doesn't depend on research

Do these first, in this order, without waiting in between:

1. **Fetch known boards and filter:**
   ```bash
   uv run scripts/ats.py fetch
   uv run scripts/filter.py
   ```
2. **In one message, launch in the background:**
   - one **jd-reader** per batch printed by filter (batches of 6; up to 10
     readers at a time). Each gets its batch path and output path
     `runs/<date>/extract/<batch-name>.jsonl`.
   - the **company-researchers** (step 2)
   - the **careers-page check** (step 3), if any companies are `no_ats`

## 2. Research new companies (background)

Read `profile/signals.md`, `targets.md`, `background.md` and
`job-sources.md`. Group the signal and target companies into **2–4 themes**
by what they sell and who buys it (e.g. "modern data stack tools sold to
analytics engineers", "developer APIs sold to app developers"). If
job-sources.md lists readable job boards, add a "job boards" theme whose
researcher goes through those boards for companies. **Show the user the themes,
one line each**, in the same message that launches them.

Give each **company-researcher**:
- the theme, plus the signal companies it's based on
- the **other themes' names**, so they don't overlap
- `data/exclude.txt`
- output file `runs/<date>/research/<theme-slug>.jsonl`
- count: 15–25

As soon as a researcher finishes (don't wait for all of them):

```bash
uv run scripts/ats.py import runs/<date>/research/<theme-slug>.jsonl
uv run scripts/ats.py detect
uv run scripts/ats.py fetch --new
uv run scripts/filter.py --append
```

Then launch jd-readers for the **new** batches it prints. Companies found on a
job board come in as `research` (the board isn't a personal connection).

If detect guessed a board wrong and you fix it with `ats.py set`, fetch that
company right away (`uv run scripts/ats.py fetch --company "<name>"`), then
`filter.py --append`. Otherwise its postings are never read.

If an agent produced nothing or died, re-run just that theme.

## 3. Companies without a supported job board (background)

`detect` marks companies with no Greenhouse, Ashby, Lever or Workable board as
`no_ats`. One **general-purpose** agent checks the careers pages of up to ~10 of
them, most promising first (`careers_url`, or the domain + /careers), and looks
for titles matching `profile.yaml → titles.include`. For each match it opens the
posting and appends a line to `runs/<date>/postings-manual.jsonl`:

```json
{"id": "web:<company-slug>:<role-slug>", "company": "...", "title": "...", "url": "<posting URL you opened>", "location": "...", "workplace": "remote|hybrid|onsite|unknown", "comp_min": null, "comp_max": null, "comp_currency": null, "description": "<posting text>"}
```

Only postings it actually opened. Never a URL it didn't visit. When it's done,
run `uv run scripts/filter.py --append` and read the new batch.

## 4. Score

When every batch has its extract file:

```bash
uv run scripts/score.py
```

If it reports postings "not read yet", re-run the jd-reader for the batches
whose extract files are missing or short, then run score.py again. It only
scores what hasn't been scored.

## 5. Plan, with the gut check built in (one approval)

```bash
uv run scripts/tracker.py plan --scored runs/<date>/scored.jsonl
```

Show the user, **in the chat**, using the numbers the scripts printed (never
your own estimates):
- companies researched (new), postings fetched, candidates read, roles to add
- the roles to add, **numbered**: score, company, role, one-line reason
- the main drop reasons, with counts. Call out any dealbreaker that removed a
  lot, in case it's too broad.

Then one ask, which also serves as the gut check:

👉 **Your turn: reply "add them", or give the numbers of any you'd never apply
to, with a word on why (e.g. "3, 7: too senior").**

Turn each "why" into a rule (CLAUDE.md → Feedback → files) **after telling the
user what you'll change**. Drop those rows from scored.jsonl, re-plan, and
apply:

```bash
uv run scripts/tracker.py apply
```

Finish the write (CLAUDE.md → Writing the tracker), then give the tracker link
(sheet URL, or `tracker/jobs.csv`). End with the next step on the last line,
in bold, e.g. 👉 **Your turn: pick any role you like and run /apply for help applying.**

## Rules

- Every row needs a posting URL fetched **in this run**. No URL, no row.
- Don't re-score or edit rows already in the tracker here. That's
  /refresh-tracker's job.
- **Never change the user's profile files without asking.** If filter's
  near-misses suggest widening `titles.include`, propose it ("Should I also
  include 'Customer Engineer'?") and wait for a yes.
- If the user reacts to results ("no crypto", "that's too senior", "score dev
  tools higher"), update the profile files right away (see CLAUDE.md →
  Feedback), then re-run `score.py` / `filter.py` as needed.
- Use `uv run` for every script. Never use plain `python`. Log any script
  problem you work around to `runs/<date>/issues.md`.
