# Google Sheets setup

The tracker works as a local CSV, but a Google Sheet is better: it **updates
automatically** whenever Claude changes it, you can open it anywhere
(including your phone), and it has filters, dropdowns, and color-coded fit
scores. You can edit it by hand, and Claude keeps your edits.

The `/setup` skill does all of this for you. This page is for reference.

## Recommended: the claude.ai Google Sheets connector

No Google Cloud setup, no keys, nothing to install.

1. claude.ai → Settings → Connectors → connect **Google Sheets** and
   **Google Drive** with your Google account.
2. Claude Code must be signed in with the same claude.ai account (`/login`).
   If you connected them while Claude Code was open, restart it and pick up
   where you left off with `claude --continue`.
3. In `/setup`, Claude creates a sheet called "Job Hunt Tracker" in your Drive
   and formats it.

What happens behind the scenes: scripts can't use connectors, so Claude does
the reading and writing. `tracker.py` still decides exactly what goes in the
sheet. Claude sends those values through the connector, reads the sheet back,
and `tracker.py verify-write` confirms the sheet matches before anything else
happens (see CLAUDE.md → Writing the tracker).

**Access:** the connector uses your Google account, so it can open any sheet
you can. Claude only touches the tracker. Disconnect any time in claude.ai →
Settings → Connectors.

**Limits:** the connector is in beta and needs a paid Claude plan. Some
company Google accounts block it. If it isn't available to you, use the
service account below, or a CSV.

## Advanced: your own service account

For people who already have a Google Cloud service account, or have very
large trackers. `tracker.py` then talks to the Sheets API directly, with no
connector involved. Setup takes about 15 minutes in the Google Cloud Console.

Why does the sheet still get created by you? Service accounts no longer get
Drive storage, so they can't create files ("storage quota exceeded"). The file
has to be owned by you and shared with the service account.

### Create a service account and key

Use a **personal** Google account. Company Google Workspace accounts often
block service-account keys (error: "Service account key creation is disabled").

1. Open https://console.cloud.google.com/ → project picker (top left) →
   **New project** → name it `job-hunter` → Create. Make sure it's selected.
2. **Enable the Sheets API**: https://console.cloud.google.com/apis/library/sheets.googleapis.com → Enable.
3. **Create the service account**: https://console.cloud.google.com/iam-admin/serviceaccounts →
   **Create service account** → name `job-hunter-sheets` → Create and continue →
   skip the optional role and user steps → **Done**.
4. **Create a key**: click the new service account → **Keys** tab → Add key →
   Create new key → **JSON** → Create. A `.json` file downloads.
5. Move it into place (in a terminal, or type `! ` before the command in Claude Code):
   ```bash
   mkdir -p ~/.config/lookalike-job-hunter
   mv ~/Downloads/job-hunter-*.json ~/.config/lookalike-job-hunter/service-account.json
   chmod 600 ~/.config/lookalike-job-hunter/service-account.json
   ```

Treat the key like a password: never commit it or paste it into chat.
`.gitignore` blocks `service-account*.json` as a safety net.

<details><summary>Prefer the command line? (gcloud)</summary>

```bash
gcloud projects create job-hunter-$RANDOM --set-as-default
gcloud services enable sheets.googleapis.com
gcloud iam service-accounts create job-hunter-sheets
SA=$(gcloud iam service-accounts list --filter=name:job-hunter-sheets --format='value(email)')
gcloud iam service-accounts keys create ~/.config/lookalike-job-hunter/service-account.json --iam-account "$SA"
chmod 600 ~/.config/lookalike-job-hunter/service-account.json
```
</details>

### Share the sheet with it

Claude does this in `/setup`: creates "Job Hunt Tracker" in your Drive and
shares it with the service account's `client_email` as **Editor**.

Doing it by hand: open https://sheets.new, name it, click **Share**, paste the
`client_email` from the key file, choose Editor, and uncheck "Notify". Copy the
URL. The ID is the long string between `/d/` and `/edit`.

### Point the tracker at it

In `profile/profile.yaml`:

```yaml
tracker:
  backend: sheets   # (the connector option uses: backend: connector)
  sheet_id: "<the ID>"
  service_account: ~/.config/lookalike-job-hunter/service-account.json
```

Then:

```bash
uv run scripts/tracker.py check       # prints the service-account email and sheet title
uv run scripts/tracker.py init-sheet  # header, frozen columns, filters, dropdowns, colors
```

### Troubleshooting

| Error | Fix |
|-------|-----|
| 403 | The sheet isn't shared with the service account's `client_email` as Editor, or the Sheets API isn't enabled in the key's project |
| 404 / "Spreadsheet not found" | Wrong `sheet_id` |
| "Service-account key not found" | Check `tracker.service_account` path |
| It's an `.xlsx` in Drive | Must be a native Google Sheet. File → Save as Google Sheets, and use the new ID |
| "Service account key creation is disabled" | Your org blocks keys. Use a personal Google account |

To revoke access at any time: Cloud Console → Service accounts → Keys → delete
the key, or remove the service account from the sheet's Share list.

## Switching later

Run `/setup Google Sheets`. After the new sheet is set up, Claude copies your
existing rows into it (pull → plan → apply).
