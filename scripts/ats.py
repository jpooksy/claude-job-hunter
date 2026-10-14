# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6"]
# ///
"""Public job-board (ATS) APIs: detect a company's board, fetch postings, verify tracked roles.

Supported boards (all public, no API key): Greenhouse, Ashby, Lever, Workable.
Most software companies use one of these. Companies that don't are marked
status=no_ats and the find-jobs skill checks their careers page by hand.

Usage:
  uv run scripts/ats.py import FILE.jsonl... [--relationship research]  # add companies, skipping known ones
  uv run scripts/ats.py set --company NAME (--ats lever --slug acme | --none)  # fix a board by hand
  uv run scripts/ats.py detect [--all | --company NAME]   # fill ats/slug in data/companies.csv
  uv run scripts/ats.py fetch [--company NAME]            # all postings -> runs/<date>/postings.jsonl
  uv run scripts/ats.py verify                            # tracked roles -> runs/<date>/verify.jsonl
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import (  # noqa: E402
    html_to_text, http_get, http_json, load_companies, norm_company, read_csv,
    read_jsonl, run_dir, save_companies, today, write_jsonl, TRACKER_DIR,
)

DESC_LIMIT = 15000

# --- Providers ------------------------------------------------------------
# Each provider returns (board_name_or_None, [posting, ...]) or None if the slug doesn't exist.


def _money(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _workplace(raw: str | None, location: str) -> str:
    s = f"{raw or ''} {location}".lower()
    if "hybrid" in s:
        return "hybrid"
    if "remote" in s:
        return "remote"
    if raw and raw.lower() in ("onsite", "on-site", "in office", "inoffice"):
        return "onsite"
    return "unknown"


def greenhouse(slug: str):
    status, data = http_json(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true")
    if status != 200 or not isinstance(data, dict):
        return None
    _, meta = http_json(f"https://boards-api.greenhouse.io/v1/boards/{slug}")
    name = meta.get("name") if isinstance(meta, dict) else None
    out = []
    for j in data.get("jobs", []):
        loc = (j.get("location") or {}).get("name", "")
        out.append({
            "job_id": str(j["id"]), "title": j.get("title", ""), "url": j.get("absolute_url", ""),
            "location": loc, "workplace": _workplace(None, loc),
            "comp_min": None, "comp_max": None, "comp_currency": None,
            "posted": (j.get("first_published") or j.get("updated_at") or "")[:10],
            "description": html_to_text(j.get("content", "")),
        })
    return name, out


def ashby(slug: str):
    status, data = http_json(
        f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true")
    if status != 200 or not isinstance(data, dict):
        return None
    out = []
    for j in data.get("jobs", []):
        if j.get("isListed") is False:
            continue
        locs = [j.get("location") or ""] + [
            s.get("location", "") for s in (j.get("secondaryLocations") or [])]
        loc = "; ".join(x for x in locs if x)
        wp = j.get("workplaceType") or ("Remote" if j.get("isRemote") else None)
        cmin = cmax = cur = None
        comp = j.get("compensation") or {}
        for c in comp.get("summaryComponents") or []:
            if c.get("compensationType") == "Salary":
                cmin, cmax, cur = _money(c.get("minValue")), _money(c.get("maxValue")), c.get("currencyCode")
                break
        out.append({
            "job_id": j["id"], "title": j.get("title", ""), "url": j.get("jobUrl", ""),
            "location": loc, "workplace": _workplace(wp, loc),
            "comp_min": cmin, "comp_max": cmax, "comp_currency": cur,
            "comp_text": comp.get("compensationTierSummary"),
            "posted": (j.get("publishedAt") or "")[:10],
            "description": j.get("descriptionPlain") or html_to_text(j.get("descriptionHtml", "")),
        })
    return None, out


def lever(slug: str):
    status, data = http_json(f"https://api.lever.co/v0/postings/{slug}?mode=json")
    if status != 200 or not isinstance(data, list):
        return None
    out = []
    for j in data:
        cat = j.get("categories") or {}
        loc = "; ".join(cat.get("allLocations") or [cat.get("location", "")])
        sal = j.get("salaryRange") or {}
        parts = [j.get("descriptionPlain", "")]
        for lst in j.get("lists") or []:
            parts.append(f"{lst.get('text', '')}\n{html_to_text(lst.get('content', ''))}")
        parts.append(j.get("additionalPlain", ""))
        posted = ""
        if j.get("createdAt"):
            posted = dt.date.fromtimestamp(int(j["createdAt"]) / 1000).isoformat()
        out.append({
            "job_id": j["id"], "title": j.get("text", ""), "url": j.get("hostedUrl", ""),
            "location": loc, "workplace": _workplace(j.get("workplaceType"), loc),
            "comp_min": _money(sal.get("min")), "comp_max": _money(sal.get("max")),
            "comp_currency": sal.get("currency"), "posted": posted,
            "description": "\n\n".join(p for p in parts if p),
        })
    return None, out


def workable(slug: str):
    status, data = http_json(f"https://apply.workable.com/api/v1/widget/accounts/{slug}?details=true")
    if status != 200 or not isinstance(data, dict):
        return None
    out = []
    for j in data.get("jobs", []):
        loc = ", ".join(x for x in (j.get("city"), j.get("state"), j.get("country")) if x)
        remote = str(j.get("telecommuting")).lower() == "true"
        out.append({
            "job_id": j.get("shortcode", ""), "title": j.get("title", ""), "url": j.get("url", ""),
            "location": loc, "workplace": "remote" if remote else _workplace(None, loc),
            "comp_min": None, "comp_max": None, "comp_currency": None,
            "posted": j.get("published_on", ""),
            "description": html_to_text(j.get("description", "")),
        })
    return data.get("name"), out


PROVIDERS = {"greenhouse": greenhouse, "ashby": ashby, "lever": lever, "workable": workable}

# Board URLs as they appear in careers-page HTML.
BOARD_PATTERNS = [
    ("greenhouse", r"(?:job-boards|boards)(?:\.eu)?\.greenhouse\.io/(?:embed/job_board\?for=)?([A-Za-z0-9_-]+)"),
    ("greenhouse", r"boards-api\.greenhouse\.io/v1/boards/([A-Za-z0-9_-]+)"),
    ("ashby", r"jobs\.ashbyhq\.com/([A-Za-z0-9_.%-]+)"),
    ("ashby", r"api\.ashbyhq\.com/posting-api/job-board/([A-Za-z0-9_.-]+)"),
    ("lever", r"jobs\.lever\.co/([A-Za-z0-9_-]+)"),
    ("workable", r"apply\.workable\.com/([A-Za-z0-9_-]+)"),
]
IGNORE_SLUGS = {"embed", "api", "v1", "j", "jobs", "careers", "static", "assets", "_next"}


def fetch_board(ats: str, slug: str):
    return PROVIDERS[ats](slug)


# --- import ---------------------------------------------------------------


def cmd_import(args):
    rows = load_companies()
    # Only companies.csv counts as "known". Companies that are in the tracker but
    # not in companies.csv (e.g. from an imported sheet) are exactly what to add.
    known = {norm_company(r["company"]) for r in rows}
    added, dupes = [], []
    for f in args.files:
        for c in read_jsonl(Path(f)):
            name = (c.get("company") or "").strip()
            if not name:
                continue
            key = norm_company(name)
            if key in known:
                dupes.append(name)
                continue
            known.add(key)
            added.append({"company": name, "domain": c.get("domain", ""),
                          "relationship": c.get("relationship") or args.relationship,
                          "careers_url": c.get("careers_url", ""), "status": "active",
                          "why": c.get("why", ""), "added": today()})
    save_companies(rows + added)
    print(f"Added {len(added)} companies, skipped {len(dupes)} already known.")
    for a in added:
        print(f"  + {a['company']} ({a['domain']}): {a['why'][:90]}")
    if dupes:
        print("  skipped: " + ", ".join(sorted(set(dupes))))


def cmd_set(args):
    """Record a company's job board by hand (or mark it as having none)."""
    rows = load_companies()
    hit = [r for r in rows if norm_company(r["company"]) == norm_company(args.company)]
    if not hit:
        sys.exit(f"{args.company} isn't in data/companies.csv. Import it first.")
    r = hit[0]
    if args.none:
        r.update({"ats": "", "slug": "", "detect": "manual", "status": "no_ats"})
    else:
        if args.ats not in PROVIDERS or not args.slug:
            sys.exit(f"--ats must be one of {', '.join(PROVIDERS)}, with --slug.")
        if fetch_board(args.ats, args.slug) is None:
            sys.exit(f"No {args.ats} board at slug {args.slug!r}.")
        r.update({"ats": args.ats, "slug": args.slug, "detect": "manual", "status": "active"})
    if args.careers_url:
        r["careers_url"] = args.careers_url
    save_companies(rows)
    print(f"{r['company']}: {r['ats'] or 'no supported board'} {r['slug']} (manual)")


# --- detect ---------------------------------------------------------------


def _careers_pages(row: dict) -> list[str]:
    urls = []
    if row.get("careers_url"):
        urls.append(row["careers_url"])
    dom = (row.get("domain") or "").strip().removeprefix("https://").removeprefix("http://").strip("/")
    if dom:
        urls += [f"https://{dom}/careers", f"https://{dom}/jobs", f"https://{dom}/company/careers",
                 f"https://{dom}/about/careers", f"https://{dom}"]
    return urls


def _slug_guesses(row: dict) -> list[str]:
    name = row["company"]
    dom = (row.get("domain") or "").split("/")[0]
    stem = dom.split(".")[0] if dom else ""
    base = re.sub(r"\(.*?\)", "", name).strip()
    cands = [norm_company(base), re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-"),
             re.sub(r"[^a-z0-9]", "", base.lower()), stem, f"{norm_company(base)}hq",
             f"{norm_company(base)}inc", f"{norm_company(base)}labs"]
    seen, out = set(), []
    for c in cands:
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _name_matches(company: str, board_name: str | None) -> bool:
    if not board_name:
        return True  # provider doesn't expose a name; can't contradict
    a, b = norm_company(company), norm_company(board_name)
    return a in b or b in a or SequenceMatcher(None, a, b).ratio() > 0.7


def detect_one(row: dict) -> dict:
    # 1) Look for a board link on the company's own careers page (reliable).
    for url in _careers_pages(row):
        status, body = http_get(url, timeout=15, retries=0)
        if status != 200 or not body:
            continue
        for ats, pat in BOARD_PATTERNS:
            for slug in re.findall(pat, body):
                slug = slug.strip("/").split("?")[0]
                if slug.lower() in IGNORE_SLUGS:
                    continue
                res = fetch_board(ats, slug)
                if res is not None:
                    return {**row, "ats": ats, "slug": slug, "detect": "careers_page",
                            "careers_url": row.get("careers_url") or url, "status": "active"}
    # 2) Guess slugs against each provider. Can hit a same-named company, so flag it.
    # A guessed board with zero jobs is usually a dead or unrelated account (Workable
    # answers 200 for abandoned accounts), so it doesn't count as a match.
    empty = None
    for slug in _slug_guesses(row):
        for ats in PROVIDERS:
            res = fetch_board(ats, slug)
            if res is None:
                continue
            board_name, jobs = res
            if not _name_matches(row["company"], board_name):
                continue
            if not jobs:
                empty = empty or f"{ats}/{slug}"
                continue
            return {**row, "ats": ats, "slug": slug, "status": "active",
                    "detect": "guessed" if board_name is None else "guessed_name_ok"}
    note = f"not_found (empty board at {empty})" if empty else "not_found"
    return {**row, "ats": "", "slug": "", "detect": note, "status": "no_ats"}


def cmd_detect(args):
    rows = load_companies()
    if not rows:
        sys.exit("data/companies.csv is empty. Add companies first.")
    # Boards set by hand (`ats.py set`) are never re-detected, even with --all.
    def eligible(r):
        return r.get("detect") != "manual" and r.get("status") != "ignored"
    targets = [r for r in rows if eligible(r) and (args.all or (not r.get("ats") and r.get("status") != "no_ats"))]
    if args.company:
        targets = [r for r in rows if eligible(r) and norm_company(r["company"]) == norm_company(args.company)]
    print(f"Detecting job boards for {len(targets)} companies...", file=sys.stderr)
    with ThreadPoolExecutor(8) as ex:
        results = list(ex.map(detect_one, targets))
    by_key = {norm_company(r["company"]): r for r in results}
    merged = [by_key.get(norm_company(r["company"]), r) for r in rows]
    save_companies(merged)
    for r in results:
        print(f"{r['company']:<28} {r['ats'] or '-':<11} {r['slug'] or '-':<24} {r['detect']}")
    found = sum(1 for r in results if r["ats"])
    guessed = [r["company"] for r in results if r["detect"] == "guessed"]
    print(f"\n{found}/{len(results)} found.", file=sys.stderr)
    if guessed:
        print("Guessed without a name check (confirm these are the right company): "
              + ", ".join(guessed), file=sys.stderr)


# --- fetch ----------------------------------------------------------------


def _fetch_company(row: dict):
    res = fetch_board(row["ats"], row["slug"])
    if res is None:
        return row, None
    _, jobs = res
    for j in jobs:
        j["id"] = f"{row['ats']}:{row['slug']}:{j['job_id']}"
        j["company"] = row["company"]
        j["ats"] = row["ats"]
        j["description"] = (j.get("description") or "")[:DESC_LIMIT]
    return row, jobs


def cmd_fetch(args):
    rows = [r for r in load_companies() if r.get("ats") and r.get("status") == "active"]
    if args.company:
        rows = [r for r in rows if norm_company(r["company"]) == norm_company(args.company)]
    print(f"Fetching boards for {len(rows)} companies...", file=sys.stderr)
    out, errors = [], []
    with ThreadPoolExecutor(8) as ex:
        for row, jobs in ex.map(_fetch_company, rows):
            if jobs is None:
                errors.append(row["company"])
            else:
                out.extend(jobs)
    path = run_dir() / "postings.jsonl"
    write_jsonl(path, out)
    print(f"{len(out)} postings from {len(rows) - len(errors)} boards -> {path}")
    if errors:
        print("Board fetch failed (slug changed? re-run detect --company): " + ", ".join(errors))


# --- verify ---------------------------------------------------------------


def cmd_verify(args):
    tracked = read_csv(TRACKER_DIR / "snapshot.csv")
    if not tracked:
        sys.exit("No tracker snapshot. Run `uv run scripts/tracker.py pull` first.")
    boards: dict[tuple, list[dict]] = {}
    other: list[dict] = []
    for r in tracked:
        parts = (r.get("ID") or "").split(":", 2)
        if len(parts) == 3 and parts[0] in PROVIDERS:
            boards.setdefault((parts[0], parts[1]), []).append(r)
        elif (r.get("URL") or "").startswith("http"):
            other.append(r)

    def check_board(key):
        res = fetch_board(*key)
        return key, (None if res is None else {j["job_id"]: j for j in res[1]})

    results = []
    with ThreadPoolExecutor(8) as ex:
        for (ats, slug), live in ex.map(check_board, boards):
            for r in boards[(ats, slug)]:
                job_id = r["ID"].split(":", 2)[2]
                if live is None:
                    state, detail = "UNKNOWN", "board fetch failed"
                elif job_id in live:
                    lt = live[job_id]["title"]
                    same = lt.strip().lower() == (r.get("Role") or "").strip().lower()
                    state, detail = ("LIVE", "") if same else ("CHANGED", f"title now: {lt}")
                else:
                    state, detail = "GONE", "not on job board"
                results.append({"id": r["ID"], "company": r["Company"], "role": r["Role"],
                                "state": state, "detail": detail})

        def check_url(r):
            status, _ = http_get(r["URL"], timeout=15, retries=1)
            if status in (404, 410):
                return {"id": r["ID"], "company": r["Company"], "role": r["Role"],
                        "state": "GONE", "detail": f"HTTP {status}"}
            return {"id": r["ID"], "company": r["Company"], "role": r["Role"],
                    "state": "UNKNOWN", "detail": f"HTTP {status}; not a supported board, check by hand"}

        results += list(ex.map(check_url, other))

    path = run_dir() / "verify.jsonl"
    write_jsonl(path, results)
    counts: dict[str, int] = {}
    for r in results:
        counts[r["state"]] = counts.get(r["state"], 0) + 1
    print(f"{counts} -> {path}")
    for r in results:
        if r["state"] != "LIVE":
            print(f"  {r['state']:<8} {r['company']} / {r['role']}  {r['detail']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    im = sub.add_parser("import")
    im.add_argument("files", nargs="+")
    im.add_argument("--relationship", default="research",
                    choices=["interviewed", "door_open", "warm", "target", "research"])
    st = sub.add_parser("set")
    st.add_argument("--company", required=True)
    st.add_argument("--ats", choices=list(PROVIDERS))
    st.add_argument("--slug")
    st.add_argument("--none", action="store_true", help="no supported board; check the careers page by hand")
    st.add_argument("--careers-url")
    d = sub.add_parser("detect")
    d.add_argument("--all", action="store_true", help="re-detect companies that already have a board")
    d.add_argument("--company")
    f = sub.add_parser("fetch")
    f.add_argument("--company")
    sub.add_parser("verify")
    args = ap.parse_args()
    {"import": cmd_import, "set": cmd_set, "detect": cmd_detect, "fetch": cmd_fetch, "verify": cmd_verify}[args.cmd](args)


if __name__ == "__main__":
    main()
