#!/bin/sh
# SessionStart hook: on a fresh copy (no profile yet), show a welcome line to the
# user (systemMessage) and tell Claude to point them to /setup (additionalContext).
# Prints nothing once setup has been done.
dir="${CLAUDE_PROJECT_DIR:-.}"
[ -f "$dir/profile/profile.yaml" ] && exit 0
cat <<'JSON'
{"systemMessage": "👋 Welcome to claude-job-hunter! New here? Type /setup to get started (about 30–45 minutes).",
 "hookSpecificOutput": {"hookEventName": "SessionStart",
  "additionalContext": "This is a fresh copy of claude-job-hunter: profile/profile.yaml doesn't exist yet. Whatever the user's first message is, start your reply by welcoming them in one or two sentences and telling them to type /setup to get started (about 30–45 minutes; it builds their profile and tracker, then /find-jobs finds roles). If they ask what this is, explain briefly first."}}
JSON
