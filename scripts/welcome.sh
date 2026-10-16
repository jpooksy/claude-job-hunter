#!/bin/sh
# SessionStart hook. Fresh copy (no profile): welcome + point to /setup.
# Setup started but not finished (runs/setup/state.json says so): offer to resume.
# Otherwise: print nothing.
dir="${CLAUDE_PROJECT_DIR:-.}"
state="$dir/runs/setup/state.json"
if [ ! -f "$dir/profile/profile.yaml" ]; then
cat <<'JSON'
{"systemMessage": "👋 Welcome to claude-job-hunter! New here? Type /setup to get started (about 25 minutes).",
 "hookSpecificOutput": {"hookEventName": "SessionStart",
  "additionalContext": "This is a fresh copy of claude-job-hunter: profile/profile.yaml doesn't exist yet. Whatever the user's first message is, start your reply by welcoming them in one or two sentences and telling them to type /setup to get started (about 25 minutes; it builds their profile and tracker, then /find-jobs finds roles). If they ask what this is, explain briefly first."}}
JSON
  exit 0
fi
[ -f "$state" ] || exit 0
next=$(sed -n 's/.*"next"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$state" | head -1)
[ -z "$next" ] || [ "$next" = "done" ] && exit 0
cat <<JSON
{"systemMessage": "👋 Welcome back! Setup isn't finished yet. Type /setup to pick up where you left off (next: $next).",
 "hookSpecificOutput": {"hookEventName": "SessionStart",
  "additionalContext": "The user started /setup but didn't finish (runs/setup/state.json: next = $next). Whatever their first message is, start by offering to pick up setup where they left off, in one sentence, unless they're clearly asking for something else."}}
JSON
