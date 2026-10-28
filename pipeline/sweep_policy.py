"""When the duplicate sweep (dedupe.py --sweep) should run. No database, no AI: easy to test.

The sweep walks every published death record looking for repeats the publish step missed. It used to
start over the moment it reached the end, so it ran for hours, four times a day, forever. Now:

- a pass that's under way always continues (it resumes from the last record it checked);
- once a full pass ends, the next one waits a week (one pass per week at most);
- once a full pass finds no duplicates at all, the cleanup is finished and the sweep stops for good.
  `--force` (the manual "dedupe-sweep" job) still runs it any time.
"""
from __future__ import annotations

import datetime as dt

PASS_EVERY = dt.timedelta(days=7)


def _when(s) -> dt.datetime | None:
    if not s:
        return None
    try:
        t = dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def skip_reason(meta: dict | None, now: dt.datetime | None = None) -> str | None:
    """None = sweep now; otherwise the reason to skip (printed in the log)."""
    meta = meta or {}
    now = now or dt.datetime.now(dt.timezone.utc)
    if int(meta.get("last_id") or 0) > 0:
        return None  # a pass is under way: finish it
    done_at = _when(meta.get("pass_done_at"))
    if done_at is None:
        return None  # no full pass recorded yet
    if meta.get("last_pass_merges") == 0:
        return ("the last full pass found no duplicates, so the cleanup is finished "
                "(run the dedupe-sweep job by hand to sweep again)")
    if now - done_at < PASS_EVERY:
        nxt = (done_at + PASS_EVERY).date().isoformat()
        return f"a full pass finished on {done_at.date().isoformat()}; the next one starts after {nxt} (one pass a week)"
    return None


def next_meta(prev: dict | None, last_id: int, merges: int, wrapped: bool,
              now: dt.datetime | None = None) -> dict:
    """What a sweep run records: where to resume, and the running count of merges in this pass."""
    prev = prev or {}
    now = now or dt.datetime.now(dt.timezone.utc)
    in_pass = int(prev.get("pass_merges") or 0) + int(merges)
    if wrapped:
        return {"last_id": 0, "pass_merges": 0, "last_pass_merges": in_pass, "pass_done_at": now.isoformat()}
    return {"last_id": int(last_id), "pass_merges": in_pass,
            "last_pass_merges": prev.get("last_pass_merges"), "pass_done_at": prev.get("pass_done_at")}
