"""Nightly: group incidents that describe the same death into one event.

1. Every incident without an event gets a singleton event.
2. For each new incident, the dedupe_candidates RPC finds nearby rows (same type,
   compatible cause, ±1 year, within 400 m or same town for city-level records).
3. Claude (Sonnet) confirms or rejects each pair; decisions are cached in dedupe_checks.
4. Confirmed pairs merge into one event; refresh_event recomputes location + combined confidence.
5. area_coverage is refreshed for the free-check footnote.

    python -m pipeline.dedupe [--limit 500]
"""
import argparse
import time

from anthropic import Anthropic

from .common.ai import create_with_tool, tool_input
from .common.config import MODEL_FAST as MODEL_DEDUPE
from .common.db import db, retry
from .common.runlog import BudgetExceeded, PipelineRun
from .dedupe_rules import date_gap_days, rule_verdict, summary_similarity

client = Anthropic()

SYSTEM = """You decide whether two newspaper-derived records describe the SAME death.
Same death = same event, even if wording, dates (±a few days), or address details differ slightly.
Different deaths can happen at the same place; be careful with common causes like accidents.
Answer only with the tool call."""

TOOL = {
    "name": "decide",
    "description": "Whether the two records are the same death.",
    "input_schema": {
        "type": "object",
        "properties": {"same_event": {"type": "boolean"}, "rationale": {"type": "string"}},
        "required": ["same_event", "rationale"],
    },
}

FIELDS = "id,event_id,source_url,source_name,published_date,incident_date,address_raw,city,county,cause_category,summary,geocode_precision,record_type,incident_year"


def describe(r: dict) -> str:
    return (
        f"source={r.get('source_name')} published={r.get('published_date')} date={r.get('incident_date')} "
        f"place={r.get('address_raw')}, {r.get('city')} ({r.get('geocode_precision')}) cause={r.get('cause_category')} "
        f"summary={r.get('summary')}"
    )


def _make_event(r: dict) -> dict:
    return retry(lambda: _make_event_once(r))


def _make_event_once(r: dict) -> dict:
    # Each step is remembered on r, so a retry after a dropped connection picks up where it stopped
    # instead of inserting a second event (that left empty or doubled events before Oct 27).
    if not r.get("_event"):
        ev = db().table("ap_events").insert({
            "record_type": r.get("record_type") or "death",
            "cause_category": r.get("cause_category") or "unknown",
            "event_year": r.get("incident_year"),
            "city": r.get("city"),
            "county": r.get("county"),
            "summary": r.get("summary"),
        }).execute().data[0]
        r["_event"] = ev["id"]
    if not r.get("event_id"):
        db().table("ap_incidents").update({"event_id": r["_event"]}).eq("id", r["id"]).execute()
        r["event_id"] = r["_event"]
    db().rpc("ap_refresh_event", {"p_event_id": r["event_id"]}).execute()
    return r


def _make_event_safe(r: dict) -> dict | None:
    """One record that still fails after the retries is left for the next run, never stops the publish."""
    try:
        return _make_event(r)
    except Exception as e:
        print(f"  record {r.get('id')}: not published this time ({type(e).__name__}: {str(e)[:120]})", flush=True)
        return None


def _ids(table: str, col: str, **eq) -> set:
    out: set = set()
    last = None
    while True:
        q = db().table(table).select(f"id,{col}" if col != "id" else "id")
        for k, v in eq.items():
            q = q.eq(k, v)
        if last is not None:
            q = q.gt("id", last)
        rows = retry(lambda: q.order("id").limit(1000).execute().data) or []
        if not rows:
            return out
        out.update(r[col] for r in rows if r.get(col) is not None)
        last = rows[-1]["id"]


def remove_empty_events() -> int:
    """Events with no record behind them (left by an interrupted publish or a detach) are deleted, or hidden
    when something (a removal request) still points at them."""
    # Records that found no New Mexico town but still point at an event: detach them (the event is then empty
    # or keeps its other, placed records). These were the "site entries with no map spot".
    stray = retry(lambda: db().table("ap_incidents").select("id,event_id").eq("geocode_status", "failed")
                  .not_.is_("event_id", "null").limit(1000).execute().data) or []
    for r in stray:
        retry(lambda: db().table("ap_incidents").update({"event_id": None}).eq("id", r["id"]).execute())
        retry(lambda: db().rpc("ap_refresh_event", {"p_event_id": r["event_id"]}).execute())
    if stray:
        print(f"records with no NM town detached from events: {len(stray)}", flush=True)
    used = _ids("ap_incidents", "event_id")
    events = _ids("ap_events", "id", hidden=False)
    empty = sorted(events - used)
    for eid in empty:
        try:
            retry(lambda: db().table("ap_events").delete().eq("id", eid).execute())
        except Exception:
            retry(lambda: db().table("ap_events").update({"hidden": True}).eq("id", eid).execute())
    print(f"empty events removed: {len(empty)} (of {len(events)} visible events)", flush=True)
    return len(empty)


def ensure_events(run, max_minutes: float = 40) -> list[dict]:
    """Give every placed, visible, unheld record its own public event. Pages through the backlog (the API
    returns at most 1,000 rows per request) two at a time, until none are left."""
    from concurrent.futures import ThreadPoolExecutor

    t0 = time.monotonic()
    made: list[dict] = []
    last_id = 0
    # 2 at a time: each event is three requests including a recompute; more than that once knocked the
    # shared database over (Oct 26).
    with ThreadPoolExecutor(max_workers=2) as pool:
        while (time.monotonic() - t0) / 60 < max_minutes:
            # Only geocoded, visible records that aren't waiting for human review become events.
            rows = retry(lambda: (
                db().table("ap_incidents").select(FIELDS)
                .is_("event_id", "null").eq("hidden", False).eq("needs_review", False)
                .not_.is_("geocode_status", "null")
                .neq("geocode_status", "failed")  # no New Mexico town: never becomes a public event
                .gt("id", last_id).order("id").limit(1000).execute().data
            )) or []
            if not rows:
                break
            last_id = rows[-1]["id"]  # records that failed this time are skipped until the next run
            for r in pool.map(_make_event_safe, rows):
                if r is None:
                    continue
                made.append(r)
                run.items_in += 1
            print(f"  published {len(made)} so far", flush=True)
    return made


def merge(keep_event: str, drop_event: str):
    if not keep_event or not drop_event or keep_event == drop_event:
        return
    retry(lambda: db().table("ap_incidents").update({"event_id": keep_event}).eq("event_id", drop_event).execute())
    try:
        retry(lambda: db().table("ap_events").delete().eq("id", drop_event).execute())
    except Exception as e:  # e.g. a removal request points at it: keep the empty event hidden instead
        print(f"  could not delete event {drop_event}: {str(e)[:120]}", flush=True)
        retry(lambda: db().table("ap_events").update({"hidden": True}).eq("id", drop_event).execute())
    retry(lambda: db().rpc("ap_refresh_event", {"p_event_id": keep_event}).execute())


def _record(a_id: int, b_id: int, same: bool, why: str, model: str):
    a, b = sorted([a_id, b_id])
    retry(lambda: db().table("ap_dedupe_checks").upsert({
        "incident_a": a, "incident_b": b, "same_event": same, "rationale": why[:500], "model": model,
    }).execute())


def check_incident(run, r: dict) -> int:
    """Compare one published record with its likely twins; merge the ones that are the same death.
    Rules first (free), the model only for pairs the rules can't settle. Returns merges made."""
    if r.get("record_type") == "road_death" or not r.get("event_id"):
        return 0  # official crash records are one row per crash
    merged = 0
    cands = retry(lambda: db().rpc("ap_dedupe_candidates", {"p_incident_id": r["id"]}).execute().data) or []
    # Already merged into this event: nothing to decide.
    cands = [c for c in cands if c.get("candidate_event_id") != r.get("event_id")]
    if not cands:
        return 0
    ids = [c["candidate_id"] for c in cands]
    rows = {x["id"]: x for x in (retry(lambda: db().table("ap_incidents").select(FIELDS).in_("id", ids).execute().data) or [])}
    dist = {c["candidate_id"]: c.get("distance_m") for c in cands}
    # Town-level candidates all sit at distance 0, so rank by what tells twins apart: closest date, most
    # similar wording. The 8 checked are then the likely twins, not an arbitrary 8 of the town's records.
    ranked = sorted(rows.values(), key=lambda o: (date_gap_days(r, o), -summary_similarity(r, o)))
    for other in ranked[:6]:
        c = {"distance_m": dist.get(other["id"])}
        verdict = rule_verdict(r, other)
        if verdict is not None:
            same, why, model = verdict, ("same town and cause, same day or same story" if verdict else "dates too far apart"), "rule"
        else:
            msg = create_with_tool(
                client,
                "decide",
                model=MODEL_DEDUPE,
                max_tokens=200,
                system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
                tools=[TOOL],
                messages=[{"role": "user", "content": f"A: {describe(r)}\nB: {describe(other)}\nDistance: {round(c.get('distance_m') or 0)} m"}],
            )
            run.ai("dedupe", MODEL_DEDUPE, msg.usage)
            d = tool_input(msg)
            if not d or "same_event" not in d:
                continue  # no usable answer: leave the pair unchecked so a later run asks again
            same, why, model = bool(d["same_event"]), d.get("rationale") or "", MODEL_DEDUPE
        _record(r["id"], other["id"], same, why, model)
        if same:
            kept = merge_incidents(other["id"], r["id"])
            if kept:
                r["event_id"] = kept
                merged += 1
    return merged


def merge_incidents(keep_id: int, drop_id: int) -> str | None:
    """Merge the events of two records, reading their current events first: earlier merges in the same run
    may have moved either record (a stale event id once broke a run with a foreign-key error, Oct 27)."""
    cur = {x["id"]: x.get("event_id") for x in (retry(lambda: db().table("ap_incidents").select("id,event_id")
                                                    .in_("id", [keep_id, drop_id]).execute().data) or [])}
    keep, drop = cur.get(keep_id), cur.get(drop_id)
    if not keep or not drop or keep == drop:
        return None
    alive = {x["id"] for x in (retry(lambda: db().table("ap_events").select("id").in_("id", [keep, drop]).execute().data) or [])}
    if keep not in alive:
        keep, drop = drop, keep
    if keep not in alive:
        return None
    merge(keep, drop)
    return keep


def check_incident_safe(run, r: dict) -> int:
    """One record that fails (a dropped connection after the retries, a race) never stops the run."""
    try:
        return check_incident(run, r)
    except BudgetExceeded:
        raise  # the run's AI budget is spent: stop, don't keep calling
    except Exception as e:
        print(f"  record {r.get('id')}: duplicate check skipped ({type(e).__name__}: {str(e)[:120]})", flush=True)
        return 0


def _sweep_start() -> int:
    rows = retry(lambda: db().table("ap_pipeline_runs").select("meta").eq("job", "dedupe_sweep")
                 .order("started_at", desc=True).limit(1).execute().data) or []
    return int(((rows[0].get("meta") or {}) if rows else {}).get("last_id") or 0)


def sweep(max_minutes: float):
    """Go back over every published death record (oldest first, resuming where the last sweep stopped)
    and merge duplicates the publish step never got to. Wraps around when it reaches the end."""
    t0 = time.monotonic()
    with PipelineRun("dedupe_sweep") as run:
        last = _sweep_start()
        checked = merges = 0
        while (time.monotonic() - t0) / 60 < max_minutes:
            rows = retry(lambda: db().table("ap_incidents").select(FIELDS)
                         .eq("record_type", "death").eq("hidden", False).not_.is_("event_id", "null")
                         .gt("id", last).order("id").limit(200).execute().data) or []
            if not rows:
                last = 0  # start over next time
                break
            for r in rows:
                try:
                    merges += check_incident_safe(run, r)
                except BudgetExceeded as e:
                    print(f"  {e}", flush=True)
                    max_minutes = 0  # end the sweep; it resumes from here next time
                    break
                checked += 1
                last = r["id"]
                if (time.monotonic() - t0) / 60 >= max_minutes:
                    break
        run.items_in, run.items_out = checked, merges
        run.meta = {"last_id": last}
    print(f"dedupe sweep: checked {checked} records, merged {merges} duplicates (next start after id {last}); "
          f"AI cost ${run.cost:.2f}")


def main(limit: int, max_minutes: float = 40):
    t0 = time.monotonic()
    with PipelineRun("dedupe") as run:
        try:
            run.meta = {"empty_events_removed": remove_empty_events()}
        except Exception as e:  # housekeeping never blocks publishing
            print(f"empty-event cleanup skipped: {type(e).__name__}: {str(e)[:150]}", flush=True)
        fresh = ensure_events(run, max_minutes)[:limit]
        for r in fresh:
            if (time.monotonic() - t0) / 60 >= max_minutes * 1.5:
                print("  dedupe: time limit, the rest waits for the sweep", flush=True)
                break
            run.items_out += check_incident_safe(run, r)
        retry(lambda: db().rpc("ap_refresh_area_coverage", {}).execute())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=500)
    ap.add_argument("--max-minutes", type=float, default=40, help="stop publishing new events after this long")
    ap.add_argument("--sweep", action="store_true", help="go back over already-published records for duplicates")
    a = ap.parse_args()
    sweep(a.max_minutes) if a.sweep else main(a.limit, a.max_minutes)
