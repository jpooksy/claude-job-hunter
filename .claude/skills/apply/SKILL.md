---
name: apply
description: Help the user apply to a specific role. Writes application answers, a cover letter, resume-tailoring suggestions and outreach or follow-up drafts, all grounded in their real resume and specific to the company. Marks the role Applied once they submit. Use when the user runs /apply, pastes application questions, or asks for help applying, a cover letter, or a recruiter or referral message.
---

# Apply

## 1. Identify the role

Find it in the tracker (`tracker/snapshot.csv`, after `tracker.py pull`) by
company and role, or take a URL the user gives. Get the full posting text:
the batch files in `runs/*/batches/` have it for roles found by the pipeline.
Otherwise, WebFetch the URL.

## 2. Gather context

Read `profile/resume.md`, `profile/background.md`, the row's Notes and Fit
reasoning, and `profile/signals.md` (did they interview here before?). If
`profile/voice.md` exists, match its style. If not, and this is the first
/apply, ask for a short writing sample (an email or post they wrote) and save
a few notes on their voice to `profile/voice.md`.

Ask what they need: answers to application questions (have them paste the
questions), a cover letter, resume tweaks, an outreach note to a recruiter or
hiring manager, a referral ask, or a follow-up.

## 3. Write

Rules, from experience:
- **Specific to this company and role.** Name the product, the buyer, and the
  problem the role solves. Don't reuse a generic answer from another
  application.
- **Grounded in the resume.** Every claim must trace to `resume.md`. Lead with
  the most recent, most relevant role. Never invent metrics, tools or
  projects. If a strong answer needs a fact you don't have, write
  `[CONFIRM: ...]` and ask.
- **Address the gaps honestly.** If the Fit reasoning shows a stretch (missing
  one required item), give the closest real experience. Don't pretend.
- Plain language, the user's voice, no buzzword filler. Respect character
  limits if the form has them.

Save to `drafts/<company>-<role-slug>/` (`answers.md`, `cover-letter.md`,
`outreach.md`). On macOS, offer to copy an answer to the clipboard with
`pbcopy`.

Resume tailoring: suggest which existing bullets to move up or reword for
this posting. Don't add experience that isn't there.

Outreach / follow-ups: short (under ~120 words), one specific reason they're
reaching out to this company, one clear ask. If email is connected, offer to
save it as a **Gmail draft**. Never send email.

## 4. Mark it applied

When the user says they submitted:

```bash
uv run scripts/tracker.py change --id "<ID>" --set Status=Applied --set "Category=Applied (waiting)" --set Applied=<today> --note "Applied (<how: direct / referral from X>)" --force
uv run scripts/tracker.py plan --changes runs/<date>/changes.jsonl
uv run scripts/tracker.py apply
```

`--force` is right here: the user asked for this change, so it overrides an earlier hand edit of the same fields. Show the one-line plan before applying.
