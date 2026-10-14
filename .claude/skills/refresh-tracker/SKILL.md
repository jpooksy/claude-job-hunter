---
name: refresh-tracker
description: Bring the job tracker up to date. Respects hand edits, re-checks every posting against its job board (live / changed / gone), audits email for application status changes, marks ghosted applications, picks up new roles at known companies, and lists follow-ups. Use when the user runs /refresh-tracker or says "update my tracker", "update the sheet", "check my applications".
---

# Refresh the tracker

Run this once or twice a week. Use today's date for `<date>`.

## 1. Pull and respect hand edits

Connector backend: read the sheet first (CLAUDE.md → Writing the tracker).

```bash
uv run scripts/tracker.py pull
```

Report the user's hand edits in a sentence or two. They're intentional:
plans never overwrite them (see `tracker/locks.json`). "Passed" means the
user chose not to apply. "Closed" means the company closed it.

## 2. Re-check postings

```bash
uv run scripts/ats.py verify
```

GONE rows the user never applied to are deleted. GONE rows they applied to
are kept with a note. CHANGED rows get the new title. Postings that aren't
on a supported board come back UNKNOWN. Spot-check up to ~10 of them with
WebFetch and queue a delete for any that are clearly closed:
`uv run scripts/tracker.py change --id <ID> --delete --note "posting closed (checked careers page)"`
(only for rows with Status "Not Applied").

## 3. Inbox audit (if `email.enabled`)

Launch the **inbox-auditor**: rows file `tracker/snapshot.csv`, since =
`email.last_audit` minus 3 days (or `search_started` if never audited),
output `runs/<date>/inbox-changes.jsonl`. Don't narrow the search to recent
keywords. The agent sweeps **every open application company by company**,
because rejections often arrive as replies in old threads.

If email isn't connected, ask the user whether anything changed: new
applications, interviews, rejections. Queue each with `tracker.py change`.

## 4. New roles at known companies

```bash
uv run scripts/ats.py fetch
uv run scripts/filter.py
```

If there are candidates, run jd-reader agents on the batches (as in
find-jobs step 4) and then `uv run scripts/score.py`. No company research here.
That's /find-jobs.

## 5. Plan → confirm → apply

```bash
uv run scripts/tracker.py plan \
  --verify runs/<date>/verify.jsonl \
  --changes runs/<date>/inbox-changes.jsonl runs/<date>/changes.jsonl \
  --scored runs/<date>/scored.jsonl \
  --ghosted
```

Leave out inputs that don't exist. Show the plan grouped as: status changes
(rejections, interviews, offers), new applications found, ghosted, postings
closed, new roles. Show **skipped** items too. Those are fields the user
edited by hand. Ask about each one ("you have Acme as Applied; an email on
Oct 2 says rejected. Update it?") and, for each yes, queue the change with
`--force` and re-plan. Then `apply`, finish the write (CLAUDE.md → Writing the tracker), and set
`email.last_audit` to today in profile.yaml.

## 6. Report

Short summary plus the tracker link:
- status changes since last refresh
- **follow-ups due**: Applied 7–14 days ago with no reply (offer to draft a
  follow-up with /apply)
- upcoming interviews found in email (company + date only)
- new roles added, top 3 by score
