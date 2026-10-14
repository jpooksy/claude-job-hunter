# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6"]
# ///
"""Cheap, deterministic filtering of fetched postings before any LLM reads them.

Drops postings that are already tracked or already judged (data/seen.jsonl), whose
title doesn't match profile.titles, whose level is excluded, whose location is
ruled out, or whose posted pay range tops out below the floor. When a field is
unknown (no salary posted, location unclear) the posting is KEPT, so the
jd-reader can make the call with the full description.

Survivors are split into batch files for jd-reader agents.

Usage:
  uv run scripts/filter.py [--date YYYY-MM-DD] [--batch-size 10]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import (  # noqa: E402
    SEEN_JSONL, TRACKER_DIR, level_from_title, load_profile, norm_company,
    read_csv, read_jsonl, run_dir, write_jsonl,
)


def _any(patterns: list[str], text: str) -> str | None:
    for p in patterns or []:
        if re.search(p, text, re.IGNORECASE):
            return p
    return None


def reason_to_drop(p: dict, prof: dict) -> str | None:
    title = p["title"]
    titles = prof.get("titles") or {}
    if not _any(titles.get("include"), title):
        return "title: not a target title"
    hit = _any(titles.get("exclude"), title)
    if hit:
        return f"title: excluded ({hit})"

    level = level_from_title(title)
    if level in ((prof.get("level") or {}).get("exclude") or []):
        return f"level: {level} excluded"

    if norm_company(p["company"]) in {norm_company(c) for c in prof.get("exclude_companies") or []}:
        return "company: excluded"

    loc = prof.get("location") or {}
    where = p.get("location") or ""
    if _any(loc.get("exclude_location_patterns"), where) and not _any(loc.get("country_markers"), where):
        return f"location: {where}"
    if loc.get("remote") == "required" and p.get("workplace") in ("onsite", "hybrid"):
        if not _any([re.escape(m) for m in loc.get("onsite_ok_metros") or []], where):
            return f"location: {p['workplace']} in {where}"

    floor = (prof.get("comp") or {}).get("min_top_of_range") or 0
    cur = (prof.get("comp") or {}).get("currency")
    if floor and p.get("comp_max") and (not cur or not p.get("comp_currency") or p["comp_currency"] == cur):
        if p["comp_max"] <= floor:
            return f"comp: tops out at {p['comp_max']}"
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date")
    ap.add_argument("--batch-size", type=int, default=10)
    args = ap.parse_args()

    prof = load_profile()
    rd = run_dir(args.date)
    # postings.jsonl comes from ats.py fetch; postings-manual.jsonl holds roles
    # found by hand on careers pages of companies without a supported board.
    postings = read_jsonl(rd / "postings.jsonl") + read_jsonl(rd / "postings-manual.jsonl")
    if not postings:
        sys.exit(f"No postings in {rd}. Run `uv run scripts/ats.py fetch` first.")

    known = {r.get("ID") for r in read_csv(TRACKER_DIR / "snapshot.csv")}
    known |= {s["id"] for s in read_jsonl(SEEN_JSONL)}

    keep, dropped, counts = [], [], {}
    for p in postings:
        if p["id"] in known:
            counts["already tracked or judged"] = counts.get("already tracked or judged", 0) + 1
            continue
        why = reason_to_drop(p, prof)
        if why:
            bucket = why.split(":")[0]
            counts[bucket] = counts.get(bucket, 0) + 1
            dropped.append({"id": p["id"], "company": p["company"], "title": p["title"], "reason": why})
        else:
            p["title_level"] = level_from_title(p["title"])
            keep.append(p)

    write_jsonl(rd / "filtered_out.jsonl", dropped)
    write_jsonl(rd / "candidates.jsonl", keep)
    bdir = rd / "batches"
    bdir.mkdir(exist_ok=True)
    for old in bdir.glob("batch-*.jsonl"):
        old.unlink()
    n = 0
    for i in range(0, len(keep), args.batch_size):
        n += 1
        write_jsonl(bdir / f"batch-{n:02d}.jsonl", keep[i:i + args.batch_size])

    print(f"{len(postings)} postings -> {len(keep)} candidates in {n} batches ({bdir})")
    for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  dropped {v:>5}  {k}")
    by_co: dict[str, int] = {}
    for p in keep:
        by_co[p["company"]] = by_co.get(p["company"], 0) + 1
    if by_co:
        print("  candidates by company: " + ", ".join(f"{c} ({n})" for c, n in sorted(by_co.items())))


if __name__ == "__main__":
    main()
