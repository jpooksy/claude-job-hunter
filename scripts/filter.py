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

--append runs it again later in the same run (e.g. after newly researched
companies were fetched): postings already in this run's candidates are skipped,
and new batches continue the numbering, so batches already being read are
never touched.

Usage:
  uv run scripts/filter.py [--date YYYY-MM-DD] [--batch-size 6] [--append]
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


def _norm_title(t: str) -> str:
    # "Pre-Sales Solutions Engineer (San Francisco, CA)" is the same job as the one
    # tracked as "Pre-Sales Solutions Engineer": ignore parenthesised locations/notes.
    t = re.sub(r"\([^)]*\)", " ", (t or "").lower())
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def comp_floor(title: str, comp: dict) -> int:
    """The pay floor for this title: the first matching by_title rule, else the default."""
    for rule in comp.get("by_title") or []:
        if re.search(rule.get("match", "$^"), title, re.IGNORECASE):
            return rule.get("min_top_of_range") or 0
    return comp.get("min_top_of_range") or 0


def reason_to_drop(p: dict, prof: dict) -> str | None:
    title = p["title"]
    titles = prof.get("titles") or {}
    stretch = _any(titles.get("stretch"), title)  # roles the user chose to keep despite the level
    if not stretch and not _any(titles.get("include"), title):
        return "title: not a target title"
    hit = _any(titles.get("exclude"), title)
    if hit:
        return f"title: excluded ({hit})"

    level = level_from_title(title)
    excluded = (prof.get("level") or {}).get("exclude") or []
    if level in excluded:
        # A stretch title (e.g. "head of devrel") only unlocks the level it implies
        # itself, not every senior variant of a broad pattern ("Staff Solutions Architect").
        if not stretch or level != level_from_title(re.sub(r"[\\()?|\[\]^$.*+]", " ", stretch)):
            return f"level: {level} excluded"

    if norm_company(p["company"]) in {norm_company(c) for c in prof.get("exclude_companies") or []}:
        return "company: excluded"

    loc = prof.get("location") or {}
    where = p.get("location") or ""
    relocate = loc.get("relocate_to") or []
    anywhere = any(str(r).lower().startswith("anywhere") for r in relocate)
    in_country = bool(_any(loc.get("country_markers"), where))
    if _any(loc.get("exclude_location_patterns"), where) and not in_country:
        return f"location: {where}"
    # Region in the title ("Solutions Engineer - EMEA") even when the location just says "Remote".
    if _any(loc.get("exclude_location_patterns"), title) and not _any(loc.get("country_markers"), title):
        return f"location: {title}"
    if loc.get("remote") == "required" and p.get("workplace") in ("onsite", "hybrid"):
        ok_metros = [re.escape(m) for m in (loc.get("onsite_ok_metros") or []) + [
            r for r in relocate if not str(r).lower().startswith("anywhere")]]
        if not _any(ok_metros, where) and not (anywhere and (in_country or not where)):
            return f"location: {p['workplace']} in {where}"

    comp = prof.get("comp") or {}
    floor = comp_floor(title, comp)
    cur = comp.get("currency")
    if floor and p.get("comp_max") and (not cur or not p.get("comp_currency") or p["comp_currency"] == cur):
        if p["comp_max"] <= floor:
            return f"comp: tops out at {p['comp_max']}"
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date")
    ap.add_argument("--batch-size", type=int, default=6)
    ap.add_argument("--append", action="store_true", help="add new batches to this run, keep existing ones")
    args = ap.parse_args()

    prof = load_profile()
    rd = run_dir(args.date)
    # postings.jsonl comes from ats.py fetch; postings-manual.jsonl holds roles
    # found by hand on careers pages of companies without a supported board.
    postings = read_jsonl(rd / "postings.jsonl") + read_jsonl(rd / "postings-manual.jsonl")
    if not postings:
        sys.exit(f"No postings in {rd}. Run `uv run scripts/ats.py fetch` first.")

    tracked = read_csv(TRACKER_DIR / "snapshot.csv")
    known = {r.get("ID") for r in tracked}
    known |= {s["id"] for s in read_jsonl(SEEN_JSONL)}
    # Rows from an imported list or the inbox have no job-board ID, so also match
    # on company + title to avoid re-reading roles the user already tracks.
    tracked_names = {(norm_company(r.get("Company", "")), _norm_title(r.get("Role", ""))) for r in tracked}

    earlier = read_jsonl(rd / "candidates.jsonl") if args.append else []
    in_run = {c["id"] for c in earlier}
    seen_names = {(norm_company(c["company"]), _norm_title(c["title"])) for c in earlier}

    keep, dropped, counts = [], [], {}
    for p in postings:
        name = (norm_company(p["company"]), _norm_title(p["title"]))
        if p["id"] in in_run:
            continue  # already a candidate in this run
        if p["id"] in known or name in tracked_names:
            counts["already tracked or judged"] = counts.get("already tracked or judged", 0) + 1
            continue
        if name in seen_names:  # the same role posted twice (e.g. two locations)
            counts["duplicate in this run"] = counts.get("duplicate in this run", 0) + 1
            continue
        why = reason_to_drop(p, prof)
        if why:
            bucket = why.split(":")[0]
            counts[bucket] = counts.get(bucket, 0) + 1
            dropped.append({"id": p["id"], "company": p["company"], "title": p["title"], "reason": why})
        else:
            p["title_level"] = level_from_title(p["title"])
            keep.append(p)
            seen_names.add(name)

    write_jsonl(rd / "filtered_out.jsonl", dropped, append=args.append)
    write_jsonl(rd / "candidates.jsonl", keep, append=args.append)
    bdir = rd / "batches"
    bdir.mkdir(exist_ok=True)
    existing = sorted(bdir.glob("batch-*.jsonl"))
    if not args.append:
        for old in existing:
            old.unlink()
        existing = []
    start = len(existing)
    new_batches = []
    for i in range(0, len(keep), args.batch_size):
        path = bdir / f"batch-{start + len(new_batches) + 1:02d}.jsonl"
        write_jsonl(path, keep[i:i + args.batch_size])
        new_batches.append(path.name)

    print(f"{len(postings)} postings -> {len(keep)} new candidates in {len(new_batches)} batches ({bdir})")
    if new_batches:
        print("  new batches: " + ", ".join(new_batches))
    for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  dropped {v:>5}  {k}")
    by_co: dict[str, int] = {}
    for p in keep:
        by_co[p["company"]] = by_co.get(p["company"], 0) + 1
    if by_co:
        print("  candidates by company: " + ", ".join(f"{c} ({n})" for c, n in sorted(by_co.items())))


if __name__ == "__main__":
    main()
