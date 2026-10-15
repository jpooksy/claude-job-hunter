# Email setup (Gmail)

Highly recommended, not required. With email connected, Claude can:

- find every application's real status: confirmations, interview invites,
  rejections, and ghosting
- catch rejections hidden as replies inside old recruiter threads
- find applications you forgot to add to the tracker
- find companies that turned you down but said **"stay in touch"**. Those are
  door-open leads, often your warmest opportunities.

## Connect

1. claude.ai → Settings → Connectors → **Gmail** → Connect.
2. Sign Claude Code in with the same claude.ai account (`/login`), then
   restart Claude Code so the connector loads.
3. In `/setup`, Claude runs a test search and sets `email.enabled: true` in
   `profile/profile.yaml`.

## What Claude does and doesn't do

- Reads only job-search messages, company by company (see
  `.claude/agents/inbox-auditor.md`).
- Searches back **12 months at most**. Change `email.history_months` in
  `profile/profile.yaml` if you want more or less.
- Writes tracker changes with the date and a one-line reason, never email
  bodies or recruiters' contact details.
- Can save **drafts** (follow-ups, outreach) when you ask. It never sends.
- You can disconnect at any time in claude.ai → Settings → Connectors.

## Security concerns? Skip it.

Everything else works. Tell Claude about changes as they happen ("Acme
rejected me", "I have a phone screen with Beta on Friday"), and it updates the
tracker for you.

## Other providers

Any email connector or MCP server that can **search** and **read threads**
works. The inbox-auditor's search syntax is Gmail's, so with another provider,
tell Claude which tools to use and it will adapt the queries.
