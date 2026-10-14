# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6", "google-auth>=2.20", "requests>=2.31"]
# ///
"""The job tracker: a Google Sheet or a CSV file, written only through pull -> plan -> apply.

Backends (profile.yaml -> tracker.backend):
  connector  Google Sheet via the claude.ai Google Sheets connector (default; no Cloud Console).
             Claude does the actual reads and writes with the connector, because
             connectors are only available to Claude, not to scripts:
               read:  get_values(<sheet>, "Jobs!A1:Z") -> save the JSON result verbatim
                      to tracker/connector-read.json, then run pull/plan/apply.
               write: `apply` writes tracker/connector-write.json; send its steps with
                      the connector, read the sheet back as above, then `verify-write`.
  sheets     Google Sheet via a service account (advanced; scripts call the Sheets API).
  csv        tracker/jobs.csv (no Google).

  pull                 read the live tracker into tracker/snapshot.csv and report
                       every edit you made by hand since the last apply
  plan [inputs...]     turn new leads / posting checks / status changes into a
                       reviewable plan (runs/<date>/plan.json). Writes nothing.
  apply                write the plan. Aborts if the tracker changed since `plan`.
  change               queue one edit (e.g. mark a role Applied) for the next plan
  exclude              write data/exclude.txt (every company already known)
  init-sheet           format a new Google Sheet (header, filters, dropdowns, colors)
  verify-write         (connector) confirm the sheet now matches what apply intended
  check                confirm the backend is reachable

Hand edits always win: if you changed a field since the last apply, plans skip
that field and say so. Rows you edited (or added yourself) are never deleted
automatically.

Usage examples:
  uv run scripts/tracker.py pull
  uv run scripts/tracker.py plan --scored runs/2026-10-14/scored.jsonl --verify runs/2026-10-14/verify.jsonl
  uv run scripts/tracker.py change --id "ashby:acme:123" --set Status=Applied --set "Category=Applied (waiting)" --note "Applied via referral"
  uv run scripts/tracker.py apply
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import (  # noqa: E402
    ADDED_BY, CATEGORIES, COLUMNS, DATA_DIR, DATE_COLUMNS, LEGACY_SOURCE, STATUSES, TRACKER_DIR,
    load_companies, load_profile, norm_company, read_csv, read_jsonl, run_dir,
    today, write_csv, write_jsonl,
)

SNAPSHOT = TRACKER_DIR / "snapshot.csv"
LAST_WRITTEN = TRACKER_DIR / ".last_written.csv"
LOCKS = TRACKER_DIR / "locks.json"  # fields/rows you edited by hand; kept until you unlock them
CSV_PATH = TRACKER_DIR / "jobs.csv"
CONNECTOR_READ = TRACKER_DIR / "connector-read.json"
CONNECTOR_WRITE = TRACKER_DIR / "connector-write.json"
CONNECTOR_VERIFY = TRACKER_DIR / "connector-verify.json"  # read-back of just the written ranges
PENDING = TRACKER_DIR / ".pending.csv"
TAB = "Jobs"
CHUNK_ROWS = 40

# --- Helpers --------------------------------------------------------------


def norm_date(v: str) -> str:
    v = (v or "").strip()
    if not v:
        return ""
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d", "%b %d, %Y", "%d %b %Y"):
        try:
            return dt.datetime.strptime(v, fmt).date().isoformat()
        except ValueError:
            pass
    # No year ("8/12", "Sep 3"): assume the most recent such date that isn't in the future.
    for fmt in ("%m/%d", "%b %d", "%B %d"):
        try:
            d = dt.datetime.strptime(v, fmt).date().replace(year=dt.date.today().year)
        except ValueError:
            continue
        if d > dt.date.today():
            d = d.replace(year=d.year - 1)
        return d.isoformat()
    return v


# Posting URLs on supported boards map to the same IDs ats.py uses, so imported
# or hand-added rows can be re-checked by `ats.py verify`.
_URL_IDS = [
    ("greenhouse", r"(?:job-boards|boards)(?:\.eu)?\.greenhouse\.io/([A-Za-z0-9_-]+)/jobs/(\d+)"),
    ("ashby", r"jobs\.ashbyhq\.com/([A-Za-z0-9_.%-]+)/([0-9a-f-]{36})"),
    ("lever", r"jobs\.lever\.co/([A-Za-z0-9_-]+)/([0-9a-f-]{36})"),
]


def row_id(r: dict) -> str:
    if r.get("ID"):
        return r["ID"]
    for ats, pat in _URL_IDS:
        m = re.search(pat, r.get("URL") or "")
        if m:
            return f"{ats}:{m.group(1)}:{m.group(2)}"
    role = re.sub(r"[^a-z0-9]+", "-", (r.get("Role") or "").lower()).strip("-")
    return f"row:{norm_company(r.get('Company', ''))}:{role or 'company'}"


def clean(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        if not any((v or "").strip() for v in r.values() if isinstance(v, str)):
            continue
        r = {k: ("" if v is None else str(v)) for k, v in r.items()}
        if "Source" in r:  # trackers made before "Added by" existed
            old = r.pop("Source")
            added = LEGACY_SOURCE.get(old.strip().lower(), old)
            if r.get("Fit reasoning", "").strip():  # only Claude's scoring writes this
                added = "Claude"
            r["Added by"] = r.get("Added by") or added
        if not r.get("Added by"):
            r["Added by"] = "You"  # rows typed into the tracker by hand
        for c in DATE_COLUMNS:
            if c in r:
                r[c] = norm_date(r[c])
        r["ID"] = row_id(r)
        out.append(r)
    return out


def digest(rows: list[dict]) -> str:
    return hashlib.sha256(json.dumps(sorted(rows, key=lambda r: r["ID"]), sort_keys=True).encode()).hexdigest()


def sort_rows(rows: list[dict]) -> list[dict]:
    def key(r):
        cat = CATEGORIES.index(r["Category"]) if r.get("Category") in CATEGORIES else len(CATEGORIES)
        try:
            fit = -float(r.get("Fit") or 0)
        except ValueError:
            fit = 0
        return (cat, fit, r.get("Company", "").lower(), r.get("Role", "").lower())
    return sorted(rows, key=key)


def header_for(rows: list[dict], live_header: list[str] | None) -> list[str]:
    """Keep any columns the user added, in their position."""
    header = [("Added by" if h == "Source" else h) for h in (live_header or COLUMNS)]
    for c in COLUMNS:
        if c not in header:
            header.append(c)
    for r in rows:
        for k in r:
            if k not in header:
                header.append(k)
    return header


# --- Backends -------------------------------------------------------------


class CsvBackend:
    name = "csv"

    def read(self) -> tuple[list[dict], list[str] | None]:
        if not CSV_PATH.exists():
            return [], None
        rows = read_csv(CSV_PATH)
        with CSV_PATH.open() as f:
            header = f.readline().strip().split(",")
        return clean(rows), header

    def write(self, rows: list[dict], header: list[str]) -> None:
        write_csv(CSV_PATH, rows, header)

    def where(self) -> str:
        return str(CSV_PATH)


class SheetsBackend:
    name = "sheets"
    API = "https://sheets.googleapis.com/v4/spreadsheets"

    def __init__(self, cfg: dict):
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2 import service_account

        self.sheet_id = cfg.get("sheet_id")
        if not self.sheet_id:
            sys.exit("profile.yaml tracker.sheet_id is empty. Run /setup (Google Sheets step).")
        key = Path(os.path.expanduser(cfg.get("service_account") or
                                      "~/.config/claude-job-hunter/service-account.json"))
        if not key.exists():
            sys.exit(f"Service-account key not found at {key}. See docs/sheets-setup.md.")
        self.creds = service_account.Credentials.from_service_account_file(
            str(key), scopes=["https://www.googleapis.com/auth/spreadsheets"])
        self.s = AuthorizedSession(self.creds)

    def _req(self, method: str, path: str, **kw):
        r = self.s.request(method, f"{self.API}/{self.sheet_id}{path}", timeout=60, **kw)
        if r.status_code == 403:
            sys.exit(f"Google returned 403. Share the sheet with {self.creds.service_account_email} "
                     "as Editor, and make sure the Sheets API is enabled for the key's project.")
        if r.status_code == 404:
            sys.exit("Spreadsheet not found. Check tracker.sheet_id in profile/profile.yaml.")
        r.raise_for_status()
        return r.json()

    def meta(self) -> dict:
        return self._req("GET", "?fields=properties.title,sheets(properties,conditionalFormats)")

    def tab(self) -> dict:
        sheets = self.meta()["sheets"]
        for s in sheets:
            if s["properties"]["title"] == TAB:
                return s
        return sheets[0]  # a brand-new sheet has only "Sheet1" until init-sheet renames it

    def _range(self, a1: str) -> str:
        from urllib.parse import quote
        title = self.tab()["properties"]["title"]
        return quote(f"'{title}'!{a1}", safe="")

    def read(self) -> tuple[list[dict], list[str] | None]:
        data = self._req("GET", f"/values/{self._range('A1:Z')}", params={"valueRenderOption": "FORMATTED_VALUE"})
        values = data.get("values", [])
        if not values:
            return [], None
        header = values[0]
        rows = [{h: (v[i] if i < len(v) else "") for i, h in enumerate(header)} for v in values[1:]]
        return clean(rows), header

    @staticmethod
    def _cell(col: str, v: str):
        if col in DATE_COLUMNS and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v or ""):
            return (dt.date.fromisoformat(v) - dt.date(1899, 12, 30)).days  # Sheets date serial
        if col == "Fit" and re.fullmatch(r"-?\d+(\.\d+)?", v or ""):
            return float(v) if "." in v else int(v)
        return v if v != "" else None  # None leaves the (already cleared) cell alone

    def write(self, rows: list[dict], header: list[str]) -> None:
        values = [header] + [[self._cell(h, r.get(h, "")) for h in header] for r in rows]
        self._req("POST", f"/values/{self._range('A1:Z')}:clear", json={})
        # RAW keeps text like "+1 referral" or "=..." from being parsed as formulas.
        self._req("PUT", f"/values/{self._range('A1')}", params={"valueInputOption": "RAW"},
                  json={"values": values})
        # Re-assert date formatting on the date columns wherever they sit now, so
        # dates always show (and sort) as yyyy-mm-dd rather than serial numbers.
        sid = self.tab()["properties"]["sheetId"]
        reqs = [{"repeatCell": {"range": {"sheetId": sid, "startRowIndex": 1, "startColumnIndex": header.index(c),
                                          "endColumnIndex": header.index(c) + 1},
                                "cell": {"userEnteredFormat": {"numberFormat": {"type": "DATE", "pattern": "yyyy-mm-dd"}}},
                                "fields": "userEnteredFormat.numberFormat"}}
                for c in DATE_COLUMNS if c in header]
        if reqs:
            self._req("POST", ":batchUpdate", json={"requests": reqs})

    def where(self) -> str:
        return f"https://docs.google.com/spreadsheets/d/{self.sheet_id}/edit"

    def init(self) -> None:
        tab = self.tab()
        reqs = init_requests(tab["properties"]["sheetId"], bool(tab.get("conditionalFormats")))
        self._req("POST", ":batchUpdate", json={"requests": reqs})
        rows, header = self.read()
        if not header:
            self.write([], COLUMNS)


def init_requests(sid: int, has_color_rule: bool) -> list[dict]:
    """Formatting for a new tracker sheet. Field masks use comma paths, which both
    the Sheets API and the claude.ai connector accept."""
    col = {c: i for i, c in enumerate(COLUMNS)}
    widths = {"Category": 150, "Fit": 50, "Company": 150, "Role": 280, "Status": 120,
              "Applied": 100, "Comp": 120, "Location": 180, "Added by": 90,
              "Last updated": 105, "URL": 220, "Notes": 360, "Fit reasoning": 360, "ID": 160}

    def rng(c, r0=1):
        return {"sheetId": sid, "startRowIndex": r0, "startColumnIndex": col[c], "endColumnIndex": col[c] + 1}

    def dropdown(c, options):
        return {"setDataValidation": {"range": rng(c), "rule": {
            "condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": o} for o in options]},
            "strict": False, "showCustomUi": True}}}

    reqs = [
        {"updateSheetProperties": {"properties": {"sheetId": sid, "title": TAB,
                                                  "gridProperties": {"frozenRowCount": 1, "frozenColumnCount": 3}},
                                   "fields": "title,gridProperties.frozenRowCount,gridProperties.frozenColumnCount"}},
        {"repeatCell": {"range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1},
                        "cell": {"userEnteredFormat": {"textFormat": {"bold": True},
                                                       "backgroundColor": {"red": 0.93, "green": 0.93, "blue": 0.93}}},
                        "fields": "userEnteredFormat.textFormat,userEnteredFormat.backgroundColor"}},
        dropdown("Category", CATEGORIES),
        dropdown("Status", STATUSES),
        dropdown("Added by", ADDED_BY),
        {"setBasicFilter": {"filter": {"range": {"sheetId": sid, "startRowIndex": 0,
                                                 "startColumnIndex": 0, "endColumnIndex": len(COLUMNS)}}}},
    ]
    for c in DATE_COLUMNS:
        reqs.append({"repeatCell": {"range": rng(c), "cell": {"userEnteredFormat": {
            "numberFormat": {"type": "DATE", "pattern": "yyyy-mm-dd"}}},
            "fields": "userEnteredFormat.numberFormat"}})
    for c in ("Notes", "Fit reasoning"):
        reqs.append({"repeatCell": {"range": rng(c), "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP"}},
                                    "fields": "userEnteredFormat.wrapStrategy"}})
    for c, w in widths.items():
        reqs.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS",
                                                             "startIndex": col[c], "endIndex": col[c] + 1},
                                                   "properties": {"pixelSize": w}, "fields": "pixelSize"}})
    if not has_color_rule:
        reqs.append({"addConditionalFormatRule": {"index": 0, "rule": {
            "ranges": [rng("Fit")],
            "gradientRule": {
                "minpoint": {"type": "NUMBER", "value": "1", "color": {"red": 0.96, "green": 0.6, "blue": 0.6}},
                "midpoint": {"type": "NUMBER", "value": "5", "color": {"red": 1, "green": 0.9, "blue": 0.6}},
                "maxpoint": {"type": "NUMBER", "value": "10", "color": {"red": 0.6, "green": 0.85, "blue": 0.6}}}}}})
    return reqs


def _col_letter(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


class ConnectorBackend:
    """Google Sheet through the claude.ai Sheets connector. The script can't call the
    connector, so reads come from a file Claude saves, and writes go to a file Claude
    sends. `verify-write` then checks the sheet matches."""

    name = "connector"
    MAX_AGE_MIN = 20

    def __init__(self, cfg: dict):
        self.sheet_id = cfg.get("sheet_id")
        if not self.sheet_id:
            sys.exit("profile.yaml tracker.sheet_id is empty. Run /setup (Google Sheets step).")

    def read_instructions(self) -> str:
        return (f'With the Google Sheets connector, call get_values(spreadsheetId="{self.sheet_id}", '
                f'range="{TAB}!A1:Z") and save the JSON result verbatim to {CONNECTOR_READ}, then re-run.')

    def read(self) -> tuple[list[dict], list[str] | None]:
        if not CONNECTOR_READ.exists():
            sys.exit("No fresh copy of the sheet. " + self.read_instructions())
        age = (dt.datetime.now().timestamp() - CONNECTOR_READ.stat().st_mtime) / 60
        if age > self.MAX_AGE_MIN:
            sys.exit(f"The saved copy of the sheet is {age:.0f} minutes old. " + self.read_instructions())
        data = json.loads(CONNECTOR_READ.read_text())
        values = data.get("values", []) if isinstance(data, dict) else data
        if not values:
            return [], None
        header = [str(h) for h in values[0]]
        self._prev = (header, [[str(x) for x in v] for v in values[1:]])  # sheet as it is, in order
        rows = [{h: (str(v[i]) if i < len(v) else "") for i, h in enumerate(header)} for v in values[1:]]
        return clean(rows), header

    @staticmethod
    def _cell(col: str, v: str):
        if col == "Fit" and re.fullmatch(r"-?\d+(\.\d+)?", v or ""):
            return float(v) if "." in v else int(v)
        if col in DATE_COLUMNS or not v:
            return v  # YYYY-MM-DD becomes a real date in the sheet
        # The connector parses input as if typed, so "8/12" or "+1 referral" would turn
        # into a date or a formula. A leading ' keeps it as text (and isn't shown).
        return "'" + v

    def write(self, rows: list[dict], header: list[str]) -> None:
        """Only rows that changed are sent, and nothing is cleared before the new
        values are in place, so an interrupted write never leaves the sheet empty."""
        last_col = _col_letter(len(header))
        plain = [[r.get(h, "") for h in header] for r in rows]
        prev_header, prev = getattr(self, "_prev", (None, None))
        if prev_header == header and prev is not None:
            pad = lambda v: (v + [""] * len(header))[:len(header)]  # noqa: E731
            dirty = [i for i, row in enumerate(plain) if i >= len(prev) or pad(prev[i]) != row]
        else:
            dirty = list(range(-1, len(plain)))  # -1 = the header row; rewrite everything
        # Group changed rows into ranges (bridging gaps of up to 2 unchanged rows).
        groups: list[list[int]] = []
        for i in dirty:
            if groups and i - groups[-1][-1] <= 3 and len(groups[-1]) < CHUNK_ROWS:
                groups[-1].extend(range(groups[-1][-1] + 1, i + 1))
            else:
                groups.append([i])
        steps = []
        for g in groups:
            vals = [header if i == -1 else [self._cell(h, rows[i].get(h, "")) for h in header] for i in g]
            first, last = g[0] + 2, g[-1] + 2  # sheet rows: 1 = header, data starts at 2
            steps.append({"tool": "update_values", "spreadsheetId": self.sheet_id,
                          "range": f"{TAB}!A{first}:{last_col}{last}", "values": vals})
        old_len = len(prev) if prev is not None else None
        if old_len is None or old_len > len(rows):  # clear leftover rows below the new end
            steps.append({"tool": "batch_clear_values", "spreadsheetId": self.sheet_id,
                          "ranges": [f"{TAB}!A{len(rows) + 2}:Z"]})
        CONNECTOR_WRITE.write_text(json.dumps({"spreadsheetId": self.sheet_id, "steps": steps},
                                              indent=1, ensure_ascii=False))
        write_csv(PENDING, rows, header)

    def where(self) -> str:
        return f"https://docs.google.com/spreadsheets/d/{self.sheet_id}/edit"


def backend(prof: dict):
    cfg = prof.get("tracker") or {}
    kind = cfg.get("backend")
    if kind == "connector":
        return ConnectorBackend(cfg)
    if kind == "sheets":
        return SheetsBackend(cfg)
    return CsvBackend()


# --- Diff / protection ----------------------------------------------------


def manual_edits(live: list[dict], last: list[dict]) -> dict:
    """What changed in the live tracker that we didn't write."""
    L, W = {r["ID"]: r for r in live}, {r["ID"]: r for r in last}
    edits = {"added": [i for i in L if i not in W], "removed": [i for i in W if i not in L], "changed": {}}
    for i in L.keys() & W.keys():
        fields = [c for c in set(L[i]) | set(W[i]) if (L[i].get(c) or "") != (W[i].get(c) or "")]
        if fields:
            edits["changed"][i] = sorted(fields)
    return edits


def print_edits(edits: dict, live: list[dict], last: list[dict]) -> None:
    L, W = {r["ID"]: r for r in live}, {r["ID"]: r for r in last}
    n = len(edits["added"]) + len(edits["removed"]) + len(edits["changed"])
    if not last:
        print("No previous write recorded; nothing to compare (first run).")
        return
    if not n:
        print("No hand edits since the last apply.")
        return
    print(f"Hand edits since the last apply ({n} rows). These are treated as intentional:")
    for i in edits["added"]:
        print(f"  + added    {L[i].get('Company')} / {L[i].get('Role')}")
    for i in edits["removed"]:
        print(f"  - removed  {W[i].get('Company')} / {W[i].get('Role')}")
    for i, fields in edits["changed"].items():
        ch = ", ".join(f"{f}: {W[i].get(f, '')!r} -> {L[i].get(f, '')!r}" for f in fields)
        print(f"  ~ changed  {L[i].get('Company')} / {L[i].get('Role')}: {ch}")


def load_locks() -> dict:
    if LOCKS.exists():
        return json.loads(LOCKS.read_text())
    return {"rows": [], "fields": {}}


def update_locks(live: list[dict]) -> dict:
    """Fold any new hand edits into tracker/locks.json and return the locks."""
    locks = load_locks()
    last = clean(read_csv(LAST_WRITTEN))
    if last:
        edits = manual_edits(live, last)
        rows = set(locks["rows"]) | set(edits["added"])
        for i, fields in edits["changed"].items():
            locks["fields"][i] = sorted(set(locks["fields"].get(i, [])) | set(fields) - {"Last updated"})
        live_ids = {r["ID"] for r in live}
        locks["rows"] = sorted(r for r in rows if r in live_ids)
        locks["fields"] = {i: f for i, f in locks["fields"].items() if i in live_ids and f}
        TRACKER_DIR.mkdir(parents=True, exist_ok=True)
        LOCKS.write_text(json.dumps(locks, indent=2))
    return locks


# --- Commands -------------------------------------------------------------


def cmd_check(args):
    prof = load_profile()
    b = backend(prof)
    if isinstance(b, SheetsBackend):
        print(f"Service account: {b.creds.service_account_email}")
        print(f"Sheet title:     {b.meta()['properties']['title']}")
    if isinstance(b, ConnectorBackend) and not CONNECTOR_READ.exists():
        print(f"Connector backend for {b.where()}\n" + b.read_instructions())
        return
    rows, _ = b.read()
    print(f"OK: {b.name} backend, {len(rows)} rows at {b.where()}")


def cmd_init_sheet(args):
    prof = load_profile()
    b = backend(prof)
    if isinstance(b, ConnectorBackend):
        path = TRACKER_DIR / "connector-init.json"
        TRACKER_DIR.mkdir(parents=True, exist_ok=True)
        steps = [
            {"tool": "update_spreadsheet", "spreadsheetId": b.sheet_id,
             "requests": init_requests(args.sheet_gid, False)},
            {"tool": "update_values", "spreadsheetId": b.sheet_id,
             "range": f"{TAB}!A1:{_col_letter(len(COLUMNS))}1", "values": [COLUMNS]},
        ]
        path.write_text(json.dumps({"spreadsheetId": b.sheet_id, "steps": steps}, indent=1))
        print(f"Send the steps in {path} with the Google Sheets connector, in order "
              f"(sheet tab id {args.sheet_gid}; check it with get_spreadsheet if unsure).\n"
              f"Then give the user this link in the chat: {b.where()}")
        return
    if not isinstance(b, SheetsBackend):
        sys.exit("tracker.backend is not 'sheets' or 'connector' in profile/profile.yaml.")
    b.init()
    print(f"Formatted {b.where()}")


def cmd_pull(args):
    prof = load_profile()
    b = backend(prof)
    live, header = b.read()
    TRACKER_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(SNAPSHOT, live, header_for(live, header))
    last = clean(read_csv(LAST_WRITTEN))
    print(f"Pulled {len(live)} rows from {b.where()} -> {SNAPSHOT}")
    print_edits(manual_edits(live, last), live, last)
    locks = update_locks(live)
    n = len(locks["rows"]) + len(locks["fields"])
    if n:
        print(f"{n} rows have hand-edited fields that plans won't overwrite (tracker/locks.json).")


def cmd_change(args):
    op: dict = {"op": "update", "id": args.id}
    if args.delete:
        op = {"op": "delete", "id": args.id, "reason": args.note or "removed by request"}
    else:
        op["set"] = dict(s.split("=", 1) for s in args.set or [])
        if args.note:
            op["append_notes"] = args.note
        if args.force:
            op["force"] = True
    path = run_dir() / "changes.jsonl"
    write_jsonl(path, [op], append=True)
    print(f"Queued {op} -> {path}")


def ops_from_verify(rows: list[dict], live_by_id: dict) -> list[dict]:
    ops = []
    for v in rows:
        r = live_by_id.get(v["id"])
        if not r:
            continue
        if v["state"] == "GONE":
            if r.get("Status") in ("", "Not Applied") and r.get("Category") in ("To apply", "Watchlist", "Passed"):
                ops.append({"op": "delete", "id": v["id"], "reason": f"posting gone ({v['detail']})"})
            else:
                ops.append({"op": "update", "id": v["id"], "append_notes": "Posting taken down"})
        elif v["state"] == "CHANGED":
            new = v["detail"].removeprefix("title now: ")
            ops.append({"op": "update", "id": v["id"], "set": {"Role": new},
                        "append_notes": f"Title changed from {r.get('Role')!r}"})
    return ops


def ops_ghosted(live: list[dict], days: int) -> list[dict]:
    cutoff = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    ops = []
    for r in live:
        if r.get("Status") != "Applied":
            continue
        applied, updated = r.get("Applied") or "", r.get("Last updated") or ""
        if applied and applied <= cutoff and (not updated or updated <= cutoff):
            ops.append({"op": "update", "id": r["ID"], "set": {"Status": "Ghosted"},
                        "append_notes": f"No reply {days}+ days after applying"})
    return ops


def cmd_plan(args):
    prof = load_profile()
    b = backend(prof)
    live, header = b.read()
    locks = update_locks(live)
    edited_fields = {i: set(f) for i, f in locks["fields"].items()}
    protected_rows = set(locks["rows"]) | set(edited_fields)
    live_by_id = {r["ID"]: r for r in live}
    by_name = {(norm_company(r.get("Company", "")), (r.get("Role") or "").strip().lower()): r["ID"] for r in live}

    ops: list[dict] = []
    for p in args.scored or []:
        ops += [{"op": "add", "row": r} for r in read_jsonl(Path(p))]
    for p in args.changes or []:
        ops += read_jsonl(Path(p))
    if args.verify:
        ops += ops_from_verify(read_jsonl(Path(args.verify)), live_by_id)
    stalled = []
    if args.ghosted:
        days = (prof.get("tracker") or {}).get("ghosted_after_days", 30)
        ops += ops_ghosted(live, days)
        cutoff = (dt.date.today() - dt.timedelta(days=days)).isoformat()
        stalled = [r for r in live if r.get("Status") in ("Interviewing", "In Conversation")
                   and (r.get("Last updated") or "") <= cutoff]

    planned, skipped = [], []
    for op in ops:
        kind = op.get("op")
        if kind == "add":
            row = {k: ("" if v is None else str(v)) for k, v in op["row"].items()}
            if not row.get("Last updated"):
                row["Last updated"] = today()
            cleaned = clean([row])  # normalize dates, map old "Source" values, assign the ID
            if not cleaned:
                skipped.append({**op, "why": "empty row"})
                continue
            row = cleaned[0]
            key = (norm_company(row.get("Company", "")), (row.get("Role") or "").strip().lower())
            if row["ID"] in live_by_id or key in by_name:
                skipped.append({**op, "why": "already in tracker"})
                continue
            planned.append({"op": "add", "row": row, "lock": op.get("lock") or []})
            live_by_id[row["ID"]] = row
            by_name[key] = row["ID"]
        elif kind == "update":
            rid = op.get("id")
            if rid not in live_by_id:
                skipped.append({**op, "why": "no such row"})
                continue
            sets, blocked = {}, {}
            for f, v in (op.get("set") or {}).items():
                if f in edited_fields.get(rid, set()) and not op.get("force"):
                    blocked[f] = v
                elif (live_by_id[rid].get(f) or "") != str(v):
                    sets[f] = str(v)
            if blocked:
                skipped.append({"op": "update", "id": rid, "set": blocked, "why": "you edited these fields by hand"})
            if sets or op.get("append_notes"):
                planned.append({"op": "update", "id": rid, "set": sets, "append_notes": op.get("append_notes"),
                                "force": bool(op.get("force"))})
        elif kind == "delete":
            rid = op.get("id")
            if rid not in live_by_id:
                continue
            if rid in protected_rows and not op.get("force"):
                skipped.append({**op, "why": "you added or edited this row by hand"})
                continue
            planned.append(op)
        else:
            skipped.append({**op, "why": f"unknown op {kind!r}"})

    plan = {"created": dt.datetime.now().isoformat(timespec="seconds"), "backend": b.name,
            "based_on": digest(live), "ops": planned, "skipped": skipped,
            "consumes": [str(p) for p in args.changes or [] if Path(p).exists()]}
    path = run_dir() / "plan.json"
    path.write_text(json.dumps(plan, indent=2, ensure_ascii=False))

    adds = [o for o in planned if o["op"] == "add"]
    upds = [o for o in planned if o["op"] == "update"]
    dels = [o for o in planned if o["op"] == "delete"]
    lb = {r["ID"]: r for r in live} | {o["row"]["ID"]: o["row"] for o in planned if o["op"] == "add"}
    print(f"Plan -> {path}\n  {len(adds)} add, {len(upds)} update, {len(dels)} delete, {len(skipped)} skipped")
    for o in adds[: args.show]:
        r = o["row"]
        print(f"  + {r.get('Fit', ''):>2} {r.get('Company')} / {r.get('Role')}  ({r.get('Category')})")
    if len(adds) > args.show:
        print(f"    ... {len(adds) - args.show} more adds")
    for o in upds:
        r = lb.get(o["id"], {})
        bits = [f"{k}={v!r}" for k, v in o["set"].items()] + ([f"note: {o['append_notes']}"] if o.get("append_notes") else [])
        print(f"  ~ {r.get('Company')} / {r.get('Role')}: {', '.join(bits)}")
    for o in dels:
        r = lb.get(o["id"], {})
        print(f"  - {r.get('Company')} / {r.get('Role')}: {o.get('reason', '')}")
    for s in skipped:
        r = lb.get(s.get("id") or "", {}) or s.get("row", {})
        print(f"  ! skipped {r.get('Company', s.get('id'))} / {r.get('Role', '')}: {s['why']}")
    for r in stalled:
        print(f"  ? likely stalled (no activity since {r.get('Last updated') or '?'}): "
              f"{r.get('Company')} / {r.get('Role')}. Ask the user; don't change it automatically")


def cmd_apply(args):
    prof = load_profile()
    b = backend(prof)
    path = Path(args.plan) if args.plan else run_dir() / "plan.json"
    if not path.exists():
        sys.exit(f"No plan at {path}. Run `tracker.py plan` first.")
    plan = json.loads(path.read_text())
    live, header = b.read()
    if digest(live) != plan["based_on"]:
        sys.exit("The tracker changed after this plan was made (probably a hand edit). "
                 "Re-run `tracker.py pull` and `tracker.py plan`, then apply.")

    TRACKER_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(TRACKER_DIR / f"backup-{dt.datetime.now():%Y%m%d-%H%M%S}.csv", live, header_for(live, header))
    for old in sorted(TRACKER_DIR.glob("backup-*.csv"))[:-20]:
        old.unlink()

    rows = {r["ID"]: dict(r) for r in live}
    order = [r["ID"] for r in live]
    locks = load_locks()
    for op in plan["ops"]:
        if op["op"] == "add":
            rows[op["row"]["ID"]] = op["row"]
            order.append(op["row"]["ID"])
            if op.get("lock"):  # e.g. a Fit the user scored in their old tracker
                locks["fields"][op["row"]["ID"]] = sorted(op["lock"])
        elif op["op"] == "update" and op["id"] in rows:
            r = rows[op["id"]]
            r.update(op.get("set") or {})
            if op.get("append_notes"):
                line = f"{today()}: {op['append_notes']}"
                r["Notes"] = f"{r['Notes']}\n{line}" if r.get("Notes") else line
            r["Last updated"] = today()
            if op.get("force"):  # you asked for this change, so the field is no longer a hand edit
                left = set(locks["fields"].get(op["id"], [])) - set(op.get("set") or {})
                locks["fields"][op["id"]] = sorted(left)
        elif op["op"] == "delete":
            rows.pop(op["id"], None)
    out = [rows[i] for i in order if i in rows]
    # A Google Sheet via the connector keeps its own row order (new rows go at the
    # end; sort with the sheet's filter), so a write only touches changed rows.
    if (prof.get("tracker") or {}).get("sort", True) and not isinstance(b, ConnectorBackend):
        out = sort_rows(out)
    hdr = header_for(out, header)
    b.write(out, hdr)
    if isinstance(b, ConnectorBackend):
        LOCKS.write_text(json.dumps(locks, indent=2))
        path.rename(path.with_suffix(".pending.json"))
        steps = json.loads(CONNECTOR_WRITE.read_text())["steps"]
        n = len(steps)
        if not steps:
            print("Nothing changed in the sheet.")
        ranges = [st["range"] for st in steps if st["tool"] == "update_values"]
        print(f"Planned {len(plan['ops'])} ops ({len(out)} rows). Now, with the Google Sheets connector:\n"
              f"  1. send the {n} steps in {CONNECTOR_WRITE} in order, copying each step's fields verbatim\n"
              f"  2. read back only what you wrote: get_values for each of {ranges}, and save the\n"
              f"     results as a JSON list, verbatim, to {CONNECTOR_VERIFY}\n"
              f"  3. run: uv run scripts/tracker.py verify-write")
        return
    finalize(b, plan, path, hdr, locks)


def finalize(b, plan: dict, path: Path, hdr: list[str], locks: dict, after: list[dict] | None = None) -> None:
    if after is None:
        after, _ = b.read()  # read back so dates/numbers match what the backend stores
    write_csv(LAST_WRITTEN, after, hdr)
    write_csv(SNAPSHOT, after, hdr)
    PENDING.unlink(missing_ok=True)
    if b.name == "connector":
        CONNECTOR_READ.unlink(missing_ok=True)  # it shows the sheet before this write; force a fresh read
    locks["fields"] = {i: f for i, f in locks["fields"].items() if f}
    LOCKS.write_text(json.dumps(locks, indent=2))
    if b.name in ("sheets", "connector"):
        write_csv(CSV_PATH, after, hdr)  # local copy for agents to read
    path.rename(path.with_name("plan.applied.json"))
    # Change files are one-shot: rename them so a later plan doesn't replay their notes.
    for c in plan.get("consumes", []):
        cp = Path(c)
        if cp.exists():
            cp.rename(cp.with_name(f"{cp.stem}.applied-{dt.datetime.now():%H%M%S}.jsonl"))
    print(f"Applied {len(plan.get('ops', []))} ops. {len(after)} rows.\nTracker: {b.where()}")


def verify_ranges(b, pending_plan: Path):
    """Check just the written ranges. The rest of the sheet was verified when it was
    read before apply (and apply refuses to run on a changed sheet)."""
    steps = [st for st in json.loads(CONNECTOR_WRITE.read_text())["steps"] if st["tool"] == "update_values"]
    data = json.loads(CONNECTOR_VERIFY.read_text())
    reads = data if isinstance(data, list) else [data]
    if len(reads) != len(steps):
        sys.exit(f"Expected {len(steps)} read-backs in {CONNECTOR_VERIFY}, found {len(reads)}.")
    norm = lambda v: str(v)[1:] if isinstance(v, str) and v.startswith("'") else str(v)  # noqa: E731
    problems = []
    for st, rd in zip(steps, reads):
        got = (rd or {}).get("values", [])
        for i, row in enumerate(st["values"]):
            have = [str(x) for x in (got[i] if i < len(got) else [])]
            have += [""] * (len(row) - len(have))
            for j, cell in enumerate(row):
                if norm(cell).strip() != have[j].strip():
                    problems.append(f"{st['range']} row {i + 1}, column {j + 1}: "
                                    f"sheet has {have[j]!r}, expected {norm(cell)!r}")
    if problems:
        print(f"The sheet doesn't match what was sent ({len(problems)} cells):")
        for p_ in problems[:30]:
            print("  " + p_)
        sys.exit(f"Re-send the steps in {CONNECTOR_WRITE} (they're unchanged), read them back, and verify again.")
    pending = clean(read_csv(PENDING))
    import csv as _csv
    with PENDING.open(newline="", encoding="utf-8") as f:
        hdr = next(_csv.reader(f), None) or COLUMNS
    finalize(b, json.loads(pending_plan.read_text()), pending_plan, hdr, load_locks(), after=pending)
    CONNECTOR_VERIFY.unlink(missing_ok=True)


def cmd_verify_write(args):
    prof = load_profile()
    b = backend(prof)
    if not isinstance(b, ConnectorBackend):
        sys.exit("verify-write is only for the connector backend.")
    pending_plan = run_dir() / "plan.pending.json"
    if not PENDING.exists() or not pending_plan.exists():
        sys.exit("Nothing waiting to be verified. Run `tracker.py apply` first.")
    if CONNECTOR_VERIFY.exists() and CONNECTOR_VERIFY.stat().st_mtime >= CONNECTOR_WRITE.stat().st_mtime:
        return verify_ranges(b, pending_plan)
    want = {r["ID"]: r for r in clean(read_csv(PENDING))}
    got_rows, hdr = b.read()
    got = {r["ID"]: r for r in got_rows}
    problems = [f"missing row: {w.get('Company')} / {w.get('Role')}" for i, w in want.items() if i not in got]
    problems += [f"unexpected row: {g.get('Company')} / {g.get('Role')}" for i, g in got.items() if i not in want]
    for i in want.keys() & got.keys():
        for c in COLUMNS:
            if (want[i].get(c) or "").strip() != (got[i].get(c) or "").strip():
                problems.append(f"{want[i].get('Company')} / {want[i].get('Role')}: {c} is "
                                f"{got[i].get(c)!r}, expected {want[i].get(c)!r}")
    if problems:
        print(f"The sheet doesn't match the plan ({len(problems)} differences):")
        for p_ in problems[:30]:
            print("  " + p_)
        sys.exit(f"Re-send the steps in {CONNECTOR_WRITE} (they're unchanged), read the sheet back, "
                 "and run verify-write again.")
    finalize(b, json.loads(pending_plan.read_text()), pending_plan, hdr or COLUMNS, load_locks())


def cmd_exclude(args):
    names = {r["Company"] for r in read_csv(SNAPSHOT) if r.get("Company")}
    names |= {r["company"] for r in load_companies()}
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / "exclude.txt"
    path.write_text("\n".join(sorted(names, key=str.lower)) + "\n")
    print(f"{len(names)} companies -> {path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    ini = sub.add_parser("init-sheet")
    ini.add_argument("--sheet-gid", type=int, default=0, help="(connector) the tab's sheetId; a new sheet's is 0")
    sub.add_parser("verify-write")
    sub.add_parser("pull")
    p = sub.add_parser("plan")
    p.add_argument("--scored", nargs="*", help="scored.jsonl files from score.py")
    p.add_argument("--changes", nargs="*", help="changes.jsonl files (add/update/delete ops)")
    p.add_argument("--verify", help="verify.jsonl from ats.py verify")
    p.add_argument("--ghosted", action="store_true", help="mark stale applications Ghosted")
    p.add_argument("--show", type=int, default=40)
    a = sub.add_parser("apply")
    a.add_argument("--plan")
    c = sub.add_parser("change")
    c.add_argument("--id", required=True)
    c.add_argument("--set", action="append", help="Field=Value (repeatable)")
    c.add_argument("--note")
    c.add_argument("--delete", action="store_true")
    c.add_argument("--force", action="store_true", help="override a field you edited by hand")
    sub.add_parser("exclude")
    args = ap.parse_args()
    {"check": cmd_check, "init-sheet": cmd_init_sheet, "pull": cmd_pull, "plan": cmd_plan,
     "apply": cmd_apply, "change": cmd_change, "exclude": cmd_exclude,
     "verify-write": cmd_verify_write}[args.cmd](args)


if __name__ == "__main__":
    main()
