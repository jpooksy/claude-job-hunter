# Google Sheets setup

The tracker works as a local CSV, but a Google Sheet is better: it **updates
automatically** every time Claude applies a change, you can open it anywhere
(including your phone), and it has filters, dropdowns, and color-coded fit
scores. You can edit it by hand, and Claude keeps your edits.

The `/setup` skill walks you through this. These are the same steps, for
reference.

## How it works

- Claude **creates** the sheet in *your* Google Drive through the claude.ai
  **Google Drive connector**, and shares it with a service account.
- `scripts/tracker.py` **reads and writes** cells as that **service account**,
  a robot Google identity that can only open spreadsheets you explicitly share
  with it. It can't see anything else in your Drive.
- Why not let the service account create the sheet? Service accounts no longer
  get Drive storage, so creating a file fails with "storage quota exceeded".
  The file has to be owned by you.

Takes about 10 minutes. It's free and needs no billing account.

## 1. Connect Google Drive in claude.ai

claude.ai → Settings → Connectors → **Google Drive** → Connect. Claude Code
must be signed in with the same claude.ai account (`/login`). Restart Claude
Code afterwards so the connector loads.

## 2. Create a service account and key

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
   mkdir -p ~/.config/claude-job-hunter
   mv ~/Downloads/job-hunter-*.json ~/.config/claude-job-hunter/service-account.json
   chmod 600 ~/.config/claude-job-hunter/service-account.json
   ```

Treat the key like a password: never commit it or paste it into chat.
`.gitignore` blocks `service-account*.json` as a safety net.

<details><summary>Prefer the command line? (gcloud)</summary>

```bash
gcloud projects create job-hunter-$RANDOM --set-as-default
gcloud services enable sheets.googleapis.com
gcloud iam service-accounts create job-hunter-sheets
SA=$(gcloud iam service-accounts list --filter=name:job-hunter-sheets --format='value(email)')
gcloud iam service-accounts keys create ~/.config/claude-job-hunter/service-account.json --iam-account "$SA"
chmod 600 ~/.config/claude-job-hunter/service-account.json
```
</details>

## 3. Create and share the sheet

Claude does this in `/setup`: creates "Job Hunt Tracker" in your Drive and
shares it with the service account's `client_email` as **Editor**.

Doing it by hand: open https://sheets.new, name it, click **Share**, paste the
`client_email` from the key file, choose Editor, and uncheck "Notify". Copy the
URL. The ID is the long string between `/d/` and `/edit`.

## 4. Point the tracker at it

In `profile/profile.yaml`:

```yaml
tracker:
  backend: sheets
  sheet_id: "<the ID>"
  service_account: ~/.config/claude-job-hunter/service-account.json
```

Then:

```bash
uv run scripts/tracker.py check       # prints the service-account email and sheet title
uv run scripts/tracker.py init-sheet  # header, frozen columns, filters, dropdowns, colors
```

## Troubleshooting

| Error | Fix |
|-------|-----|
| 403 | The sheet isn't shared with the service account's `client_email` as Editor, or the Sheets API isn't enabled in the key's project |
| 404 / "Spreadsheet not found" | Wrong `sheet_id` |
| "Service-account key not found" | Check `tracker.service_account` path |
| It's an `.xlsx` in Drive | Must be a native Google Sheet. File → Save as Google Sheets, and use the new ID |
| "Service account key creation is disabled" | Your org blocks keys. Use a personal Google account |

To revoke access at any time: Cloud Console → Service accounts → Keys → delete
the key, or remove the service account from the sheet's Share list.

## Switching from CSV later

Run `/setup Google Sheets`. After the sheet is set up, Claude copies your
existing `tracker/jobs.csv` rows into it (pull → plan → apply).
