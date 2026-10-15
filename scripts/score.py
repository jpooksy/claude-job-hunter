# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6"]
# ///
"""Turn jd-reader extractions into fit scores, using profile/fit-score.yaml.

The LLM's job is to read a posting and fill in fields (level, industry tier,
qualification fit, dealbreaker hits). This script does the arithmetic, so the
same posting always gets the same score and every point is written into the
"Fit reasoning" column.

Inputs:  runs/<date>/candidates.jsonl, runs/<date>/extract/*.jsonl
Outputs: runs/<date>/scored.jsonl (rows to add), runs/<date>/dropped.jsonl,
         and every judged posting is appended to data/seen.jsonl so it is never
         read twice.

Usage:
  uv run scripts/score.py [--date YYYY-MM-DD] [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import (  # noqa: E402
    LEVELS, SEEN_JSONL, TRACKER_DIR, load_companies, load_profile, load_rubric, norm_company,
    read_csv, read_jsonl, run_dir, today, write_jsonl,
)

# A short, plain note on why this company is in the search at all.
RELATIONSHIP_NOTE = {
    "interviewed": "You interviewed here before.",
    "door_open": "They asked you to stay in touch.",
    "warm": "You have a warm path in here.",
    "target": "A company on your list.",
    "research": "A new company Claude found for you.",
}


def comp_text(c: dict, x: dict) -> str:
    if c.get("comp_text"):
        return c["comp_text"]
    lo = x.get("comp_min") or c.get("comp_min")
    hi = x.get("comp_max") or c.get("comp_max")
    if not (lo or hi):
        return ""
    cur = x.get("comp_currency") or c.get("comp_currency") or ""
    sym = "$" if cur in ("USD", "", None) else f"{cur} "
    fmt = lambda v: f"{sym}{round(v / 1000)}k" if v else "?"  # noqa: E731
    return f"{fmt(lo)}–{fmt(hi)}"


def score_one(c: dict, x: dict, rubric: dict, prof: dict, rel: str) -> tuple[int | None, list[str], str | None]:
    """Return (score, reasons, drop_reason)."""
    if x.get("dealbreakers"):
        d = x["dealbreakers"][0]
        return None, [], f"dealbreaker: {d.get('rule')} ({d.get('evidence', '')[:120]})"
    if x.get("location_ok") is False:
        return None, [], f"location: {x.get('location_note') or x.get('workplace')}"
    qual_rules = rubric.get("qualification") or {}
    q = x.get("qualification", "solid")
    if qual_rules.get(q) == "drop":
        missing = [r["req"] for r in x.get("required", []) if r.get("met") == "no"]
        return None, [], f"qualification: {q} (missing: {'; '.join(missing)[:160]})"

    pts = [("base", rubric.get("base", 5))]

    tier = x.get("industry_tier", "other")
    v = (rubric.get("industry") or {}).get(tier, 0)
    if v:
        pts.append((f"{tier} industry ({x.get('industry', '?')})", v))

    v = (rubric.get("relationship") or {}).get(rel, 0)
    if v:
        pts.append((rel.replace("_", " "), v))

    lv_rules = rubric.get("level") or {}
    targets = [LEVELS[t] for t in (prof.get("level") or {}).get("target", ["mid"]) if t in LEVELS]
    lv = x.get("level") or c.get("title_level") or "mid"
    if lv in LEVELS and targets:
        gap = LEVELS[lv] - max(targets)
        if LEVELS[lv] in targets:
            key = "on_target"
        elif gap < 0:
            key = "below_target"
        elif gap == 1:
            key = "one_above"
        else:
            key = "two_plus_above"
        v = lv_rules.get(key, 0)
        if v:
            pts.append((f"level {lv} ({key.replace('_', ' ')})", v))

    loc_rules = rubric.get("location") or {}
    pref = (prof.get("location") or {}).get("preferred_metros") or []
    where = c.get("location", "")  # the posting's own location; the reader's note may just mention home
    if loc_rules.get("preferred_metro") and any(m.lower() in where.lower() for m in pref):
        pts.append(("preferred metro", loc_rules["preferred_metro"]))
    if loc_rules.get("hours_conflict") and x.get("hours_conflict"):
        pts.append(("working hours conflict", loc_rules["hours_conflict"]))

    v = qual_rules.get(q, 0)
    if isinstance(v, int) and v:
        pts.append((f"{q} qualification match", v))

    stretch = (prof.get("titles") or {}).get("stretch") or []
    if any(re.search(pt, c.get("title", ""), re.IGNORECASE) for pt in stretch):
        pts.append(("stretch role you chose to keep", rubric.get("stretch_title", -1)))

    hay = " ".join([c.get("title", ""), x.get("industry", ""), x.get("buyer", "")])
    for k in rubric.get("keywords") or []:
        if re.search(k["pattern"], hay, re.IGNORECASE):
            pts.append((k.get("label", k["pattern"]), k["points"]))

    total = sum(p for _, p in pts)
    total = max(rubric.get("min", 1), min(rubric.get("max", 10), total))
    reasons = [f"{label} {'+' if p >= 0 else ''}{p}" if label != "base" else f"base {p}" for label, p in pts]
    return total, reasons, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date")
    ap.add_argument("--dry-run", action="store_true", help="don't append to data/seen.jsonl")
    args = ap.parse_args()

    prof, rubric = load_profile(), load_rubric()
    if not rubric:
        sys.exit("No profile/fit-score.yaml. Run /setup or copy templates/profile/fit-score.yaml.")
    rd = run_dir(args.date)
    cands = {c["id"]: c for c in read_jsonl(rd / "candidates.jsonl")}
    extracts = {}
    for f in sorted((rd / "extract").glob("*.jsonl")):
        for x in read_jsonl(f):
            extracts[x["id"]] = x
    rel_by_co = {norm_company(r["company"]): (r.get("relationship") or "research") for r in load_companies()}
    # If the user is already in process somewhere, a second role there isn't extra
    # evidence of fit, so it gets no relationship bonus, just a note.
    active = {}
    for r in read_csv(TRACKER_DIR / "snapshot.csv"):
        if r.get("Status") in ("Applied", "In Conversation", "Interviewing", "Offer"):
            active.setdefault(norm_company(r.get("Company", "")), r.get("Role") or "a role")

    scored, dropped, seen, unread = [], [], [], []
    for cid, c in cands.items():
        x = extracts.get(cid)
        if not x:
            unread.append(cid)
            continue
        rel = rel_by_co.get(norm_company(c["company"]), "research")
        in_process = active.get(norm_company(c["company"]))
        s, reasons, drop = score_one(c, x, rubric, prof, "research" if in_process else rel)
        if drop:
            dropped.append({"id": cid, "company": c["company"], "title": c["title"], "reason": drop})
            seen.append({"id": cid, "decision": "dropped", "reason": drop, "date": today()})
            continue
        scored.append({
            "ID": cid, "Category": "To apply", "Fit": s, "Company": c["company"],
            "Role": c["title"], "Status": "Not Applied", "Applied": "",
            "Comp": comp_text(c, x), "Location": c.get("location", ""),
            "Added by": "Claude",
            "Last updated": today(), "URL": c.get("url", ""),
            "Notes": (f"You're already in process here ({in_process})." if in_process
                      else RELATIONSHIP_NOTE.get(rel, RELATIONSHIP_NOTE["research"])) + f" {x.get('summary', '')}".rstrip(), "Fit reasoning": "; ".join(reasons) + f" = {s}",
        })
        seen.append({"id": cid, "decision": "scored", "score": s, "date": today()})

    scored.sort(key=lambda r: -r["Fit"])
    write_jsonl(rd / "scored.jsonl", scored)
    write_jsonl(rd / "dropped.jsonl", dropped)
    if not args.dry_run:
        write_jsonl(SEEN_JSONL, seen, append=True)

    print(f"{len(scored)} scored, {len(dropped)} dropped, {len(unread)} not read yet")
    for r in scored[:25]:
        print(f"  {r['Fit']:>2}  {r['Company']} / {r['Role']}  [{r['Fit reasoning']}]")
    if dropped:
        print("Dropped:")
        for d in dropped:
            print(f"  {d['company']} / {d['title']}: {d['reason']}")
    if unread:
        print(f"Not read yet (no extraction): {len(unread)}. Re-run the jd-reader for the missing batches.")


if __name__ == "__main__":
    main()
