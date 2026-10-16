"""Shared paths, schema, and helpers for the lookalike-job-hunter scripts.

Every script resolves files relative to a *workspace*: the directory holding
profile/, data/, tracker/ and runs/. It defaults to the repo root. Set
JH_WORKSPACE to point somewhere else (e.g. examples/fictional-persona).
"""

from __future__ import annotations

import csv
import datetime as dt
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WS = Path(os.environ.get("JH_WORKSPACE", REPO)).resolve()
PROFILE_DIR = WS / "profile"
DATA_DIR = WS / "data"
TRACKER_DIR = WS / "tracker"
RUNS_DIR = WS / "runs"
COMPANIES_CSV = DATA_DIR / "companies.csv"
SEEN_JSONL = DATA_DIR / "seen.jsonl"

# --- Tracker schema (one row per role) ------------------------------------

COLUMNS = [
    "Category", "Fit", "Company", "Role", "Status", "Applied", "Comp",
    "Location", "Added by", "Last updated", "URL", "Notes", "Fit reasoning", "ID",
]
DATE_COLUMNS = {"Applied", "Last updated"}

CATEGORIES = [
    "Interviewing", "Applied (waiting)", "Door open (reapply)", "To apply",
    "Watchlist", "Passed", "Closed",
]
STATUSES = [
    "Not Applied", "Applied", "In Conversation", "Interviewing", "Offer",
    "Rejected", "Ghosted", "Hiring Freeze", "Closed",
]
# Who put the row in the tracker. Your relationship with a company (you
# interviewed there, they said stay in touch) lives in Category, Notes and
# Fit reasoning, not here.
ADDED_BY = [
    "You",     # from your own list, or something you told Claude
    "Email",   # found in your inbox (an application, interview or rejection)
    "Claude",  # a role Claude recommends from its job search
]
# Old "Source" values from earlier versions of the template, mapped to Added by.
LEGACY_SOURCE = {
    "my list": "You", "signal company": "You", "door open": "Email", "warm network": "You",
    "inbox": "Email", "applied (gmail)": "Email", "similar company": "Claude",
}

COMPANY_COLUMNS = [
    "company", "domain", "relationship", "ats", "slug", "detect", "careers_url",
    "status", "why", "added",
]
# relationship: interviewed | door_open | warm | target | research
# status: active | no_ats | ignored

# --- Levels ---------------------------------------------------------------

LEVELS = {"entry": 0, "mid": 1, "senior": 2, "manager": 2, "staff": 3,
          "principal": 4, "director": 4, "vp": 5}

_LEVEL_PATTERNS = [
    ("vp", r"\b(vp|vice president|chief)\b"),
    ("director", r"\b(director|head of)\b"),
    ("principal", r"\b(principal|distinguished|fellow)\b"),
    ("staff", r"\b(staff|lead)\b"),
    ("manager", r"\bmanager\b"),
    ("senior", r"\b(senior|sr\.?|iii|level 3)\b"),
    ("entry", r"\b(junior|jr\.?|associate|entry|new grad|graduate|intern)\b"),
]


def level_from_title(title: str) -> str:
    t = title.lower()
    for level, pat in _LEVEL_PATTERNS:
        if re.search(pat, t):
            # "Account Manager" / "Product Manager" are IC titles, not people managers.
            if level == "manager" and re.search(
                    r"(account|product|program|project|success|partner|marketing|"
                    r"community|solutions?|engagement|relationship|territory)\s+manager", t):
                continue
            return level
    return "mid"


# --- Small utilities ------------------------------------------------------


def today() -> str:
    return dt.date.today().isoformat()


def run_dir(date: str | None = None) -> Path:
    d = RUNS_DIR / (date or today())
    d.mkdir(parents=True, exist_ok=True)
    return d


def norm_company(name: str) -> str:
    n = name.lower().strip()
    n = re.sub(r"\(.*?\)", "", n)
    n = re.sub(r"[,.]?\s+(inc|llc|ltd|gmbh|ag|corp|corporation|co|labs?|technologies|hq|ai|io)\.?$", "", n)
    n = re.sub(r"[^a-z0-9]", "", n)
    return n


def load_yaml(path: Path) -> dict:
    import yaml  # provided by each script's inline uv dependencies

    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}


def load_profile() -> dict:
    p = PROFILE_DIR / "profile.yaml"
    if not p.exists():
        sys.exit(f"No profile at {p}. Run the /setup skill first.")
    return load_yaml(p)


def load_rubric() -> dict:
    return load_yaml(PROFILE_DIR / "fit-score.yaml")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    # split on "\n" only: splitlines() also breaks on U+2028 and friends, which
    # postings contain and json.dumps(ensure_ascii=False) leaves as-is
    for i, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as e:
            print(f"warning: {path.name}:{i} is not valid JSON ({e}); skipped", file=sys.stderr)
    return out


def write_jsonl(path: Path, rows: list[dict], append: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a" if append else "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in columns})


def load_companies() -> list[dict]:
    return read_csv(COMPANIES_CSV)


def save_companies(rows: list[dict]) -> None:
    rows.sort(key=lambda r: norm_company(r["company"]))
    write_csv(COMPANIES_CSV, rows, COMPANY_COLUMNS)


# --- HTTP -----------------------------------------------------------------

UA = "Mozilla/5.0 (lookalike-job-hunter; +https://github.com/jpooksy/lookalike-job-hunter)"


def http_get(url: str, timeout: int = 20, retries: int = 2) -> tuple[int, str]:
    """Return (status, body). Status 0 means a network error."""
    last = (0, "")
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            return e.code, ""
        except Exception as e:  # noqa: BLE001 - network errors of every flavor
            last = (0, str(e))
            time.sleep(1)
    return last


def http_json(url: str) -> tuple[int, object]:
    status, body = http_get(url)
    if status != 200:
        return status, None
    try:
        return status, json.loads(body)
    except json.JSONDecodeError:
        return 0, None


# --- HTML -> text ---------------------------------------------------------


class _Text(HTMLParser):
    BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "tr", "ul", "ol"}

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.BLOCK:
            self.parts.append("\n")
        if tag == "li":
            self.parts.append("- ")

    def handle_data(self, data):
        self.parts.append(data)


def html_to_text(s: str) -> str:
    if not s:
        return ""
    p = _Text()
    p.feed(html.unescape(s) if "&lt;" in s else s)
    text = "".join(p.parts)
    text = re.sub(r"[ \t\xa0]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()
