"""Records that turned out not to be a death ("a suicide attempt", "expected to recover", "a murder charge").

New finds are dropped at extraction (extract.to_rows). For ones already stored:

    python -m pipeline.quality              # list matches (no changes)
    python -m pipeline.quality --apply      # hide them (hidden = true; reversible in /admin or the database)
"""
from __future__ import annotations

import argparse
import re

# Says no one died...
_NOT_DEATH = re.compile(
    r"\b(attempt(ed)?\s+(suicide|to\s+(kill|take))|suicide\s+attempt|attempted\s+murder|survived|survives|"
    r"(is|was)\s+expected\s+to\s+(live|recover)|will\s+recover|recovering|not\s+(seriously|fatally)\s+(hurt|injured|wounded)|"
    r"narrow(ly)?\s+escape[sd]?|escaped\s+(death|injury)|near[- ]drowning)\b",
    re.I,
)
# ...unless it also says someone did die.
_DEATH = re.compile(
    r"\b(died|dies|dead|death|deaths|killed|fatal(ly)?|drowned|body|bodies|perished|slain|murdered|"
    r"lynched|executed|hanged|burned\s+to\s+death|frozen\s+to\s+death|succumbed)\b",
    re.I,
)


def not_a_death(summary: str | None) -> bool:
    """True when a summary describes an event where nobody died."""
    s = summary or ""
    return bool(_NOT_DEATH.search(s)) and not _DEATH.search(_NOT_DEATH.sub(" ", s))


def main(apply: bool):
    from .common.db import db, retry

    last, found = 0, []
    while True:
        rows = retry(lambda: db().table("ap_incidents").select("id,event_id,summary")
                     .eq("hidden", False).eq("record_type", "death").gt("id", last)
                     .order("id").limit(1000).execute().data) or []
        if not rows:
            break
        last = rows[-1]["id"]
        found += [r for r in rows if not_a_death(r.get("summary"))]
    print(f"not a death: {len(found)} records")
    for r in found[:40]:
        print(f"  {r['id']}: {r.get('summary')}")
    if not apply:
        return
    events = set()
    for r in found:
        retry(lambda: db().table("ap_incidents").update({"hidden": True, "review_reason": "not a death"}).eq("id", r["id"]).execute())
        if r.get("event_id"):
            events.add(r["event_id"])
    for e in events:  # an event with nothing else behind it drops off the map
        retry(lambda: db().rpc("ap_refresh_event", {"p_event_id": e}).execute())
    print(f"hidden {len(found)} records, refreshed {len(events)} events")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    main(ap.parse_args().apply)
